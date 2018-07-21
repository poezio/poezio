"""
A generic tab that displays a text and a boolean choice
"""

import logging
log = logging.getLogger(__name__)

from poezio import windows
from poezio.tabs import Tab


class ConfirmTab(Tab):
    plugin_commands = {}
    plugin_keys = {}

    def __init__(self,
                 core,
                 name,
                 text,
                 short_message,
                 callback,
                 critical=False):
        """Parameters:
        name: The name of the tab
        text: the text shown in the tab
        short_message: what will be displayed at the top and bottom of
          the tab
        callback: the function(bool) that will be called when the user
          makes a choice
        critical: if the message needs to be displayed in a flashy color
        """
        Tab.__init__(self, core)
        self.state = 'highlight'
        self.name = name
        self.default_help_message = windows.HelpText(
            "Choose with arrow keys and press enter")
        self.input = self.default_help_message
        self.infowin_top = windows.ConfirmStatusWin(short_message, critical)
        self.infowin_bottom = windows.ConfirmStatusWin(short_message, critical)
        self.dialog = windows.Dialog(text, critical)
        self.key_func['^I'] = self.toggle_choice
        self.key_func[' '] = self.toggle_choice
        self.key_func['KEY_LEFT'] = self.toggle_choice
        self.key_func['KEY_RIGHT'] = self.toggle_choice
        self.key_func['^M'] = self.validate
        self.resize()
        self.update_keys()
        self.update_commands()
        self.completion_callback = callback
        self.done = False

    def toggle_choice(self):
        self.dialog.toggle_choice()
        self.refresh()
        self.core.doupdate()

    def validate(self):
        self.completion_callback(self.dialog.accept)
        self.close()

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        if self.size.tab_degrade_y:
            display_info_win = False
        else:
            display_info_win = True
        if display_info_win:
            self.info_win.refresh()
        self.refresh_tab_win()
        self.infowin_top.refresh()
        self.infowin_bottom.refresh()
        self.dialog.refresh()
        self.input.refresh()

    def resize(self):
        if self.size.tab_degrade_y:
            info_win_height = 0
            tab_win_height = 0
        else:
            info_win_height = self.core.information_win_size
            tab_win_height = Tab.tab_win_height()

        self.infowin_top.resize(1, self.width, 0, 0)
        self.infowin_bottom.resize(
            1, self.width, self.height - 2 - info_win_height - tab_win_height,
            0)
        self.dialog.resize(self.height - 3 - info_win_height - tab_win_height,
                           self.width, 1, 0)
        self.input.resize(1, self.width, self.height - 1, 0)

    def close(self, arg=None):
        self.done = True
        self.core.close_tab(self)

    def on_input(self, key, raw):
        res = self.input.do_command(key, raw=raw)
        if res and not isinstance(self.input, windows.Input):
            return True
        elif res:
            return False
        if not raw and key in self.key_func:
            return self.key_func[key]()

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height - 3:
            return
        self.dialog.resize(
            self.height - 3 - self.core.information_win_size -
            Tab.tab_win_height(), self.width, 1, 0)
        self.infowin_bottom.resize(
            1, self.width, self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), 0)
