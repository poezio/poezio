# Copyright 2010-2011 Le Coz Florent <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

"""
Define the variables (colors and some other stuff) that are
used when drawing the interface (mainly colors)
"""

import curses
import glob
import imp
import os
from config import config

import logging
log = logging.getLogger(__name__)

## Define the default colors
## Do not change these colors, create a theme file instead.

# Message text color
COLOR_NORMAL_TEXT = 0
COLOR_INFORMATION_TEXT = 5
COLOR_HIGHLIGHT_NICK = 45

# User list color
COLOR_USER_VISITOR = 7
COLOR_USER_PARTICIPANT = 4
COLOR_USER_NONE = 0
COLOR_USER_MODERATOR = 1

# nickname colors
COLOR_REMOTE_USER = 5

# The character printed in color (COLOR_STATUS_*) before the nickname
# in the user list
CHAR_STATUS = ' '

# Separators
COLOR_VERTICAL_SEPARATOR = 4
COLOR_NEW_TEXT_SEPARATOR = 2
COLOR_MORE_INDICATOR = 6

# Time
COLOR_TIME_SEPARATOR = 6
COLOR_TIME_LIMITER = 0
CHAR_TIME_LEFT = ''
CHAR_TIME_RIGHT = ''
COLOR_TIME_NUMBERS = 0

# Tabs
COLOR_TAB_NORMAL = 42
COLOR_TAB_CURRENT = 56
COLOR_TAB_NEW_MESSAGE = 49
COLOR_TAB_HIGHLIGHT = 21
COLOR_TAB_PRIVATE = 28

# Nickname colors
LIST_COLOR_NICKNAMES = [
    1, 2, 3, 4, 5, 6, -2, -4, -5, -6
    ]
COLOR_OWN_NICK = 7

# Status color
COLOR_STATUS_XA = 49
COLOR_STATUS_NONE = 0
COLOR_STATUS_DND = 21
COLOR_STATUS_AWAY = 35
COLOR_STATUS_CHAT = 28
COLOR_STATUS_UNAVAILABLE = 57
COLOR_STATUS_ONLINE = 41

# Bars
COLOR_INFORMATION_BAR = 42
COLOR_TOPIC_BAR = 42
COLOR_PRIVATE_ROOM_BAR = 28
COLOR_SCROLLABLE_NUMBER = -39
COLOR_SELECTED_ROW = 42
COLOR_PRIVATE_NAME = 42
COLOR_CONVERSATION_NAME = 42
COLOR_GROUPCHAT_NAME = 42
COLOR_COLUMN_HEADER = 36

# Strings for special messages (like join, quit, nick change, etc)
# Special messages
CHAR_JOIN = '---->'
CHAR_QUIT = '<----'
CHAR_KICK = '-!-'

COLOR_JOIN_CHAR = 4
COLOR_QUIT_CHAR = 1
COLOR_KICK_CHAR = 1

# words between ()
COLOR_CURLYBRACKETED_WORD = 4
# words between {}
COLOR_ACCOLADE_WORD = 6
# words between []
COLOR_BRACKETED_WORD = 3

def init_colors():
    """
    Initilization of all the available ncurses colors
    limit the number of colors to 64 (because some terminals
    don't handle more than that), by removing some useless colors
    like 'black on black', etc.
    """
    curses.start_color()
    curses.use_default_colors()
    cpt = 0
    for i in range(-1, 7):
        for y in range(0, 8):
            if y == i:
                continue
            curses.init_pair(cpt, y, i)
            cpt += 1
    for y in range(0, 7):
        # init the default fg on others bg at last
        curses.init_pair(cpt, -1, y)
        cpt += 1
    # Have the default color be default fg on default bg
    reload_theme()

def reload_theme():
    themes_dir = config.get('themes_dir', '')
    themes_dir = themes_dir or\
        os.path.join(os.environ.get('XDG_DATA_HOME') or\
                         os.path.join(os.environ.get('HOME'), '.local', 'share'),
                     'poezio', 'themes')
    try:
        os.makedirs(themes_dir)
    except OSError:
        pass
    theme_name = config.get('theme', '')
    if not theme_name:
        return
    try:
        theme = imp.load_source('theme', os.path.join(themes_dir, theme_name))
    except:                     # TODO warning: theme not found
        return
    for var in dir(theme):
        if var.startswith('COLOR_') or var.startswith('CHAR_') or var.startswith('LIST_'):
            globals()[var] = getattr(theme, var)

if __name__ == '__main__':
    """
    Launch 'python theme.py' to see the list of all the available colors
    in your terminal
    """
    s = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    init_colors()
    for i in range(64):
        s.attron(curses.color_pair(i) | curses.A_BOLD)
        s.addstr(str(curses.color_pair(i) | curses.A_BOLD))
        s.attroff(curses.color_pair(i) | curses.A_BOLD)
        s.addstr(' ')
    s.addstr('\n')
    for i in range(64):
        s.attron(curses.color_pair(i))
        s.addstr(str(i))
        s.attroff(curses.color_pair(i))
        s.addstr(' ')

    s.refresh()
    s.getch()
    s.endwin()
