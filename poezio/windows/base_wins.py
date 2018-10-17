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

from typing import Optional, Tuple

from poezio import libpoezio

FORMAT_CHAR = '\x19'
# These are non-printable chars, so they should never appear in the input,
# I guess. But maybe we can find better chars that are even less risky.
format_chars = '\x0E\x0F\x10\x11\x12\x13\x14\x15\x16\x17\x18\x1A'


class DummyWin:
    def __getattribute__(self, name: str):
        if name != '__bool__':
            return lambda *args, **kwargs: (0, 0)
        else:
            return object.__getattribute__(self, name)

    def __bool__(self) -> bool:
        return False


class Win:
    def __init__(self) -> None:
        self._win = None
        self.height, self.width = 0, 0

    def _resize(self, height: int, width: int, y: int, x: int) -> None:
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

    def resize(self, height: int, width: int, y: int, x: int) -> None:
        """
        Override if something has to be done on resize
        """
        self._resize(height, width, y, x)

    def _refresh(self) -> None:
        self._win.noutrefresh()

    def addnstr(self, *args) -> None:
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

    def addstr(self, *args) -> None:
        """
        Safe call to addstr
        """
        try:
            self._win.addstr(*args)
        except:
            pass

    def move(self, y: int, x: int) -> None:
        try:
            self._win.move(y, x)
        except:
            pass

    def addstr_colored(self, text: str, y: Optional[int] = None, x: Optional[int] = None) -> None:
        """
        Write a string on the window, setting the
        attributes as they are in the string.
        For example:
        \x19bhello → hello in bold
        \x191}Bonj\x192}our → 'Bonj' in red and 'our' in green
        """
        if y is not None and x is not None:
            self.move(y, x)
        # XXX: the cancel attribute is a hack for nom’s Incomplete issue.
        libpoezio.printw(self._win, text + '\x19o')

    def finish_line(self, color: Optional[Tuple] = None) -> None:
        """
        Write colored spaces until the end of line
        """
        libpoezio.finish_line(self._win, self.width, color);
