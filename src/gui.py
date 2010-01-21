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
from datetime import datetime

locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

import sys

from connection import *
from window import Window

class User(object):
    """
    keep trace of an user in a Room
    """
    def __init__(self, nick, affiliation, show, status, role):
        self.update(affiliation, show, status, role)
        self.change_nick(nick)

    def update(self, affiliation, show, status, role):
        self.affiliation = None
        self.show = None
        self.status = status
        self.role = role

    def change_nick(self, nick):
        self.nick = nick.encode('utf-8')

class Room(object):
    """
    """
    def __init__(self, name, nick):
        self.name = name
        self.own_nick = nick
        self.joined = False     # false until self presence is received
        self.users = []
        self.lines = []         # (time, nick, msg) or (time, info)
        self.topic = ''

    def add_message(self, nick, msg):
        self.lines.append((datetime.now(), nick.encode('utf-8'), msg.encode('utf-8')))

    def add_info(self, info):
        """ info, like join/quit/status messages"""
        self.lines.append((datetime.now(), info.encode('utf-8')))

    def on_presence(self, stanza, nick):
        """
        """
        affiliation = stanza.getAffiliation()
        show = stanza.getShow()
        status = stanza.getStatus()
        role = stanza.getRole()
        if not self.joined:
             self.users.append(User(nick, affiliation, show, status, role))
             if nick == self.own_nick:
                 self.joined = True
             self.add_info("%s is in the room" % (nick))
             return
        change_nick = stanza.getStatusCode() == '303'
        for user in self.users:
            if user.nick == nick:
                if change_nick:
                    user.change_nick(stanza.getNick())
                    self.add_info('%s is now known as %s' % (nick, stanza.getNick()))
                    return
                if status == 'offline':
                    self.users.remove(user)
                    self.add_info('%s has left the room' % (nick))
                    return
                user.update(affiliation, show, status, role)
                self.add_info('%s, status : %s, %s, %s, %s' % (nick, affiliation, role, show, status))
                return
        self.users.append(User(nick, affiliation, show, status, role))
        self.add_info('%s joined the room %s' % (nick, self.name))

class Gui(object):
    """
    Graphical user interface using ncurses
    """
    def __init__(self, stdscr=None, muc=None):

        self.init_curses(stdscr)
        self.stdscr = stdscr
        self.stdscr.leaveok(True)
        self.rooms = [Room('Info', '')]         # current_room is self.rooms[0]
        self.window = Window(stdscr)
        self.window.refresh(self.rooms[0])

        self.muc = muc

        self.commands = {
            'join': self.command_join,
            'quit': self.command_quit,
            'next': self.rotate_rooms_left,
            'prev': self.rotate_rooms_right,
            }


        self.handler = Handler()
        self.handler.connect('on-connected', self.on_connected)
        self.handler.connect('join-room', self.join_room)
        self.handler.connect('room-presence', self.room_presence)
        self.handler.connect('room-message', self.room_message)

    def init_curses(self, stdscr):
        curses.start_color()
        curses.noecho()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK) # Admin
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK) # Participant
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLACK) # Visitor

    def on_connected(self):
        pass

    def join_room(self, room, nick):
        self.rooms.insert(0, Room(room, nick))
        self.window.refresh(self.rooms[0])

    def rotate_rooms_left(self, args):
        self.rooms.append(self.rooms.pop(0))
        self.window.refresh(self.rooms[0])

    def rotate_rooms_right(self, args):
        self.rooms.insert(0, self.rooms.pop())
        self.window.refresh(self.rooms[0])

    def room_message(self, stanza):
        if stanza.getType() != 'groupchat':
            return  # ignore all messages not comming from a MUC
        room_from = stanza.getFrom().getStripped()
        nick_from = stanza.getFrom().getResource()
        for room in self.rooms:
            if room_from == room.name:
                room.add_message(nick_from, stanza.getBody())
                if room == self.rooms[0]:
                    self.window.text_win.refresh(room.lines)
                    self.window.user_win.refresh(room.users)
                    self.window.input.refresh()
#                    self.window.refresh(self.rooms[0])
                    curses.doupdate()
                break

    def room_presence(self, stanza):
        from_nick = stanza.getFrom().getResource()
        from_room = stanza.getFrom().getStripped()
        for room in self.rooms:
            if from_room == room.name:
                room.on_presence(stanza, from_nick)
                if room == self.rooms[0]:
                    self.window.text_win.refresh(room.lines)
                    self.window.user_win.refresh(room.users)
                    curses.doupdate()
                break

    def execute(self):
        line = self.window.input.get_text()
        self.window.input.clear_text()
        if line == "":
            return
        if line.strip().startswith('/'):
            command = line.strip()[:].split()[0][1:]
            args = line.strip()[:].split()[1:]
            if command in self.commands.keys():
                func = self.commands[command]
                func(args)
            return
        if self.rooms[0].name != 'Info':
            self.muc.send_message(self.rooms[0].name, line)

    def command_join(self, args):
        room = args[0]
        self.muc.join_room(room, "poezio")
        self.join_room(room, 'poezio')

    def command_quit(self, args):
        sys.exit()

    def main_loop(self, stdscr):
        while 1:
            curses.doupdate()
            # self.window.input.refresh()
            key = stdscr.getch()
            if key == curses.KEY_RESIZE:
                self.window.resize(stdscr)
            elif key == 10:
                self.execute()
            else:
                self.window.do_command(key)
