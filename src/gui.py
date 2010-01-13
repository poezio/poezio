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

import locale
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

import sys

from connection import *

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
        self.win.attron(curses.color_pair(2))
        self.win.vline(0, 0, curses.ACS_VLINE, self.height)
        self.win.attroff(curses.color_pair(2))
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
        self.win.clear()
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
        self.input.stripspaces = False
        self.input.insert_mode = True
        self.txt = ''

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)
        self.input = curses.textpad.Textbox(self.win)
        self.input.insert_mode = True
        self.input.stripspaces = False
        self.win.clear()
        self.win.addstr(self.txt)

    def do_command(self, key):
        self.input.do_command(key)
#        self.win.refresh()
#        self.text = self.input.gather()

    # def insert_char(self, key):
    #     if self.insert:
    #         self.text = self.text[:self.pos]+key+self.text[self.pos:]
    #     else:
    #         self.text = self.text[:self.pos]+key+self.text[self.pos+1:]
    #     self.pos += 1
    #     pass

    def get_text(self):
        return self.input.gather()

    def save_text(self):
        self.txt = self.input.gather()
#        self.win.clear()
#        self.win.addstr(self.txt)

    def refresh(self):
#        self.win.clear()
#        self.win.addstr(self.text)
#        self.win.move(0, len(self.text)-1)
        self.win.refresh()

    def clear_text(self):
        self.win.clear()
        self.txt = ''
        self.pos = 0
        self.refresh()

class Tab(object):
    """
    The whole "screen" that can be seen at once in the terminal.
    It contains an userlist, an input zone and a chat zone, all
    related to one single chat room.
    """
    def __init__(self, stdscr, name='info'):
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

        self.info_win.set_info(name)
        # debug
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
        self.text_win.add_line("fion", "fion", "refresh")
        self.text_win.refresh()
        self.user_win.refresh()
        self.topic_win.refresh()
        self.info_win.refresh()
        self.input.refresh()

    def do_command(self, key):
        self.input.do_command(key)
#        self.input.save_text()
        self.input.refresh()

class Gui(object):
    """
    Graphical user interface using ncurses
    """
    def __init__(self, stdscr):
        self.handler = Handler()

        self.commands = {
            'join': self.command_join,
            'quit': self.command_quit,
            }

        self.handler.connect('on-muc-message-received', self.on_message)
        self.handler.connect('gui-join-room', self.on_join_room)
        self.handler.connect('on-muc-presence-changed', self.on_presence)

        self.init_curses(stdscr)
        self.stdscr = stdscr

    def execute(self):
        line = self.current_tab.input.get_text()
        self.current_tab.input.clear_text()
        if line.strip().startswith('/'):
            command = line.strip()[:].split()[0][1:]
            args = line.strip()[:].split()[1:]
            if command in self.commands.keys():
                func = self.commands[command]
                func(args)
            return
        self.current_tab.text_win.add_line("NOW", "louiz'", line)
        # TODO, send message to jabber

    def command_join(self, args):
        room = args[0]
        self.on_join_room(room, "poezio")

    def command_quit(self, args):
        sys.exit()

    def init_curses(self, stdscr):
        stdscr.leaveok(True)
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLACK)
        self.current_tab = Tab(stdscr)
        self.tabs = [self.current_tab]

    def main_loop(self, stdscr):
        while 1:
            stdscr.refresh()
            key = stdscr.getch()
            if key == curses.KEY_RESIZE:
                self.current_tab.resize(stdscr)
            elif key == 10:
                self.execute()
            else:
                self.current_tab.do_command(key)

    def on_message(self, jid, msg, subject, typ, stanza):
        print "on_message", jid, msg, subject, typ

    def on_join_room(self, room, nick):
        sys.stderr.write(room)
        self.current_tab = Tab(self.stdscr, room)
        self.tabs.append(self.current_tab)
#        self.current_tab.resize()
        self.current_tab.refresh()
        print "on_join_room", room, nick

    def on_presence(self, jid, priority, show, status, stanza):
        print "on presence", jid, priority, show, status

def main(stdscr):
    gui = Gui(stdscr)
    gui.main_loop(stdscr)

if __name__ == '__main__':
    resource = config.get('resource')
    server = config.get('server')
    connection = Connection(server, resource)
    connection.start()
    curses.wrapper(main)
    # rooms = config.get('rooms').split(':')
    # for room in rooms:
    #     connection.send_join_room(room.split('/')[0], room.split('/')[1])
