"""
Windows relevant for the listing tabs, not much else
"""

import logging
import curses

from typing import Dict, List, Optional

from poezio.windows.base_wins import Win
from poezio.theming import to_curses_attr, get_theme

log = logging.getLogger(__name__)


class ListWin(Win):
    """
    A list (with no depth, so not for the roster) that can be
    scrolled up and down, with one selected line at a time
    """

    __slots__ = ('_columns', '_columns_sizes', 'sorted_by', 'lines',
                 '_selected_row', '_starting_pos')

    def __init__(self, columns: Dict[str, int], with_headers: bool = True) -> None:
        Win.__init__(self)
        self._columns = columns  # type: Dict[str, int]
        self._columns_sizes = {}  # type: Dict[str, int]
        self.sorted_by = (None, None)  # for example: ('name', '↑')
        self.lines = []  # type: List[str]
        self._selected_row = 0
        self._starting_pos = 0  # The column number from which we start the refresh

    @property
    def pos(self) -> int:
        if len(self.lines) > self.height:
            return len(self.lines)
        else:
            return 0

    def empty(self) -> None:
        """
        empty the list and reset some important values as well
        """
        self.lines = []
        self._selected_row = 0
        self._starting_pos = 0

    def resize_columns(self, dic: Dict[str, int]) -> None:
        """
        Resize the width of the columns
        """
        self._columns_sizes = dic

    def sort_by_column(self, col_name: str, asc: bool = True) -> None:
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

    def add_lines(self, lines: List[str]) -> None:
        """
        Append some lines at the end of the list
        """
        if not lines:
            return
        self.lines.extend(lines)

    def set_lines(self, lines: List[str]) -> None:
        """
        Set the lines to another list
        """
        if not lines:
            return
        self.lines = lines

    def get_selected_row(self) -> Optional[str]:
        """
        Return the tuple representing the selected row
        """
        if self._selected_row is not None and self.lines:
            return self.lines[self._selected_row]
        return None

    def refresh(self) -> None:
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        lines = self.lines[self._starting_pos:self._starting_pos + self.height]
        color = to_curses_attr(get_theme().COLOR_INFORMATION_BAR)
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
                    self.addstr(y, x, txt[:size], color)
                else:
                    self.addstr(y, x, txt[:size])
                x += size
        self._refresh()

    def move_cursor_down(self) -> bool:
        """
        Move the cursor Down
        """
        if not self.lines:
            return False
        if self._selected_row < len(self.lines) - 1:
            self._selected_row += 1
        while self._selected_row >= self._starting_pos + self.height:
            self._starting_pos += self.height // 2
        if self._starting_pos < 0:
            self._starting_pos = 0
        return True

    def move_cursor_up(self) -> bool:
        """
        Move the cursor Up
        """
        if not self.lines:
            return False
        if self._selected_row > 0:
            self._selected_row -= 1
        while self._selected_row < self._starting_pos:
            self._starting_pos -= self.height // 2
        return True

    def scroll_down(self) -> bool:
        if not self.lines:
            return False
        self._selected_row += self.height
        if self._selected_row > len(self.lines) - 1:
            self._selected_row = len(self.lines) - 1
        while self._selected_row >= self._starting_pos + self.height:
            self._starting_pos += self.height // 2
        if self._starting_pos < 0:
            self._starting_pos = 0
        return True

    def scroll_up(self) -> bool:
        if not self.lines:
            return False
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

    __slots__ = ('_columns', '_columns_sizes', '_column_sel', '_column_order',
                 '_column_order_asc')

    def __init__(self, columns: List[str]) -> None:
        Win.__init__(self)
        self._columns = columns
        self._columns_sizes = {}  # type: Dict[str, int]
        self._column_sel = ''
        self._column_order = ''
        self._column_order_asc = False

    def resize_columns(self, dic) -> None:
        self._columns_sizes = dic

    def get_columns(self) -> List[str]:
        return self._columns

    def refresh(self) -> None:
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        x = 0
        theme = get_theme()
        for col in self._columns:
            txt = col
            if col in self._column_order:
                if self._column_order_asc:
                    txt += theme.CHAR_COLUMN_ASC
                else:
                    txt += theme.CHAR_COLUMN_DESC
            #⇓⇑↑↓⇧⇩▲▼
            size = self._columns_sizes[col]
            txt += ' ' * (size - len(txt))
            if col in self._column_sel:
                self.addstr(
                    0, x, txt,
                    to_curses_attr(theme.COLOR_COLUMN_HEADER_SEL))
            else:
                self.addstr(0, x, txt,
                            to_curses_attr(theme.COLOR_COLUMN_HEADER))
            x += size
        self._refresh()

    def sel_column(self, dic) -> None:
        self._column_sel = dic

    def get_sel_column(self):
        return self._column_sel

    def set_order(self, order) -> None:
        self._column_order = self._column_sel
        self._column_order_asc = order

    def get_order(self) -> bool:
        if self._column_sel == self._column_order:
            return self._column_order_asc
        else:
            return False

    def sel_column_left(self) -> None:
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

    def sel_column_right(self) -> None:
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
