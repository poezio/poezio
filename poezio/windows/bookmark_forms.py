"""
Windows used inthe bookmarkstab
"""
import curses

from poezio.windows import base_wins
from poezio.windows.base_wins import Win
from poezio.windows.inputs import Input
from poezio.windows.data_forms import FieldInput, FieldInputMixin
from poezio.theming import to_curses_attr, get_theme
from poezio.common import safeJID


class BookmarkNameInput(FieldInput, Input):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        Input.__init__(self)
        self.text = field.name
        self.pos = len(self.text)
        self.color = get_theme().COLOR_NORMAL_TEXT

    def save(self):
        self._field.name = self.get_text()

    def get_help_message(self):
        return 'Edit the text'


class BookmarkJIDInput(FieldInput, Input):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        Input.__init__(self)
        jid = safeJID(field.jid)
        jid.resource = field.nick or None
        self.text = jid.full
        self.pos = len(self.text)
        self.color = get_theme().COLOR_NORMAL_TEXT

    def save(self):
        jid = safeJID(self.get_text())
        self._field.jid = jid.bare
        self._field.nick = jid.resource

    def get_help_message(self):
        return 'Edit the text'


class BookmarkMethodInput(FieldInputMixin):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        Win.__init__(self)
        self.options = ('local', 'remote')
        # val_pos is the position of the currently selected option
        self.val_pos = self.options.index(field.method)

    def do_command(self, key):
        if key == 'KEY_LEFT':
            if self.val_pos > 0:
                self.val_pos -= 1
        elif key == 'KEY_RIGHT':
            if self.val_pos < len(self.options) - 1:
                self.val_pos += 1
        else:
            return
        self.refresh()

    def refresh(self):
        self._win.erase()
        self._win.attron(to_curses_attr(self.color))
        self.addnstr(0, 0, ' ' * self.width, self.width)
        if self.val_pos > 0:
            self.addstr(0, 0, '←')
        if self.val_pos < len(self.options) - 1:
            self.addstr(0, self.width - 1, '→')
        if self.options:
            option = self.options[self.val_pos]
            self.addstr(0, self.width // 2 - len(option) // 2, option)
        self._win.attroff(to_curses_attr(self.color))
        self._refresh()

    def save(self):
        self._field.method = self.options[self.val_pos]

    def get_help_message(self):
        return '←, →: Select a value amongst the others'


class BookmarkPasswordInput(FieldInput, Input):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        Input.__init__(self)
        self.text = field.password or ''
        self.pos = len(self.text)
        self.color = get_theme().COLOR_NORMAL_TEXT

    def rewrite_text(self):
        self._win.erase()
        if self.color:
            self._win.attron(to_curses_attr(self.color))
        self.addstr(
            '*' * len(self.text[self.view_pos:self.view_pos + self.width - 1]))
        if self.color:
            (y, x) = self._win.getyx()
            size = self.width - x
            self.addnstr(' ' * size, size, to_curses_attr(self.color))
        self.addstr(0, self.pos, '')
        if self.color:
            self._win.attroff(to_curses_attr(self.color))
        self._refresh()

    def save(self):
        self._field.password = self.get_text() or None

    def get_help_message(self):
        return 'Edit the secret text'


class BookmarkAutojoinWin(FieldInputMixin):
    def __init__(self, field):
        FieldInput.__init__(self, field)
        Win.__init__(self)
        self.last_key = 'KEY_RIGHT'
        self.value = field.autojoin

    def do_command(self, key):
        if key == 'KEY_LEFT' or key == 'KEY_RIGHT':
            self.value = not self.value
            self.last_key = key
        self.refresh()

    def refresh(self):
        self._win.erase()
        self._win.attron(to_curses_attr(self.color))
        format_string = '←{:^%s}→' % 7
        inp = format_string.format(repr(self.value))
        self.addstr(0, 0, inp)
        if self.last_key == 'KEY_RIGHT':
            self.move(0, 8)
        else:
            self.move(0, 0)
        self._win.attroff(to_curses_attr(self.color))
        self._refresh()

    def save(self):
        self._field.autojoin = self.value

    def get_help_message(self):
        return '← and →: change the value between True and False'


class BookmarksWin(Win):
    def __init__(self, bookmarks, height, width, y, x):
        self._win = base_wins.TAB_WIN.derwin(height, width, y, x)
        self.scroll_pos = 0
        self._current_input = 0
        self.current_horizontal_input = 0
        self._bookmarks = list(bookmarks)
        self.lines = []
        for bookmark in sorted(self._bookmarks, key=lambda x: x.jid):
            self.lines.append((BookmarkNameInput(bookmark),
                               BookmarkJIDInput(bookmark),
                               BookmarkPasswordInput(bookmark),
                               BookmarkAutojoinWin(bookmark),
                               BookmarkMethodInput(bookmark)))

    @property
    def current_input(self):
        return self._current_input

    @current_input.setter
    def current_input(self, value):
        if 0 <= self._current_input < len(self.lines):
            if 0 <= value < len(self.lines):
                self.lines[self._current_input][
                    self.current_horizontal_input].set_color(
                        get_theme().COLOR_NORMAL_TEXT)
                self._current_input = value
        else:
            self._current_input = 0

    def add_bookmark(self, bookmark):
        self.lines.append((BookmarkNameInput(bookmark),
                           BookmarkJIDInput(bookmark),
                           BookmarkPasswordInput(bookmark),
                           BookmarkAutojoinWin(bookmark),
                           BookmarkMethodInput(bookmark)))
        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_NORMAL_TEXT)
        self.current_horizontal_input = 0
        self.current_input = len(self.lines) - 1
        if self.current_input - self.scroll_pos > self.height - 1:
            self.scroll_pos = self.current_input - self.height + 1
        self.refresh()

    def del_current_bookmark(self):
        if self.lines:
            bm = self.lines[self.current_input][0]._field
            to_delete = self.current_input
            self.current_input -= 1
            del self.lines[to_delete]
            if self.scroll_pos:
                self.scroll_pos -= 1
            self.refresh()
            return bm

    def resize(self, height, width, y, x):
        self.height = height
        self.width = width
        self._win = base_wins.TAB_WIN.derwin(height, width, y, x)
        # Adjust the scroll position, if resizing made the window too small
        # for the cursor to be visible
        while self.current_input - self.scroll_pos > self.height - 1:
            self.scroll_pos += 1

    def go_to_next_line_input(self):
        if not self.lines:
            return
        if self.current_input == len(self.lines) - 1:
            return
        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_NORMAL_TEXT)
        # Adjust the scroll position if the current_input would be outside
        # of the visible area
        if self.current_input + 1 - self.scroll_pos > self.height - 1:
            self.current_input += 1
            self.scroll_pos += 1
            self.refresh()
        else:
            self.current_input += 1
            self.lines[self.current_input][
                self.current_horizontal_input].set_color(
                    get_theme().COLOR_SELECTED_ROW)

    def go_to_previous_line_input(self):
        if not self.lines:
            return
        if self.current_input == 0:
            return
        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_NORMAL_TEXT)
        self.current_input -= 1
        # Adjust the scroll position if the current_input would be outside
        # of the visible area
        if self.current_input < self.scroll_pos:
            self.scroll_pos = self.current_input
            self.refresh()
        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_SELECTED_ROW)

    def go_to_next_horizontal_input(self):
        if not self.lines:
            return
        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_NORMAL_TEXT)
        self.current_horizontal_input += 1
        if self.current_horizontal_input > 3:
            self.current_horizontal_input = 0
        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_SELECTED_ROW)

    def go_to_next_page(self):
        if not self.lines:
            return

        if self.current_input == len(self.lines) - 1:
            return

        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_NORMAL_TEXT)
        inc = min(self.height, len(self.lines) - self.current_input - 1)

        if self.current_input + inc - self.scroll_pos > self.height - 1:
            self.current_input += inc
            self.scroll_pos += inc
            self.refresh()
        else:
            self.current_input += inc
            self.lines[self.current_input][
                self.current_horizontal_input].set_color(
                    get_theme().COLOR_SELECTED_ROW)
        return True

    def go_to_previous_page(self):
        if not self.lines:
            return

        if self.current_input == 0:
            return

        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_NORMAL_TEXT)

        dec = min(self.height, self.current_input)
        self.current_input -= dec
        # Adjust the scroll position if the current_input would be outside
        # of the visible area
        if self.current_input < self.scroll_pos:
            self.scroll_pos = self.current_input
            self.refresh()
        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_SELECTED_ROW)
        return True

    def go_to_previous_horizontal_input(self):
        if not self.lines:
            return
        if self.current_horizontal_input == 0:
            return
        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_NORMAL_TEXT)
        self.current_horizontal_input -= 1
        self.lines[self.current_input][
            self.current_horizontal_input].set_color(
                get_theme().COLOR_SELECTED_ROW)

    def on_input(self, key):
        if not self.lines:
            return
        self.lines[self.current_input][
            self.current_horizontal_input].do_command(key)

    def refresh(self):
        # store the cursor status
        self._win.erase()
        y = -self.scroll_pos
        for i in range(len(self.lines)):
            self.lines[i][0].resize(1, self.width // 4, y + 1, 0)
            self.lines[i][1].resize(1, self.width // 4, y + 1, self.width // 4)
            self.lines[i][2].resize(1, self.width // 6, y + 1,
                                    3 * self.width // 6)
            self.lines[i][3].resize(1, self.width // 6, y + 1,
                                    4 * self.width // 6)
            self.lines[i][4].resize(1, self.width // 6, y + 1,
                                    5 * self.width // 6)
            y += 1
        self._refresh()
        for i, inp in enumerate(self.lines):
            if i < self.scroll_pos:
                continue
            if i >= self.height + self.scroll_pos:
                break
            for j in range(4):
                inp[j].refresh()

        if self.lines and self.current_input < self.height - 1:
            self.lines[self.current_input][
                self.current_horizontal_input].set_color(
                    get_theme().COLOR_SELECTED_ROW)
            self.lines[self.current_input][
                self.current_horizontal_input].refresh()
        if not self.lines:
            curses.curs_set(0)
        else:
            curses.curs_set(1)

    def refresh_current_input(self):
        if self.lines:
            self.lines[self.current_input][
                self.current_horizontal_input].refresh()

    def save(self):
        for line in self.lines:
            for item in line:
                item.save()
