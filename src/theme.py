# -*- coding:utf-8 -*-
#
# Copyright 2010 Le Coz Florent <louizatakk@fedoraproject.org>
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
import inspect
import imp
from config import config

## Define the default colors
## Do not change these colors, create a theme file instead.

# Message text color
COLOR_NORMAL_TEXT = 0
COLOR_INFORMATION_TEXT = 76
COLOR_HIGHLIGHT_TEXT = 77

# User list color
COLOR_USER_VISITOR = 78
COLOR_USER_PARTICIPANT = 73
COLOR_USER_NONE = 80
COLOR_USER_MODERATOR = 77

# Separators
COLOR_VERTICAL_SEPARATOR = 73
COLOR_NEW_TEXT_SEPARATOR = 75

# Time
COLOR_TIME_SEPARATOR = 79
COLOR_TIME_BRACKETS = 74
COLOR_TIME_NUMBERS = 0

# Tabs
COLOR_TAB_NORMAL = 15
COLOR_TAB_CURRENT = 24
COLOR_TAB_NEW_MESSAGE = 42
COLOR_TAB_HIGHLIGHT = 51
COLOR_TAB_PRIVATE = 33

# Nickname colors
LIST_COLOR_NICKNAMES = [
    73, 74, 75, 76, 77, 78, 79
    ]
COLOR_OWN_NICK = 72

# Status color
COLOR_STATUS_XA = 40
COLOR_STATUS_NONE = 0
COLOR_STATUS_DND = 50
COLOR_STATUS_AWAY = 70
COLOR_STATUS_CHAT = 30

# Bars
COLOR_INFORMATION_BAR = 15
COLOR_TOPIC_BAR = 15
COLOR_PRIVATE_ROOM_BAR = 33
COLOR_SCROLLABLE_NUMBER = 16

def init_colors():
    """
    Initilization of all the available ncurses colors
    """
    curses.start_color()
    curses.use_default_colors()
    colors_list = [
        curses.COLOR_BLACK,
        curses.COLOR_BLUE,
        curses.COLOR_CYAN,
        curses.COLOR_GREEN,
        curses.COLOR_MAGENTA,
        curses.COLOR_RED,
        curses.COLOR_WHITE,
        curses.COLOR_YELLOW,
        -1
        ]
    cpt = 0
    for i in colors_list:
        for y in colors_list:
            curses.init_pair(cpt, y, i)
            cpt += 1
    reload_theme()

def reload_theme():
    current_module = __import__(inspect.getmodulename(__file__))
    path = config.get('theme_file', '../default.theme')
    try:
        theme = imp.load_source('theme', path)
    except:
        return
    for var in dir(theme):
        if var.startswith('COLOR_'):
            globals()[var] = getattr(theme, var)

if __name__ == '__main__':
    """
    Launch 'python theme.py' to see the list of all the available colors
    in your terminal
    """
    s = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    for i in xrange(80):
        s.attron(curses.color_pair(i))
        s.addstr(str(i))
        s.attroff(curses.color_pair(i))
        s.addstr(' ')
    s.refresh()
    s.getch()
    s.endwin()



