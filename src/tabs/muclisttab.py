"""
A MucListTab is a tab listing the rooms on a conference server.

It has no functionnality except scrolling the list, and allowing the
user to join the rooms.
"""
from gettext import gettext as _

import logging
log = logging.getLogger(__name__)

import curses
import collections
from datetime import datetime

from sleekxmpp.plugins.xep_0030.stanza.items import DiscoItem

import windows
from common import safeJID
from decorators import refresh_wrapper

from . import Tab


class MucListTab(Tab):
    """
    A tab listing rooms from a specific server, displaying various information,
    scrollable, and letting the user join them, etc
    """
    plugin_commands = {}
    plugin_keys = {}

    def __init__(self, server):
        Tab.__init__(self)
        self.state = 'normal'
        self.name = server
        columns = collections.OrderedDict()
        columns['node-part'] = 0
        columns['name'] = 2
        columns['users'] = 3
        self.list_header = windows.ColumnHeaderWin(list(columns))
        self.listview = windows.ListWin(columns)
        self.info_header = windows.MucListInfoWin(_('Chatroom list on server %s (Loading)') % self.name)
        self.default_help_message = windows.HelpText("“j”: join room.")
        self.input = self.default_help_message
        self.key_func["KEY_DOWN"] = self.move_cursor_down
        self.key_func["KEY_UP"] = self.move_cursor_up
        self.key_func['^I'] = self.completion
        self.key_func["/"] = self.on_slash
        self.key_func['j'] = self.join_selected
        self.key_func['J'] = self.join_selected_no_focus
        self.key_func['^M'] = self.join_selected
        self.key_func['KEY_LEFT'] = self.list_header.sel_column_left
        self.key_func['KEY_RIGHT'] = self.list_header.sel_column_right
        self.key_func[' '] = self.sort_by
        self.register_command('close', self.close,
                shortdesc=_('Close this tab.'))
        self.resize()
        self.update_keys()
        self.update_commands()

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        self.info_header.refresh(window=self.listview)
        self.info_win.refresh()
        self.refresh_tab_win()
        self.list_header.refresh()
        self.listview.refresh()
        self.input.refresh()
        self.update_commands()

    def resize(self):
        if self.core.information_win_size >= self.height-3 or not self.visible:
            return
        self.need_resize = False
        self.info_header.resize(1, self.width, self.height-2-self.core.information_win_size - Tab.tab_win_height(), 0)
        column_size = {'node-part': int(self.width*2/8),
                       'name': int(self.width*5/8),
                       'users': self.width-int(self.width*2/8)-int(self.width*5/8)}
        self.list_header.resize_columns(column_size)
        self.list_header.resize(1, self.width, 0, 0)
        self.listview.resize_columns(column_size)
        self.listview.resize(self.height-3-self.core.information_win_size - Tab.tab_win_height(), self.width, 1, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def on_slash(self):
        """
        '/' is pressed, activate the input
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message, self.execute_slash_command)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.do_command("/") # we add the slash

    def close(self, arg=None):
        self.input.on_delete()
        self.core.close_tab(self)

    def join_selected_no_focus(self):
        return

    def set_error(self, msg, code, body):
        """
        If there's an error (retrieving the values etc)
        """
        self._error_message = _('Error: %(code)s - %(msg)s: %(body)s') % {'msg':msg, 'body':body, 'code':code}
        self.info_header.message = self._error_message
        self.info_header.refresh()
        curses.doupdate()

    def on_muc_list_item_received(self, iq):
        """
        Callback called when a disco#items result is received
        Used with command_list
        """
        if iq['type'] == 'error':
            self.set_error(iq['error']['type'], iq['error']['code'], iq['error']['text'])
            return
        def get_items():
            substanza = iq['disco_items']
            for item in substanza['substanzas']:
                if isinstance(item, DiscoItem):
                    yield (item['jid'], item['node'], item['name'])
        items = [(item[0].split('@')[0],
                  item[0],
                  item[2] or '', '') for item in get_items()]
        self.listview.set_lines(items)
        self.info_header.message = _('Chatroom list on server %s') % self.name
        if self.core.current_tab() is self:
            self.refresh()
        else:
            self.state = 'highlight'
            self.refresh_tab_win()
        self.core.doupdate()

    def sort_by(self):
        if self.list_header.get_order():
            self.listview.sort_by_column(
                    col_name=self.list_header.get_sel_column(),
                    asc=False)
            self.list_header.set_order(False)
            self.list_header.refresh()
        else:
            self.listview.sort_by_column(
                    col_name=self.list_header.get_sel_column(),
                    asc=True)
            self.list_header.set_order(True)
            self.list_header.refresh()
        self.core.doupdate()

    def join_selected(self):
        row = self.listview.get_selected_row()
        if not row:
            return
        self.core.command_join(row[1])

    @refresh_wrapper.always
    def reset_help_message(self, _=None):
        curses.curs_set(0)
        self.input = self.default_help_message
        self.input.resize(1, self.width, self.height-1, 0)
        return True

    def execute_slash_command(self, txt):
        if txt.startswith('/'):
            self.input.key_enter()
            self.execute_command(txt)
        return self.reset_help_message()

    def get_name(self):
        return self.name

    def completion(self):
        if isinstance(self.input, windows.Input):
            self.complete_commands(self.input)

    def on_input(self, key, raw):
        res = self.input.do_command(key, raw=raw)
        if res:
            return True
        if not raw and key in self.key_func:
            return self.key_func[key]()

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        self.info_header.resize(1, self.width, self.height-2-self.core.information_win_size - Tab.tab_win_height(), 0)
        self.listview.resize(self.height-3-self.core.information_win_size - Tab.tab_win_height(), self.width, 1, 0)

    def on_lose_focus(self):
        self.state = 'normal'

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(0)

    def on_scroll_up(self):
        return self.listview.scroll_up()

    def on_scroll_down(self):
        return self.listview.scroll_down()

    def move_cursor_up(self):
        self.listview.move_cursor_up()
        self.listview.refresh()
        self.core.doupdate()

    def move_cursor_down(self):
        self.listview.move_cursor_down()
        self.listview.refresh()
        self.core.doupdate()

    def matching_names(self):
        return [(2, self.name)]


