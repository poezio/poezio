"""
Windows specific to a MUC
"""

import logging
log = logging.getLogger(__name__)

import curses

from poezio.windows.base_wins import Win

from poezio import poopt
from poezio.config import config
from poezio.theming import to_curses_attr, get_theme


def userlist_to_cache(userlist):
    result = []
    for user in userlist:
        result.append((user.nick, user.status, user.chatstate,
                       user.affiliation, user.role))
    return result


class UserList(Win):
    def __init__(self):
        Win.__init__(self)
        self.pos = 0
        self.cache = []

    def scroll_up(self):
        self.pos += self.height - 1
        return True

    def scroll_down(self):
        pos = self.pos
        self.pos -= self.height - 1
        if self.pos < 0:
            self.pos = 0
        return self.pos != pos

    def draw_plus(self, y):
        self.addstr(y, self.width - 2, '++',
                    to_curses_attr(get_theme().COLOR_MORE_INDICATOR))

    def refresh_if_changed(self, users):
        old = self.cache
        new = userlist_to_cache(users[self.pos:self.pos + self.height])
        if len(old) != len(new):
            self.cache = new
            self.refresh(users)
            return
        for a, b in zip(old, new):
            if a != b:
                self.cache = new
                self.refresh(users)
                return

    def refresh(self, users):
        log.debug('Refresh: %s', self.__class__.__name__)
        if config.get('hide_user_list'):
            return  # do not refresh if this win is hidden.
        if len(users) < self.height:
            self.pos = 0
        elif self.pos >= len(users) - self.height and self.pos != 0:
            self.pos = len(users) - self.height
        self._win.erase()
        asc_sort = (config.get('user_list_sort').lower() == 'asc')
        if asc_sort:
            y, _ = self._win.getmaxyx()
            y -= 1
        else:
            y = 0

        for user in users[self.pos:self.pos + self.height]:
            self.draw_role_affiliation(y, user)
            self.draw_status_chatstate(y, user)
            self.addstr(y, 2, poopt.cut_by_columns(user.nick, self.width - 2),
                        to_curses_attr(user.color))
            if asc_sort:
                y -= 1
            else:
                y += 1
            if y == self.height:
                break
        # draw indicators of position in the list
        if self.pos > 0:
            if asc_sort:
                self.draw_plus(self.height - 1)
            else:
                self.draw_plus(0)
        if self.pos + self.height < len(users):
            if asc_sort:
                self.draw_plus(0)
            else:
                self.draw_plus(self.height - 1)
        self._refresh()

    def draw_role_affiliation(self, y, user):
        theme = get_theme()
        color = theme.color_role(user.role)
        symbol = theme.char_affiliation(user.affiliation)
        self.addstr(y, 1, symbol, to_curses_attr(color))

    def draw_status_chatstate(self, y, user):
        show_col = get_theme().color_show(user.show)
        if user.chatstate == 'composing':
            char = get_theme().CHAR_CHATSTATE_COMPOSING
        elif user.chatstate == 'active':
            char = get_theme().CHAR_CHATSTATE_ACTIVE
        elif user.chatstate == 'paused':
            char = get_theme().CHAR_CHATSTATE_PAUSED
        else:
            char = get_theme().CHAR_STATUS
        self.addstr(y, 0, char, to_curses_attr(show_col))

    def resize(self, height, width, y, x):
        separator = to_curses_attr(get_theme().COLOR_VERTICAL_SEPARATOR)
        self._resize(height, width, y, x)
        self._win.attron(separator)
        self._win.vline(0, 0, curses.ACS_VLINE, self.height)
        self._win.attroff(separator)


class Topic(Win):
    def __init__(self):
        Win.__init__(self)
        self._message = ''

    def refresh(self, topic=None):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        if topic:
            msg = topic[:self.width - 1]
        else:
            msg = self._message[:self.width - 1]
        self.addstr(0, 0, msg, to_curses_attr(get_theme().COLOR_TOPIC_BAR))
        _, x = self._win.getyx()
        remaining_size = self.width - x
        if remaining_size:
            self.addnstr(' ' * remaining_size, remaining_size,
                         to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self._refresh()

    def set_message(self, message):
        self._message = message
