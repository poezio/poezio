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
        self._resize(height, width, y, x, parent_win)

    def _resize(self, height, width, y, x, parent_win):
        self.height, self.width, self.x, self.y = height, width, x, y
        try:
            self.win = parent_win.subwin(height, width, y, x)
        except:
            pass

class UserList(Win):
    def __init__(self, height, width, y, x, parent_win):
        Win.__init__(self, height, width, y, x, parent_win)
        self.list = []

    def add_user(self, name):
        """
        add an user to the list
        """
        self.list.append(name)

    def refresh(self):
        self.win.clear()
        self.win.attron(curses.color_pair(2))
        self.win.vline(0, 0, curses.ACS_VLINE, self.height)
        self.win.attroff(curses.color_pair(2))
        y = 0
        for name in self.list:
            self.win.addstr(y, 1, name)
            y += 1
        self.win.refresh()

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)
        self.refresh()

class Info(Win):
    def __init__(self, height, width, y, x, parent_win):
        Win.__init__(self, height, width, y, x, parent_win)
        self.txt = ""
#        self.win.bkgd(ord('p'), curses.COLOR_BLUE)

    def set_info(self, text):
        self.txt = text
        self.refresh()

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)
        self.refresh()

    def refresh(self):
        try:
            self.win.addstr(0, 0, self.txt + " "*(self.width-len(self.txt)-1)
                        , curses.color_pair(1))
        except:
            pass

class TextWin(Win):
    def __init__(self, height, width, y, x, parent_win):
        Win.__init__(self, height, width, y, x, parent_win)
        self.lines = []

    def add_line(self, time, nick, text):
        self.lines.append((time, nick, text))
        self.refresh()

    def refresh(self):
        self.win.clear()
        y = 0
        for line in self.lines[-self.height:]:
            self.win.addstr(y, 0, line[0] + " : " + line[1] + ": " + line[2])
            y += 1
        self.win.refresh()

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)
        self.refresh()

class Input(Win):
    """
    """
    def __init__(self, height, width, y, x, stdscr):
        Win.__init__(self, height, width, y, x, stdscr)
        self.input = curses.textpad.Textbox(self.win)
        self.input.tripspaces = False

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)
        txt = self.input.gather()
        self.input = curses.textpad.Textbox(self.win)
        self.input.tripspaces = False
        self.win.clear()
#        self.win.addstr(txt)

    def do_command(self, key):
        self.input.do_command(key)
        self.win.refresh()

    def gettext(self):
        return self.input.gather()

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

        self.user_win = UserList(self.height-3, self.width/7, 1, 6*(self.width/7), stdscr)
        self.topic_win = Info(1, self.width, 0, 0, stdscr)
        self.info_win = Info(1, self.width, self.height-2, 0, stdscr)
        self.text_win = TextWin(self.height-3, (self.width/7)*6, 1, 0, stdscr)
        self.input = Input(1, self.width, self.height-1, 0, stdscr)
#        self.text_win.refresh()

        # debug
        self.topic_win.set_info("Salon machin - Blablablbla, le topic blablabla")
        self.info_win.set_info("FION")
        for name in ["pipi", "caca", "louiz", "mRk", "restrict", "jacko"]:
            self.user_win.add_user(name)
        self.refresh()

    def resize(self, stdscr):
        """
        Resize the whole tabe. i.e. all its sub-windows
        """
        self.size = (self.height, self.width) = stdscr.getmaxyx()
        self.user_win.resize(self.height-3, self.width/7, 1, 6*(self.width/7), stdscr)
        self.topic_win.resize(1, self.width, 0, 0, stdscr)
        self.info_win.resize(1, self.width, self.height-2, 0, stdscr)
        self.text_win.resize(self.height-3, (self.width/7)*6, 1, 0, stdscr)
        self.input.resize(1, self.width, self.height-1, 0, stdscr)
        self.refresh()

    def refresh(self):
        self.text_win.refresh()
        self.user_win.refresh()
        self.topic_win.refresh()
        self.info_win.refresh()

    def do_command(self, key):
        self.input.do_command(key)
#        self.input_win.refresh()

    def send_message(self):
        self.text_win.add_line("NOW", "louiz'", self.input.gettext())

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

    def init_curses(self, stdscr):
#        self.stdscr=       curses.initscr()
        # curses.noecho()
        # curses.cbreak()
        stdscr.leaveok(True)
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLUE, 0)
        self.current_tab = Tab(stdscr)

    def main_loop(self, stdscr):
        while 1:
            stdscr.refresh()
            key = stdscr.getch()
            if key == curses.KEY_RESIZE:
                self.current_tab.resize(stdscr)
            elif key == 10:
                self.current_tab.send_message()
            self.current_tab.do_command(key)
            # else:
            #     sys.exit()
#            self.current_tab.input.do_command(key)

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
