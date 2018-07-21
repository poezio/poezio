"""
A generic tab that displays a serie of items in a scrollable, searchable,
sortable list.  It should be inherited, to actually provide methods that
insert items in the list, and that lets the user interact with them.
"""

import logging
log = logging.getLogger(__name__)

import curses
import collections

from poezio import windows
from poezio.decorators import refresh_wrapper

from poezio.tabs import Tab


class ListTab(Tab):
    plugin_commands = {}
    plugin_keys = {}

    def __init__(self, core, name, help_message, header_text, cols):
        """Parameters:
        name: The name of the tab
        help_message: The default help message displayed instead of the
        input
        header_text: The text displayed on the header line, at the top of
        the tab
        cols: a tuple of 2-tuples. e.g. (('column1_name', number),
                                         ('column2_name', number))
        """
        Tab.__init__(self, core)
        self.state = 'normal'
        self._error_message = ''
        self.name = name
        columns = collections.OrderedDict()
        for col, num in cols:
            columns[col] = num
        self.list_header = windows.ColumnHeaderWin(list(columns))
        self.listview = windows.ListWin(columns)
        self.info_header = windows.MucListInfoWin(header_text)
        self.default_help_message = windows.HelpText(help_message)
        self.input = self.default_help_message
        self.key_func["KEY_DOWN"] = self.move_cursor_down
        self.key_func["KEY_UP"] = self.move_cursor_up
        self.key_func['^I'] = self.completion
        self.key_func["/"] = self.on_slash
        self.key_func['KEY_LEFT'] = self.list_header.sel_column_left
        self.key_func['KEY_RIGHT'] = self.list_header.sel_column_right
        self.key_func[' '] = self.sort_by
        self.register_command('close', self.close, shortdesc='Close this tab.')
        self.resize()
        self.update_keys()
        self.update_commands()

    def get_columns_sizes(self):
        """
        Must be implemented in subclasses. Must return a dict like this:
        {'column1_name': size1,
         'column2_name': size2}
        Where the size are calculated based on the size of the tab etc
        """
        raise NotImplementedError

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        if self.size.tab_degrade_y:
            display_info_win = False
        else:
            display_info_win = True

        self.info_header.refresh(window=self.listview)
        if display_info_win:
            self.info_win.refresh()
        self.refresh_tab_win()
        self.list_header.refresh()
        self.listview.refresh()
        self.input.refresh()

    def resize(self):
        if self.size.tab_degrade_y:
            info_win_height = 0
            tab_win_height = 0
        else:
            info_win_height = self.core.information_win_size
            tab_win_height = Tab.tab_win_height()

        self.info_header.resize(
            1, self.width, self.height - 2 - info_win_height - tab_win_height,
            0)
        column_size = self.get_columns_sizes()
        self.list_header.resize_columns(column_size)
        self.list_header.resize(1, self.width, 0, 0)
        self.listview.resize_columns(column_size)
        self.listview.resize(
            self.height - 3 - info_win_height - tab_win_height, self.width, 1,
            0)
        self.input.resize(1, self.width, self.height - 1, 0)

    def on_slash(self):
        """
        '/' is pressed, activate the input
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message,
                                          self.execute_slash_command)
        self.input.resize(1, self.width, self.height - 1, 0)
        self.input.do_command("/")  # we add the slash

    def close(self, arg=None):
        self.core.close_tab(self)

    def set_error(self, msg, code, body):
        """
        If there's an error (retrieving the values etc)
        """
        self._error_message = 'Error: %(code)s - %(msg)s: %(body)s' % {
            'msg': msg,
            'body': body,
            'code': code
        }
        self.info_header.message = self._error_message
        self.info_header.refresh()
        curses.doupdate()

    def sort_by(self):
        if self.list_header.get_order():
            self.listview.sort_by_column(
                col_name=self.list_header.get_sel_column(), asc=False)
            self.list_header.set_order(False)
            self.list_header.refresh()
        else:
            self.listview.sort_by_column(
                col_name=self.list_header.get_sel_column(), asc=True)
            self.list_header.set_order(True)
            self.list_header.refresh()
        self.core.doupdate()

    @refresh_wrapper.always
    def reset_help_message(self, _=None):
        if self.closed:
            return True
        curses.curs_set(0)
        self.input = self.default_help_message
        self.input.resize(1, self.width, self.height - 1, 0)
        return True

    def execute_slash_command(self, txt):
        if txt.startswith('/'):
            self.input.key_enter()
            self.execute_command(txt)
        return self.reset_help_message()

    def completion(self):
        if isinstance(self.input, windows.Input):
            self.complete_commands(self.input)

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
        self.info_header.resize(
            1, self.width, self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), 0)
        self.listview.resize(
            self.height - 3 - self.core.information_win_size -
            Tab.tab_win_height(), self.width, 1, 0)

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
