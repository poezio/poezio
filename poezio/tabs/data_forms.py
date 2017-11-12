"""
Defines the data-forms Tab
"""

import logging
log = logging.getLogger(__name__)

from poezio import windows
from poezio.tabs import Tab


class DataFormsTab(Tab):
    """
    A tab contaning various window type, displaying
    a form that the user needs to fill.
    """
    plugin_commands = {}

    def __init__(self, core, form, on_cancel, on_send, kwargs):
        Tab.__init__(self, core)
        self._form = form
        self._on_cancel = on_cancel
        self._on_send = on_send
        self._kwargs = kwargs
        self.fields = []
        for field in self._form:
            self.fields.append(field)
        self.topic_win = windows.Topic()
        self.form_win = windows.FormWin(form, self.height - 4, self.width, 1,
                                        0)
        self.help_win = windows.HelpText("Ctrl+Y: send form, Ctrl+G: cancel")
        self.help_win_dyn = windows.HelpText()
        self.key_func['KEY_UP'] = self.form_win.go_to_previous_input
        self.key_func['KEY_DOWN'] = self.form_win.go_to_next_input
        self.key_func['^G'] = self.on_cancel
        self.key_func['^Y'] = self.on_send
        self.resize()
        self.update_commands()

    def on_cancel(self):
        self._on_cancel(self._form, **self._kwargs)
        return True

    def on_send(self):
        self._form.reply()
        self.form_win.reply()
        self._on_send(self._form, **self._kwargs)
        return True

    def on_input(self, key, raw=False):
        if key in self.key_func:
            res = self.key_func[key]()
            if res:
                return res
            self.help_win_dyn.refresh(self.form_win.get_help_message())
            self.form_win.refresh_current_input()
        else:
            self.form_win.on_input(key, raw=raw)

    def resize(self):
        self.need_resize = False
        self.topic_win.resize(1, self.width, 0, 0)
        self.form_win.resize(self.height - 3 - Tab.tab_win_height(),
                             self.width, 1, 0)
        self.help_win.resize(1, self.width, self.height - 1, 0)
        self.help_win_dyn.resize(1, self.width,
                                 self.height - 2 - Tab.tab_win_height(), 0)
        self.lines = []

    def refresh(self):
        if self.need_resize:
            self.resize()
        self.topic_win.refresh(self._form['title'])
        self.refresh_tab_win()
        self.help_win.refresh()
        self.help_win_dyn.refresh(self.form_win.get_help_message())
        self.form_win.refresh()
