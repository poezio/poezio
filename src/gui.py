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
        curses.initscr()
        self.stdscr = curses.newwin(1, 1000, 0, 0)
        curses.noecho()
        curses.cbreak()
        curses.meta(True)
        self.stdscr.keypad(1)
        self.input = textpad.Textbox(self.stdscr)

    def on_message(self, jid, msg, subject, typ, stanza):
        print "on_message", jid, msg, subject, typ

    def on_join_room(self, room, nick):
        print "on_join_room", room, nick

    def on_presence(self, jid, priority, show, status, stanza):
        print "on presence", jid, priority, show, status

    def get_input(self):
        return self.stdscr.getch()
def sigwinch_handler(n, frame):
    fd = open('fion', 'a')
    fd.write(str(n)+ '\n')
    fd.close()

if __name__ == '__main__':
    gui = Gui()
    import signal
    signal.signal(signal.SIGWINCH, sigwinch_handler)
    while 1:
        key = gui.stdscr.getch()
        if key == curses.KEY_RESIZE:
            print "FION"
            import sys
            sys.exit()
        gui.input.do_command(key)

