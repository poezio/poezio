#!/usr/bin/python
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

from handler import Handler
import curses
from curses import textpad

import sys

class Win(object):
    def __init__(self, height, width, y, x, parent_win):
        self.height, self.width, self.x, self.y = height, width, x, y
        self.win = parent_win.subwin(height, width, y, x)

class UserList(Win):
    def __init__(self, height, width, y, x, parent_win):
        Win.__init__(self, height, width, y, x, parent_win)
        self.list = []
        for name in ["kikoo", "louiz", "mrk", "fion", "bite"]:
            self.add_user(name)
        self.win.attron(curses.color_pair(2))
        self.win.vline(0, 0, curses.ACS_VLINE, self.height)
        self.win.attroff(curses.color_pair(2))
        self.win.refresh()

    def add_user(self, name):
        """
        add an user to the list
        """
        self.win.addstr(len(self.list), 2, name)
        self.list.append(name)

class Info(Win):
    def __init__(self, height, width, y, x, parent_win):
        Win.__init__(self, height, width, y, x, parent_win)
#        self.win.bkgd(ord('p'), curses.COLOR_BLUE)

    def set_info(self, text):
        self.win.addstr(0, 0, text + " "*(self.width-len(text)-1)
                        , curses.color_pair(1))

class Tab(object):
    """
    The whole "screen" that can be seen at once in the terminal.
    It contains an userlist, an input zone and a chat zone, all
    related to one single chat room.
    """
    def __init__(self, stdscr, name=None):
        """
        name is the name of the Tab, and it's also
        the JID of the chatroom.
        A particular tab is the "Info" tab which has no
        name (None). This info tab should be unique.
        The stdscr should be passed to know the size of the
        terminal
        """
        self.name = name
        self.size = (self.height, self.width) = stdscr.getmaxyx()
        self.user_win = UserList(self.height-1, self.width/7, 0, 6*(self.width/7), stdscr)#        self.contact_win = stdscr.subwin(7, 7)#self.height-1, self.width/3, 0, 2*(self.width/3))
        self.topic_win = Info(1, self.width, 0, 0, stdscr)
        self.topic_win.set_info("Salon machin - Blablablbla, le topic blablabla")
        self.info_win = Info(1, self.width, self.height-2, 0, stdscr)
        self.info_win.set_info("FION")

        # stdscr.addstr("stdscr [%s, %s]\n" % (self.height, self.width))
        # stdscr.addstr("contact [%s, %s][%s, %s]" % (self.height-1, self.width/3, 0, 2*(self.width/3)))
    def resize(self, y, x):
        """
        Resize the whole tabe. i.e. all its sub-windows
        """
        pass

class Gui(object):
    """
    Graphical user interface using ncurses
    """
    def __init__(self, stdscr):
        self.handler = Handler()

        self.handler.connect('on-muc-message-received', self.on_message)
        self.handler.connect('join-room', self.on_join_room)
        self.handler.connect('on-muc-presence-changed', self.on_presence)

        self.init_curses(stdscr)

    # def __del__(self):
    #     curses.nocbreak();
    #     self.stdscr.keypad(0);
    #     curses.echo()
    #     curses.endwin()

    def init_curses(self, stdscr):
#        self.stdscr=       curses.initscr()
        # curses.noecho()
        # curses.cbreak()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLUE, 0)
        self.current_tab = Tab(stdscr)

    def main_loop(self, stdscr):
        while 1:
            stdscr.refresh()
            key = stdscr.getch()
#            print key
#            stdscr.addstr("f")
            if key == curses.KEY_RESIZE:
                sys.exit()
            self.current_tab.input.do_command(key)

    def on_message(self, jid, msg, subject, typ, stanza):
        print "on_message", jid, msg, subject, typ

    def on_join_room(self, room, nick):
        print "on_join_room", room, nick

    def on_presence(self, jid, priority, show, status, stanza):
        print "on presence", jid, priority, show, status

    def get_input(self):
        return self.stdscr.getch()

def main(stdscr):
    gui = Gui(stdscr)
    gui.main_loop(stdscr)

if __name__ == '__main__':
    curses.wrapper(main)
