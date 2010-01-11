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
#        self.window = curses.newwin(0, 0)#, self.height, self.width)
        self.input = textpad.Textbox(stdscr)
#        self.window.refresh()

    def resize(self, y, x):
        """
        Resize the whole tabe. i.e. all its sub-windows
        """
        pass

class Gui(object):
    """
    Graphical user interface using ncurses
    """
    def __init__(self):
        self.handler = Handler()

        self.handler.connect('on-muc-message-received', self.on_message)
        self.handler.connect('join-room', self.on_join_room)
        self.handler.connect('on-muc-presence-changed', self.on_presence)

        self.init_curses()

    def __del__(self):
        curses.nocbreak();
        self.stdscr.keypad(0);
        curses.echo()
        curses.endwin()

    def init_curses(self):
        self.stdscr=       curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.current_tab = Tab(self.stdscr)

    def main_loop(self, stdscr):
        while 1:
            key = stdscr.getch()
            if key == curses.KEY_RESIZE:
                pass
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
    gui = Gui()
    gui.main_loop(stdscr)

if __name__ == '__main__':
    curses.wrapper(main)
