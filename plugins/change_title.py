"""
This plugin will set the title of your terminal to the name of the current tab.

"""
from poezio.plugin import BasePlugin
import sys


class Plugin(BasePlugin):
    def init(self):
        self.on_tab_change(None, new_tab=self.core.tabs.current_tab)
        self.api.add_event_handler('tab_change', self.on_tab_change)

    def cleanup(self):
        "Re-set the terminal title to 'poezio'"
        sys.stdout.write("\x1b]0;poezio\x07")
        sys.stdout.flush()

    def on_tab_change(self, old_tab, new_tab):
        sys.stdout.write("\x1b]0;{}\x07".format(new_tab.name))
        sys.stdout.flush()
