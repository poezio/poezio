"""
Classes used to replace the input in some tabs or special situations,
but which are not inputs.
"""

import logging
log = logging.getLogger(__name__)

from poezio.windows.base_wins import Win
from poezio.theming import get_theme, to_curses_attr


class HelpText(Win):
    """
    A Window just displaying a read-only message.
    Usually used to replace an Input when the tab is in
    command mode.
    """

    def __init__(self, text=''):
        Win.__init__(self)
        self.txt = text

    def refresh(self, txt=None):
        log.debug('Refresh: %s', self.__class__.__name__)
        if txt:
            self.txt = txt
        self._win.erase()
        self.addstr(0, 0, self.txt[:self.width - 1],
                    to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        self._refresh()

    def do_command(self, key, raw=False):
        return False

    def on_delete(self):
        return
