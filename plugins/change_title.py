"""
This plugin will set the title of your terminal to the name of the current tab.

"""
from poezio.plugin import BasePlugin
import sys


class Plugin(BasePlugin):
    def init(self):
        self.on_tab_change(0, self.core.current_tab_nb)
        self.api.add_event_handler('tab_change', self.on_tab_change)

    def cleanup(self):
        "Re-set the terminal title to 'poezio'"
        sys.stdout.write("\x1b]0;poezio\x07")
        sys.stdout.flush()

    def on_tab_change(self, old, new):
        new_tab = self.core.get_tab_by_number(new)
        sys.stdout.write("\x1b]0;{}\x07".format(new_tab.name))
        sys.stdout.flush()

