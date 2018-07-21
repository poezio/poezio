"""
Define the base window object and the constants/"globals" used
by the file of this module.

A window is a little part of the screen, for example the input window,
the text window, the roster window, etc.
A Tab (see the poezio.tabs module) is composed of multiple Windows
"""

TAB_WIN = None

import logging
log = logging.getLogger(__name__)

import curses
import string

from poezio.theming import to_curses_attr, read_tuple

FORMAT_CHAR = '\x19'
# These are non-printable chars, so they should never appear in the input,
# I guess. But maybe we can find better chars that are even less risky.
format_chars = '\x0E\x0F\x10\x11\x12\x13\x14\x15\x16\x17\x18\x1A'


class DummyWin:
    def __getattribute__(self, name):
        if name != '__bool__':
            return lambda *args, **kwargs: (0, 0)
        else:
            return object.__getattribute__(self, name)

    def __bool__(self):
        return False


class Win:
    def __init__(self):
        self._win = None
        self.height, self.width = 0, 0

    def _resize(self, height, width, y, x):
        if height == 0 or width == 0:
            self.height, self.width = height, width
            return
        self.height, self.width, self.x, self.y = height, width, x, y
        try:
            self._win = TAB_WIN.derwin(height, width, y, x)
        except:
            log.debug('DEBUG: mvwin returned ERR. Please investigate')
            if self._win is None:
                self._win = DummyWin()

    def resize(self, height, width, y, x):
        """
        Override if something has to be done on resize
        """
        self._resize(height, width, y, x)

    def _refresh(self):
        self._win.noutrefresh()

    def addnstr(self, *args):
        """
        Safe call to addnstr
        """
        try:
            self._win.addnstr(*args)
        except:
            # this actually mostly returns ERR, but works.
            # more specifically, when the added string reaches the end
            # of the screen.
            pass

    def addstr(self, *args):
        """
        Safe call to addstr
        """
        try:
            self._win.addstr(*args)
        except:
            pass

    def move(self, y, x):
        try:
            self._win.move(y, x)
        except:
            pass

    def addstr_colored(self, text, y=None, x=None):
        """
        Write a string on the window, setting the
        attributes as they are in the string.
        For example:
        \x19bhello → hello in bold
        \x191}Bonj\x192}our → 'Bonj' in red and 'our' in green
        next_attr_char is the \x19 delimiter
        attr_char is the char following it, it can be
        one of 'u', 'b', 'i', 'c[0-9]'
        """
        if y is not None and x is not None:
            self.move(y, x)
        next_attr_char = text.find(FORMAT_CHAR)
        attr_italic = curses.A_ITALIC if hasattr(
            curses, 'A_ITALIC') else curses.A_REVERSE
        while next_attr_char != -1 and text:
            if next_attr_char + 1 < len(text):
                attr_char = text[next_attr_char + 1].lower()
            else:
                attr_char = str()
            if next_attr_char != 0:
                self.addstr(text[:next_attr_char])
            if attr_char == 'o':
                self._win.attrset(0)
            elif attr_char == 'u':
                self._win.attron(curses.A_UNDERLINE)
            elif attr_char == 'b':
                self._win.attron(curses.A_BOLD)
            elif attr_char == 'i':
                self._win.attron(attr_italic)
            if (attr_char in string.digits
                    or attr_char == '-') and attr_char != '':
                color_str = text[next_attr_char +
                                 1:text.find('}', next_attr_char)]
                if ',' in color_str:
                    tup, char = read_tuple(color_str)
                    self._win.attron(to_curses_attr(tup))
                    if char:
                        if char == 'o':
                            self._win.attrset(0)
                        elif char == 'u':
                            self._win.attron(curses.A_UNDERLINE)
                        elif char == 'b':
                            self._win.attron(curses.A_BOLD)
                        elif char == 'i':
                            self._win.attron(attr_italic)
                    else:
                        # this will reset previous bold/uderline sequences if any was used
                        self._win.attroff(curses.A_UNDERLINE)
                        self._win.attroff(curses.A_BOLD)
                elif color_str:
                    self._win.attron(to_curses_attr((int(color_str), -1)))
                text = text[next_attr_char + len(color_str) + 2:]
            else:
                text = text[next_attr_char + 2:]
            next_attr_char = text.find(FORMAT_CHAR)
        self.addstr(text)

    def finish_line(self, color=None):
        """
        Write colored spaces until the end of line
        """
        (y, x) = self._win.getyx()
        size = self.width - x
        if color:
            self.addnstr(' ' * size, size, to_curses_attr(color))
        else:
            self.addnstr(' ' * size, size)
