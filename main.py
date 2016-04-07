from collections import defaultdict, UserDict
from functools import partial
import asyncio
from asyncio.queues import Queue, QueueEmpty
from operator import itemgetter
from hashlib import md5
from plyer import browser, call, sms, email

from mywidgets import PaddedBoxLayout, WrappedLabel
from kivyevents import KivyEventLoop, get_event_loop
import gruppewebscrape as scrape

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.core.text import LabelBase
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.uix.settings import SettingsWithSpinner
from kivy.config import ConfigParser
from kivy.properties import (StringProperty)
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.storage.dictstore import DictStore
import json
# Color the background
Window.clearcolor = get_color_from_hex("#FFFFFF")


TEXTCOLOR = get_color_from_hex("#003366")

JSONSETTINGS = json.dumps([
    {
        "type": "string",
        "title": "Hjemmeside",
        "desc": "Fuld URL til den gruppewebside hvor den relevante adresseliste kan findes",
        "section": "Blåt Medlem",
        "key": "bm_url"
    },
    {
        "type": "numeric",
        "title": "Medlemsnummer",
        "desc": "Medlemsnummer som skal bruges til login",
        "section": "Blåt Medlem",
        "key": "bm_mno"
    }
])

# Register fonts
LabelBase.register(
    name="OpenSans",
    fn_regular="./fonts/OpenSans-Regular.ttf",
    fn_bold="./fonts/OpenSans-Bold.ttf",
)


class ContactStore(DictStore):
    tags = 'Navn mno Patrulje'

    def __init__(self, *args, **kwargs):
        super(ContactStore, self).__init__(*args, **kwargs)
        self.ops_q = Queue()

    def task_done(self, *_):
        self.ops_q.task_done()

    async def join(self):
        while True:
            try:
                func, args, kwargs = self.ops_q.get_nowait()
                func(self.task_done, *args, **kwargs)
            except QueueEmpty:
                break

        await self.ops_q.join()

    def enqueue(self, func, *args, **kwargs):
        self.ops_q.put_nowait((func, args, kwargs))

    async def set_contacts(self, contacts: dict):
        self.clear()
        hashmap = defaultdict(set)
        for key, person_info in contacts.items():
            self.hash_contact(key, person_info, hashmap)
            self.enqueue(self.async_put, key, dump=json.dumps(person_info))

        for tag, keys in hashmap.items():
            self.enqueue(self.async_put, tag, keys=', '.join(keys))

        await self.join()

    def hash_contact(self, key, info: dict, hashmap):
        for tag in self.tags.split():
            for part in info.get(tag, '').split():
                s = 'tag_'
                for c in part.lower():
                    s += c
                    hashmap[s].add(key)

    def search(self, tag):
        try:
            keys = self.get('tag_' + str(tag).lower())
        except KeyError:
            return

        if keys:
            for key in keys['keys'].split(', '):
                yield json.loads(self.get(key)['dump'])


class ContactStoreHolder(UserDict):
    def __missing__(self, key):
        filename = 'contacts/' + md5(str(key).encode()).hexdigest() + '.pkl'
        self.__setitem__(key, ContactStore(filename))
        return self.__getitem__(key)

    def __getitem__(self, item) -> ContactStore:
        return super().__getitem__(item)

class AsyncValueHolder(Queue):
    def __init__(self, max_size=1, **kwargs):
        super().__init__(max_size, **kwargs)

    def clear(self):
        while self.full():
            self.get_nowait()

    def read(self):
        if self.empty():
            return None
        return self._queue[0]

    async def async_read(self):
        if self.empty():
            value = await self.get()
            self.put_nowait(value)
        else:
            value = self._queue[0]
        return value



class SettingsScreen(Screen):
    pass

class PassGetter(Popup):
    class _PassCancel:
        def __bool__(self):
            return False
    PassCancel = _PassCancel()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = ''
        self.clear_state()
        self._password = AsyncValueHolder()
        self.login_lock = asyncio.locks.Lock()
        self.logged_in = False

        layout = PaddedBoxLayout(orientation='vertical')
        # input box
        layout.add_widget(WrappedLabel(text='Kodeord til Blåt medlem'))
        self.inp = TextInput(text="", multiline=False,
                             password=True)

        layout.add_widget(self.inp)
        msg = ("Din kode gemmes ikke til disk, men findes udelukkende"
               " i den virtuelle hukommelse. Derfor skal det indtastes"
               "efter genstart af app'en. Tilgengæld er der ingen risiko"
               " for at kodeordet 'lækkes' til 3.part.\n\n"
               "Dette er gjort fordi jeg ikke ønsker at være ansvarlig "
               "for at opbevare andres koder.")
        #layout.add_widget(WrappedLabel(text=msg, multiline=True))

        # buttons
        self.close_button = Button(text='Done')
        self.close_button.on_release = self.close

        self.cancel_button = Button(text='Cancel')
        self.cancel_button.on_release = self.cancel

        buttons = PaddedBoxLayout(size_hint_y=None, orientation='horizontal')
        buttons.add_widget(self.close_button)
        buttons.add_widget(self.cancel_button)
        layout.add_widget(buttons)

        # add layout
        self.add_widget(layout)

    @property
    def password(self):
        return self._password.read()

    async def login(self, url, mno, *_):
        async with self.login_lock:
            while not self.logged_in:
                passw = self._password.read()
                while not passw:
                    self.open()
                    passw = await self._password.async_read()
                    if passw is self.PassCancel:
                        return

                try:
                    scrape.login(url, mno, passw)
                    self.logged_in = True
                except scrape.LoginFailed as e:
                    self._password.clear()
                    raise

    def clear_state(self):
        self.state = 'nopass'

    @property
    def canceled(self):
        if self.state == 'cancel':
            return True
        return False

    @property
    def ready(self):
        if self.state == 'entered':
            return True
        return False

    def open(self):
        self._password.clear()
        self.inp.text = ""
        super().open()

    def close(self, *_):
        self._password.put_nowait(self.inp.text)
        self.dismiss()

    def cancel(self, *_):
        self._password.put_nowait(self.PassCancel)
        self.dismiss()


class UpdatePopup(Popup):
    """Popup for telling user to wait for updating to finish
    """
    message = StringProperty(default="")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logged_in = False
        self.pass_getter = PassGetter()
        self.contacts = ContactStoreHolder()

    def open(self, config: ConfigParser):
        url = config.get('Blåt Medlem', 'bm_url')
        mno = config.get('Blåt Medlem', 'bm_mno')

        if not url or not mno:
            self.message = ("Du har ikke konfigureret en hjemmeside at trække"
                            " data fra og eller medlemsnummer."
                            " Gå ind i Settings (oppe til højre) og"
                            " og gør dette for du opdaterer.")
            super().open()
            Clock.schedule_once(self.dismiss, 1)
            return

        super().open()
        get_event_loop().create_task(self.update(url, mno))

    async def update(self, url, mno):
        self.message = "Logger ind på {}".format(url)
        try:
            await self.pass_getter.login(url, mno)
        except scrape.LoginFailed as e:
            self.message = str(e)
            Clock.schedule_once(self.dismiss, 2)
            return

        if not self.pass_getter.logged_in:
            self.dismiss()
            return
        self.message = "Henter data fra {}".format(url)
        info = scrape.get_info(url)
        await self.contacts[url].set_contacts(info)
        self.dismiss()

class AboutScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        label = Label(
            text=self.get_about_text(),
            halign="center",
            markup=True,
            center_y=.5,
            font_name="OpenSans",
            color=TEXTCOLOR,
        )
        label.on_ref_press = self.on_ref_press
        layout = PaddedBoxLayout()
        layout.add_widget(label)
        self.add_widget(layout)

    def get_about_text(self):
        return ("Denne App er lavet i [b][ref=kivy]kivy[/ref][/b]\n"
                "Store dele af koden er sakset fra [b][ref=source]Math Tutor[/ref][/b]\n"
                "Math Tutor er lavet af [b][ref=gopar]Daniel Gopar[/ref][/b]"
                "som del af en Kivy guide\n"
                "This app is under the [b][ref=mit]MIT License[/ref][/b]\n"
                )

    def on_ref_press(self, ref):
        _dict = {
            "source": "https://github.com/gopar/Kivy-Tutor",
            "gopar": "http://www.pygopar.com",
            "kivy": "http://kivy.org/#home",
            "mit": "https://github.com/emillynge/bm-phonebook/blob/master/LICENSE"
        }

        browser.open(_dict[ref])


class PhonebookRoot(PaddedBoxLayout):
    def __init__(self, root: App, **kwargs):
        super().__init__(**kwargs)
        self.root = root
        self.updater = UpdatePopup()

        self.screen_mgr = ScreenManager()
        self.add_widget(self.screen_mgr)

        self.about_screen = AboutScreen(name="about")
        self.phonebook_screen = PhonebookScreen(self, name="phonebook")
#        self.settings_screen = SettingsScreen(name="settings")
        self.screen_mgr.add_widget(self.about_screen)
        self.screen_mgr.add_widget(self.phonebook_screen)
        self.screen_list = []

    @property
    def contacts(self) -> ContactStore:
        url = self.root.config.get('Blåt Medlem', 'bm_url')
        return self.updater.contacts[url]


    def on_back_button(self):
        # Check if there are any scresn to go back to
        if self.screen_list:
            # if there are screens we can go back to, the just do it
            self.screen_mgr.current = self.screen_list.pop()
            # Saw we don't want to close
            return True
        # No more screens to go back to
        return False

    def change_screen(self, next_screen):
        # If screen is not already in the list fo prevous screens
        if self.screen_mgr.current not in self.screen_list:
            self.screen_list.append(self.screen_mgr.current)

        if next_screen == "about":
            self.screen_mgr.current = 'about'

class ResLabel(Label): pass
class SearchResult(PaddedBoxLayout):
    display_tags = 'Navn Patrulje'
    actions = {'Call': ('mobile', call.makecall),
               'SMS': ('mobile', sms.send),
               'Email': ('Email', email.send),
               }

    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        self._text = ResLabel(size_hint_x=3, color=TEXTCOLOR)
        self.add_widget(self._text)
        for name, (field, callback) in self.actions.items():
            button = Button(text=name)
            button.on_release = partial(self.do_action, name, field, callback)
            self.add_widget(button)
        self.info = None

    @property
    def text(self):
        return self._text.text

    @text.setter
    def text(self, s):
        self._text.text = s

    def do_action(self, name, field, callback, *_):
        if self.info:
            callback(self.info[field])

    def set_contact(self, info):
        if info is None:
            self.clear()
            return

        self.info = info
        self.text = '\n'.join(self.info.get(tag, '')
                              for tag in self.display_tags.split())

    def clear(self):
        self.info = None
        self.text = ""


class PhoneBookSearch(PaddedBoxLayout):
    max_results = 10

    def __init__(self, root: PhonebookRoot, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.add_widget(WrappedLabel(text='Søg på navn eller patrulje'.format(ContactStore.tags),
                                     color=TEXTCOLOR, font_size=40))
        self.inp = TextInput(text="", multiline=False, size_hint_y=None, height=60,
                             font_size=30)
        self.add_widget(self.inp)
        self.inp.bind(text=self.on_search_term)
        self.root = root
        self.results = list()

        for i in range(self.max_results):
            button = SearchResult()
            self.add_widget(button)
            self.results.append(button)

    def on_search_term(self, inst, value):
        contacts = self.root.contacts
        results = sorted(contacts.search(value), key=itemgetter('Navn')) + [None] * self.max_results

        for r, b in zip(results, self.results):
            b.set_contact(r)

class PhonebookScreen(Screen):
    def __init__(self, root: PhonebookRoot, **kwargs):
        super().__init__(**kwargs)
        self.root = root
        self.searcher = PhoneBookSearch(root)
        self.add_widget(self.searcher)

class PhonebookApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.use_kivy_settings = False
        Window.bind(on_keyboard=self.on_back_button)

    def on_back_button(self, window, key, *args):
        # user presses back button
        if key == 27:
            return self.root.on_back_button()

    def open_about(self, *_):
        self.root.change_screen('about')

    def build_config(self, config):
        config.setdefaults("Blåt Medlem", {"bm_url": None, "bm_mno": None})

    def build_settings(self, settings: SettingsWithSpinner):
        settings.add_json_panel("BM Telefonbog", self.config,
                                data=JSONSETTINGS)

    def update_phonebook(self):
        self.root.updater.open(self.config)

    def build(self):
        self.root = PhonebookRoot(root=self)
        self.root.screen_mgr.current = self.root.phonebook_screen.name
        return self.root

if __name__ == '__main__':
    KivyEventLoop(PhonebookApp(), Clock).mainloop()