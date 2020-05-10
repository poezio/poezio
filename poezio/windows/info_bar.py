"""
Module defining the global info bar

This window is the one listing the current opened tabs in poezio.
The GlobalInfoBar can be either horizontal or vertical
(VerticalGlobalInfoBar).
"""
import logging
log = logging.getLogger(__name__)

import curses

from poezio.config import config
from poezio.windows.base_wins import Win
from poezio.theming import get_theme, to_curses_attr
from poezio.colors import ccg_text_to_color


class GlobalInfoBar(Win):
    __slots__ = ('core')

    def __init__(self, core) -> None:
        Win.__init__(self)
        self.core = core

    def refresh(self) -> None:
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        theme = get_theme()
        self.addstr(0, 0, "[",
                    to_curses_attr(theme.COLOR_INFORMATION_BAR))

        show_names = config.get('show_tab_names')
        show_nums = config.get('show_tab_numbers')
        use_nicks = config.get('use_tab_nicks')
        show_inactive = config.get('show_inactive_tabs')
        autocolor_tab_names = config.get('autocolor_tab_names')

        for nb, tab in enumerate(self.core.tabs):
            if not tab:
                continue
            color = tab.color
            if not show_inactive and color is theme.COLOR_TAB_NORMAL:
                continue
            if autocolor_tab_names:
                # TODO: in case of private MUC conversations, we should try to
                # get hold of more information to make the colour the same as
                # the nickname colour in the MUC.
                fgcolor, bgcolor, *flags = color
                # this is fugly, but I’m not sure how to improve it... since
                # apparently the state is only kept in the color -.-
                if (color == theme.COLOR_TAB_HIGHLIGHT or
                        color == theme.COLOR_TAB_PRIVATE):
                    fgcolor = ccg_text_to_color(theme.ccg_palette, tab.name)
                    bgcolor = -1
                    flags = theme.MODE_TAB_IMPORTANT
                elif color == theme.COLOR_TAB_NEW_MESSAGE:
                    fgcolor = ccg_text_to_color(theme.ccg_palette, tab.name)
                    bgcolor = -1
                    flags = theme.MODE_TAB_NORMAL

                color = (fgcolor, bgcolor) + tuple(flags)
            try:
                if show_nums or not show_names:
                    self.addstr("%s" % str(nb), to_curses_attr(color))
                    if show_names:
                        self.addstr(' ', to_curses_attr(color))
                if show_names:
                    if use_nicks:
                        self.addstr("%s" % str(tab.get_nick()),
                                    to_curses_attr(color))
                    else:
                        self.addstr("%s" % tab.name, to_curses_attr(color))
                self.addstr("|",
                            to_curses_attr(theme.COLOR_INFORMATION_BAR))
            except:  # end of line
                break
        (y, x) = self._win.getyx()
        self.addstr(y, x - 1, '] ',
                    to_curses_attr(theme.COLOR_INFORMATION_BAR))
        (y, x) = self._win.getyx()
        remaining_size = self.width - x
        self.addnstr(' ' * remaining_size, remaining_size,
                     to_curses_attr(theme.COLOR_INFORMATION_BAR))
        self._refresh()


class VerticalGlobalInfoBar(Win):
    __slots__ = ('core')

    def __init__(self, core, scr) -> None:
        Win.__init__(self)
        self.core = core
        self._win = scr

    def refresh(self) -> None:
        height, width = self._win.getmaxyx()
        self._win.erase()
        sorted_tabs = [tab for tab in self.core.tabs if tab]
        theme = get_theme()
        if not config.get('show_inactive_tabs'):
            sorted_tabs = [
                tab for tab in sorted_tabs
                if tab.vertical_color != theme.COLOR_VERTICAL_TAB_NORMAL
            ]
        nb_tabs = len(sorted_tabs)
        use_nicks = config.get('use_tab_nicks')
        if nb_tabs >= height:
            for y, tab in enumerate(sorted_tabs):
                if tab.vertical_color == theme.COLOR_VERTICAL_TAB_CURRENT:
                    pos = y
                    break
            # center the current tab as much as possible
            if pos < height // 2:
                sorted_tabs = sorted_tabs[:height]
            elif nb_tabs - pos <= height // 2:
                sorted_tabs = sorted_tabs[-height:]
            else:
                sorted_tabs = sorted_tabs[pos - height // 2:pos + height // 2]
        asc_sort = (config.get('vertical_tab_list_sort') == 'asc')
        for y, tab in enumerate(sorted_tabs):
            color = tab.vertical_color
            if asc_sort:
                y = height - y - 1
            self.addstr(y, 0, "%2d" % tab.nb,
                        to_curses_attr(theme.COLOR_VERTICAL_TAB_NUMBER))
            self.addstr('.')
            if use_nicks:
                self.addnstr("%s" % tab.get_nick(), width - 4,
                             to_curses_attr(color))
            else:
                self.addnstr("%s" % tab.name, width - 4, to_curses_attr(color))
        separator = to_curses_attr(theme.COLOR_VERTICAL_SEPARATOR)
        self._win.attron(separator)
        self._win.vline(0, width - 1, curses.ACS_VLINE, height)
        self._win.attroff(separator)
        self._refresh()
