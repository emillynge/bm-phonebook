import asyncio

from kivy.base import EventLoopBase
from kivy.clock import ClockBase
from asyncio import set_event_loop
from guievents import GuiEventLoop

class KivyEventLoop(GuiEventLoop):
    _default_executor = None

    def __init__(self, app: EventLoopBase, clock: ClockBase):
        super().__init__()
        self.app = app
        self.clock = clock

    def mainloop(self):
        set_event_loop(self)
        try:
            self.run_forever()
        finally:
            set_event_loop(None)

    # Event Loop API
    def run(self):
        """Run the event loop.  Block until there is nothing left to do."""
        self.app.run()

    def run_forever(self):
        """Run the event loop.  Block until stop() is called."""
        self.app.run()

    def run_once(self, timeout=None):  # NEW!
        """Run one complete cycle of the event loop."""
        self.app.update()

    def stop(self):  # NEW!
        """Stop the event loop as soon as reasonable.

        Exactly how soon that is may depend on the implementation, but
        no more I/O callbacks should be scheduled.
        """
        super().stop()
        self.app.stop()

    def call_later(self, delay, callback, *args):
        def callback_func(dt):
            callback(*args)
        event = self.clock.schedule_once(callback_func, 0)
        return event

def get_event_loop() -> KivyEventLoop:
    """ Wrapper with type hint to help IDE's determine event loop class
    """
    return asyncio.get_event_loop()