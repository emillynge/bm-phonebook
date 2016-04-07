from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.layout import Layout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Rectangle, Rotate, Translate, PushMatrix, PopMatrix



class SetSizeWidget(Widget):
    def set_size(self, root):
        pass

    def _set_size(self, root=None):
        root = root or self.get_root_window()
        if root and root.size != self._root_sz:
            self._root_sz = tuple(root.size)
            for child in self.children:
                if hasattr(child, 'set_size') and not hasattr(child, 'do_layout'):
                    child.set_size(root=root)
            self.set_size(root)
        return root


class SetSizeLayout(Layout, SetSizeWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._root_sz = (None, None)

    def add_widget(self, widget: Widget, index=0):
        super().add_widget(widget, index=0)
        if hasattr(widget, 'set_size'):
            widget._set_size()

    def do_layout(self, *largs):
        self._set_size()
        super().do_layout()

class PaddedLayout(SetSizeLayout):
    def set_size(self, root=None):
        pad_percent = .02
        root = super().set_size(root)
        if root:
            self.padding = root.width * pad_percent, root.height * pad_percent
            self.spacing = min(root.size) * pad_percent
        return root


class SetSizeBoxLayout(SetSizeLayout, BoxLayout): pass

class PaddedBoxLayout(PaddedLayout, BoxLayout):
    pass


class PaddedGridLayout(PaddedLayout, GridLayout):
    pass


class WrappedLabel(Label):
    def __init__(self, wrap_dir='vertical', **kwargs):
        if wrap_dir in ['both', 'vertical']:
            kwargs['size_hint_y'] = None

        if wrap_dir in ['both', 'horizontal']:
            kwargs['size_hint_x'] = None
        super().__init__(**kwargs)
        self.texture_update()
        self.wrap_dir = wrap_dir
        self.wrap()

    def wrap(self):
        if self.wrap_dir in ['both', 'vertical']:
            self.height = self.texture_size[1] * (1 + .5)

        if self.wrap_dir in ['both', 'horizontal']:
            self.width = self.texture_size[0] * (1 + .2)


class VertWidget(Widget):
    pass


class VertWrapLabel(VertWidget, WrappedLabel):
    def wrap(self):
        if self.wrap_dir in ['both', 'vertical']:
            self.height = self.texture_size[0] * (1 + .5)

        if self.wrap_dir in ['both', 'horizontal']:
            self.width = self.texture_size[1] * (1 + .2)


class RelativeSizeLabel(SetSizeWidget, Label):
    def __init__(self, rel_size=.05, **kwargs):
        super().__init__(**kwargs)
        self.rel_size = rel_size

    def set_size(self, root):
        self.font_size = int(min(root.size) * self.rel_size)
        self.texture_update()
        self.wrap()

class RelSzWrapLabel(WrappedLabel, RelativeSizeLabel): pass
class RelSzVertWrapLabel(VertWrapLabel, RelativeSizeLabel): pass