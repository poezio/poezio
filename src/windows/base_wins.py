"""
Define the base window object and the constants/"globals" used
by the file of this module.

A window is a little part of the screen, for example the input window,
the text window, the roster window, etc.
A Tab (see the src/tabs module) is composed of multiple Windows
"""

import logging
log = logging.getLogger(__name__)

import collections
import curses
import string

import core
import singleton
from theming import to_curses_attr, read_tuple

FORMAT_CHAR = '\x19'
# These are non-printable chars, so they should never appear in the input,
# I guess. But maybe we can find better chars that are even less risky.
format_chars = ['\x0E', '\x0F', '\x10', '\x11', '\x12', '\x13',
                '\x14', '\x15', '\x16', '\x17', '\x18']

# different colors allowed in the input
allowed_color_digits = ('0', '1', '2', '3', '4', '5', '6', '7')

# msg is a reference to the corresponding Message tuple. text_start and
# text_end are the position delimiting the text in this line.
Line = collections.namedtuple('Line', 'msg start_pos end_pos prepend')

LINES_NB_LIMIT = 4096

class DummyWin(object):
    def __getattribute__(self, name):
        if name != '__bool__':
            return lambda *args, **kwargs: (0, 0)
        else:
            return object.__getattribute__(self, name)

    def __bool__(self):
        return False

class Win(object):
    _win_core = None
    _tab_win = None
    def __init__(self):
        self._win = None
        self.height, self.width = 0, 0

    def _resize(self, height, width, y, x):
        if height == 0 or width == 0:
            self.height, self.width = height, width
            return
        self.height, self.width, self.x, self.y = height, width, x, y
        try:
            self._win = Win._tab_win.derwin(height, width, y, x)
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
            self._win.move(0, 0)

    def addstr_colored(self, text, y=None, x=None):
        """
        Write a string on the window, setting the
        attributes as they are in the string.
        For example:
        \x19bhello → hello in bold
        \x191}Bonj\x192}our → 'Bonj' in red and 'our' in green
        next_attr_char is the \x19 delimiter
        attr_char is the char following it, it can be
        one of 'u', 'b', 'c[0-9]'
        """
        if y is not None and x is not None:
            self.move(y, x)
        next_attr_char = text.find(FORMAT_CHAR)
        while next_attr_char != -1 and text:
            if next_attr_char + 1 < len(text):
                attr_char = text[next_attr_char+1].lower()
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
            if (attr_char in string.digits or attr_char == '-') and attr_char != '':
                color_str = text[next_attr_char+1:text.find('}', next_attr_char)]
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
                elif color_str:
                    self._win.attron(to_curses_attr((int(color_str), -1)))
                text = text[next_attr_char+len(color_str)+2:]
            else:
                text = text[next_attr_char+2:]
            next_attr_char = text.find(FORMAT_CHAR)
        self.addstr(text)

    def finish_line(self, color=None):
        """
        Write colored spaces until the end of line
        """
        (y, x) = self._win.getyx()
        size = self.width - x
        if color:
            self.addnstr(' '*size, size, to_curses_attr(color))
        else:
            self.addnstr(' '*size, size)

    @property
    def core(self):
        if not Win._win_core:
            Win._win_core = singleton.Singleton(core.Core)
        return Win._win_core

