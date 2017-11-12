"""
Wins that don’t fit any category
"""

import logging
log = logging.getLogger(__name__)

import curses

from poezio.windows.base_wins import Win
from poezio.theming import get_theme, to_curses_attr


class VerticalSeparator(Win):
    """
    Just a one-column window, with just a line in it, that is
    refreshed only on resize, but never on refresh, for efficiency
    """

    def rewrite_line(self):
        self._win.vline(0, 0, curses.ACS_VLINE, self.height,
                        to_curses_attr(get_theme().COLOR_VERTICAL_SEPARATOR))
        self._refresh()

    def refresh(self):
        log.debug('Refresh: %s', self.__class__.__name__)
        self.rewrite_line()


class SimpleTextWin(Win):
    def __init__(self, text):
        Win.__init__(self)
        self._text = text
        self.built_lines = []

    def rebuild_text(self):
        """
        Transform the text in lines than can then be
        displayed without any calculation or anything
        at refresh() time
        It is basically called on each resize
        """
        self.built_lines = []
        for line in self._text.split('\n'):
            while len(line) >= self.width:
                limit = line[:self.width].rfind(' ')
                if limit <= 0:
                    limit = self.width
                self.built_lines.append(line[:limit])
                line = line[limit:]
            self.built_lines.append(line)

    def refresh(self):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        for y, line in enumerate(self.built_lines):
            self.addstr_colored(line, y, 0)
        self._refresh()
