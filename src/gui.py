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

from logging import logger

from random import randrange

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
        self.color = randrange(2, 10)

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
        if not msg:
            logger.info('msg is None..., %s' % (nick))
            return
        # lines = msg.split('\n')
        # first line has the nick and timestamp but others don't
        self.lines.append((datetime.now(), nick.encode('utf-8'), msg.encode('utf-8')))
        # if len(lines) > 0:
        #     for line in lines:
        #         self.lines.append((line.encode('utf-8')))

    def add_info(self, info):
        """ info, like join/quit/status messages"""
        self.lines.append((datetime.now(), info.encode('utf-8')))
        return info.encode('utf-8')

    def on_presence(self, stanza, nick):
        """
        """
        affiliation = stanza.getAffiliation()
        show = stanza.getShow()
        status = stanza.getStatus()
        role = stanza.getRole()
        if not self.joined:
             self.users.append(User(nick, affiliation, show, status, role))
             if nick.encode('utf-8') == self.own_nick.encode('utf-8'):
                 self.joined = True
             return self.add_info("%s is in the room" % (nick))
        change_nick = stanza.getStatusCode() == '303'
        for user in self.users:
            if user.nick.encode('utf-8') == nick.encode('utf-8'):
                if change_nick:
                    user.change_nick(stanza.getNick())
                    return self.add_info('%s is now known as %s' % (nick, stanza.getNick()))
                if status == 'offline' or role == 'none':
                    self.users.remove(user)
                    return self.add_info('%s has left the room' % (nick))
                user.update(affiliation, show, status, role)
                return self.add_info('%s, status : %s, %s, %s, %s' % (nick, affiliation, role, show, status))
        self.users.append(User(nick, affiliation, show, status, role))
        return self.add_info('%s joined the room %s' % (nick, self.name))

class Gui(object):
    """
    Graphical user interface using ncurses
    """
    def __init__(self, stdscr=None, muc=None):

        self.init_curses(stdscr)
        self.stdscr = stdscr
        self.stdscr.leaveok(1)
        self.rooms = [Room('Info', '')]         # current_room is self.rooms[0]
        self.window = Window(stdscr)
        self.window.text_win.new_win('Info')
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

    def current_room(self):
	return self.rooms[0]

    def get_room_by_name(self, name):
	for room in self.rooms:
	    if room.name == name:
		return room
	return None

    def init_curses(self, stdscr):
        curses.start_color()
        curses.noecho()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK) # Admin
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK) # Participant
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLACK) # Visitor
        curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(8, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(9, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    def reset_curses(self):
	curses.echo()
        curses.endwin()

    def on_connected(self):
        pass

    def join_room(self, room, nick):
        self.window.text_win.new_win(room)
        self.rooms.insert(0, Room(room, nick))
        self.window.refresh(self.current_room())

    def rotate_rooms_left(self, args):
        self.rooms.append(self.rooms.pop(0))
        self.stdscr.touchwin()
        self.window.refresh(self.current_room())

    def rotate_rooms_right(self, args):
        self.rooms.insert(0, self.rooms.pop())
#        self.stdscr.touchwin()
        self.window.refresh(self.current_room())

    def room_message(self, stanza):
        if stanza.getType() != 'groupchat':
            return  # ignore all messages not comming from a MUC
        room_from = stanza.getFrom().getStripped()
        nick_from = stanza.getFrom().getResource()
        if not nick_from:
            nick_from = ''
	room = self.get_room_by_name(room_from)
	if not room:
	    return logger.warning("message received for a non-existing room: %s" % (name))
        body = stanza.getBody()
        if not body:
            body = stanza.getSubject()
            room.add_info("%s changed the subject to: %s" % (nick_from, stanza.getSubject()))
        else:
            room.add_message(nick_from, body)
            self.window.text_win.add_line(room, (datetime.now(), nick_from.encode('utf-8'), body.encode('utf-8')))
        if room == self.current_room():
            self.window.text_win.refresh(room.name)
            self.window.input.refresh()
            curses.doupdate()

    def room_presence(self, stanza):
        from_nick = stanza.getFrom().getResource()
        from_room = stanza.getFrom().getStripped()
	room = self.get_room_by_name(from_room)
	if not room:
	    return logger.warning("presence received for a non-existing room: %s" % (name))
        msg = room.on_presence(stanza, from_nick)
        self.window.text_win.add_line(room, (datetime.now(), msg))
        if room == self.current_room():
	        self.window.text_win.refresh(room.name)
                self.window.user_win.refresh(room.users)
                curses.doupdate()

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
        if self.current_room().name != 'Info':
            self.muc.send_message(self.current_room().name, line)
	self.window.input.refresh()

    def command_join(self, args):
        room = args[0]
        self.muc.join_room(room, "poezio")
        self.join_room(room, 'poezio')

    def command_quit(self, args):
	self.reset_curses()
        sys.exit()

    def main_loop(self, stdscr):
        while 1:
            curses.doupdate()
            key = stdscr.getkey()
            if ord(key) == 195:
                n = stdscr.getkey()
                key = key+n
                self.window.input.win.addstr(key)
                self.window.input.add_char(key)
                self.window.input.win.refresh()
            elif ord(key) == 226:
                n = stdscr.getkey()
                m = stdscr.getkey()
                key = key+n+m
                self.window.input.win.addstr(key)
                self.window.input.add_char(key)
                self.window.input.win.refresh()

            elif key == curses.KEY_RESIZE:
                self.window.resize(stdscr)
            elif ord(key) == 10:
                self.execute()
            else:
                self.window.do_command(ord(key))
