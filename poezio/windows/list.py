"""
Windows relevant for the listing tabs, not much else
"""

import logging
log = logging.getLogger(__name__)

import curses

from poezio.windows.base_wins import Win
from poezio.theming import to_curses_attr, get_theme


class ListWin(Win):
    """
    A list (with no depth, so not for the roster) that can be
    scrolled up and down, with one selected line at a time
    """

    def __init__(self, columns, with_headers=True):
        Win.__init__(self)
        self._columns = columns  # a dict {'column_name': tuple_index}
        self._columns_sizes = {}  # a dict {'column_name': size}
        self.sorted_by = (None, None)  # for example: ('name', '↑')
        self.lines = []  # a list of dicts
        self._selected_row = 0
        self._starting_pos = 0  # The column number from which we start the refresh

    @property
    def pos(self):
        if len(self.lines) > self.height:
            return len(self.lines)
        else:
            return 0

    def empty(self):
        """
        emtpy the list and reset some important values as well
        """
        self.lines = []
        self._selected_row = 0
        self._starting_pos = 0

    def resize_columns(self, dic):
        """
        Resize the width of the columns
        """
        self._columns_sizes = dic

    def sort_by_column(self, col_name, asc=True):
        """
        Sort the list by the given column, ascendant or descendant
        """
        if not col_name:
            return
        elif asc:
            self.lines.sort(key=lambda x: x[self._columns[col_name]])
        else:
            self.lines.sort(
                key=lambda x: x[self._columns[col_name]], reverse=True)
        self.refresh()
        curses.doupdate()

    def add_lines(self, lines):
        """
        Append some lines at the end of the list
        """
        if not lines:
            return
        self.lines.extend(lines)

    def set_lines(self, lines):
        """
        Set the lines to another list
        """
        if not lines:
            return
        self.lines = lines

    def get_selected_row(self):
        """
        Return the tuple representing the selected row
        """
        if self._selected_row is not None and self.lines:
            return self.lines[self._selected_row]
        return None

    def refresh(self):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        lines = self.lines[self._starting_pos:self._starting_pos + self.height]
        for y, line in enumerate(lines):
            x = 0
            for col in self._columns.items():
                try:
                    txt = line[col[1]] or ''
                except KeyError:
                    txt = ''
                size = self._columns_sizes[col[0]]
                txt += ' ' * (size - len(txt))
                if not txt:
                    continue
                if line is self.lines[self._selected_row]:
                    self.addstr(
                        y, x, txt[:size],
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
                else:
                    self.addstr(y, x, txt[:size])
                x += size
        self._refresh()

    def move_cursor_down(self):
        """
        Move the cursor Down
        """
        if not self.lines:
            return
        if self._selected_row < len(self.lines) - 1:
            self._selected_row += 1
        while self._selected_row >= self._starting_pos + self.height:
            self._starting_pos += self.height // 2
        if self._starting_pos < 0:
            self._starting_pos = 0
        return True

    def move_cursor_up(self):
        """
        Move the cursor Up
        """
        if not self.lines:
            return
        if self._selected_row > 0:
            self._selected_row -= 1
        while self._selected_row < self._starting_pos:
            self._starting_pos -= self.height // 2
        return True

    def scroll_down(self):
        if not self.lines:
            return
        self._selected_row += self.height
        if self._selected_row > len(self.lines) - 1:
            self._selected_row = len(self.lines) - 1
        while self._selected_row >= self._starting_pos + self.height:
            self._starting_pos += self.height // 2
        if self._starting_pos < 0:
            self._starting_pos = 0
        return True

    def scroll_up(self):
        if not self.lines:
            return
        self._selected_row -= self.height + 1
        if self._selected_row < 0:
            self._selected_row = 0
        while self._selected_row < self._starting_pos:
            self._starting_pos -= self.height // 2
        return True


class ColumnHeaderWin(Win):
    """
    A class displaying the column's names
    """

    def __init__(self, columns):
        Win.__init__(self)
        self._columns = columns
        self._columns_sizes = {}
        self._column_sel = ''
        self._column_order = ''
        self._column_order_asc = False

    def resize_columns(self, dic):
        self._columns_sizes = dic

    def get_columns(self):
        return self._columns

    def refresh(self):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        x = 0
        for col in self._columns:
            txt = col
            if col in self._column_order:
                if self._column_order_asc:
                    txt += get_theme().CHAR_COLUMN_ASC
                else:
                    txt += get_theme().CHAR_COLUMN_DESC
            #⇓⇑↑↓⇧⇩▲▼
            size = self._columns_sizes[col]
            txt += ' ' * (size - len(txt))
            if col in self._column_sel:
                self.addstr(
                    0, x, txt,
                    to_curses_attr(get_theme().COLOR_COLUMN_HEADER_SEL))
            else:
                self.addstr(0, x, txt,
                            to_curses_attr(get_theme().COLOR_COLUMN_HEADER))
            x += size
        self._refresh()

    def sel_column(self, dic):
        self._column_sel = dic

    def get_sel_column(self):
        return self._column_sel

    def set_order(self, order):
        self._column_order = self._column_sel
        self._column_order_asc = order

    def get_order(self):
        if self._column_sel == self._column_order:
            return self._column_order_asc
        else:
            return False

    def sel_column_left(self):
        if self._column_sel in self._columns:
            index = self._columns.index(self._column_sel)
            if index > 1:
                index = index - 1
            else:
                index = 0
        else:
            index = 0
        self._column_sel = self._columns[index]
        self.refresh()

    def sel_column_right(self):
        if self._column_sel in self._columns:
            index = self._columns.index(self._column_sel)
            if index < len(self._columns) - 2:
                index = index + 1
            else:
                index = len(self._columns) - 1
        else:
            index = len(self._columns) - 1
        self._column_sel = self._columns[index]
        self.refresh()
