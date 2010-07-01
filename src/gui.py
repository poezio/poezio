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

from gettext import (bindtextdomain, textdomain, bind_textdomain_codeset,
                     gettext as _)
from os.path import isfile

from time import sleep

import sys
import os

import curses
from datetime import datetime

import common

from handler import Handler
from config import config
from window import Window
from user import User
from room import Room
from message import Message

from common import is_jid_the_same, jid_get_domain, is_jid

def doupdate():
    curses.doupdate()

class Gui(object):
    """
    User interface using ncurses
    """
    def __init__(self, stdscr=None, muc=None):
        self.init_curses(stdscr)
        self.stdscr = stdscr
        self.window = Window(stdscr)
        self.rooms = [Room('Info', '', self.window)]
        self.ignores = {}

        self.muc = muc

        self.commands = {
            'help': (self.command_help, u'\_o< KOIN KOIN KOIN'),
            'join': (self.command_join, _("Usage: /join [room_name][@server][/nick] [password]\nJoin: Join the specified room. You can specify a nickname after a slash (/). If no nickname is specified, you will use the default_nick in the configuration file. You can omit the room name: you will then join the room you\'re looking at (useful if you were kicked). You can also provide a room_name without specifying a server, the server of the room you're currently in will be used. You can also provide a password to join the room.\nExamples:\n/join room@server.tld\n/join room@server.tld/John\n/join room2\n/join /me_again\n/join\n/join room@server.tld/my_nick password\n/join / password")),
            'quit': (self.command_quit, _("Usage: /quit\nQuit: Just disconnect from the server and exit poezio.")),
            'exit': (self.command_quit, _("Usage: /exit\nExit: Just disconnect from the server and exit poezio.")),
            'next': (self.rotate_rooms_right, _("Usage: /next\nNext: Go to the next room.")),
            'n': (self.rotate_rooms_right, _("Usage: /n\nN: Go to the next room.")),
            'prev': (self.rotate_rooms_left, _("Usage: /prev\nPrev: Go to the previous room.")),
            'p': (self.rotate_rooms_left, _("Usage: /p\nP: Go to the previous room.")),
            'win': (self.command_win, _("Usage: /win <number>\nWin: Go to the specified room.")),
            'w': (self.command_win, _("Usage: /w <number>\nW: Go to the specified room.")),
            'ignore': (self.command_ignore, _("Usage: /ignore <nickname> \nIgnore: Ignore a specified nickname.")),
            'unignore': (self.command_unignore, _("Usage: /unignore <nickname>\nUnignore: Remove the specified nickname from the ignore list.")),
            'part': (self.command_part, _("Usage: /part [message]\n Part: disconnect from a room. You can specify an optional message.")),
            'show': (self.command_show, _("Usage: /show <availability> [status]\nShow: Change your availability and (optionaly) your status. The <availability> argument is one of \"avail, available, ok, here, chat, away, afk, dnd, busy, xa\" and the optional [message] argument will be your status message")),
            'away': (self.command_away, _("Usage: /away [message]\nAway: Sets your availability to away and (optional) sets your status message. This is equivalent to '/show away [message]'")),
            'busy': (self.command_busy, _("Usage: /busy [message]\nBusy: Sets your availability to busy and (optional) sets your status message. This is equivalent to '/show busy [message]'")),
            'avail': (self.command_avail, _("Usage: /avail [message]\nAvail: Sets your availability to available and (optional) sets your status message. This is equivalent to '/show available [message]'")),
            'available': (self.command_avail, _("Usage: /available [message]\nAvailable: Sets your availability to available and (optional) sets your status message. This is equivalent to '/show available [message]'")),
           'bookmark': (self.command_bookmark, _("Usage: /bookmark [roomname][/nick]\nBookmark: Bookmark the specified room (you will then auto-join it on each poezio start). This commands uses the same syntaxe as /join. Type /help join for syntaxe examples. Note that when typing \"/bookmark\" on its own, the room will be bookmarked with the nickname you\'re currently using in this room (instead of default_nick)")),
            'unquery': (self.command_unquery, _("Usage: /unquery\nClose the private conversation window")),
            'set': (self.command_set, _("Usage: /set <option> [value]\nSet: Sets the value to the option in your configuration file. You can, for example, change your default nickname by doing `/set default_nick toto` or your resource with `/set resource blabla`. You can also set an empty value (nothing) by providing no [value] after <option>.")),
            'kick': (self.command_kick, _("Usage: /kick <nick> [reason]\nKick: Kick the user with the specified nickname. You also can give an optional reason.")),
            'topic': (self.command_topic, _("Usage: /topic <subject> \nTopic: Change the subject of the room")),
            'query': (self.command_query, _('Usage: /query <nick> [message]\nQuery: Open a private conversation with <nick>. This nick has to be present in the room you\'re currently in. If you specified a message after the nickname, it will immediately be sent to this user')),

            'nick': (self.command_nick, _("Usage: /nick <nickname> \nNick: Change your nickname in the current room"))
            }

        self.key_func = {
            "KEY_LEFT": self.window.input.key_left,
            "KEY_RIGHT": self.window.input.key_right,
            "KEY_UP": self.window.input.key_up,
            "KEY_END": self.window.input.key_end,
            "KEY_HOME": self.window.input.key_home,
            "KEY_DOWN": self.window.input.key_down,
            "KEY_PPAGE": self.scroll_page_up,
            "KEY_NPAGE": self.scroll_page_down,
            "KEY_DC": self.window.input.key_dc,
            "KEY_F(5)": self.rotate_rooms_left,
            "KEY_F(6)": self.rotate_rooms_right,
            "kLFT5": self.rotate_rooms_left,
            "kRIT5": self.rotate_rooms_right,
            "\t": self.auto_completion,
            "KEY_BACKSPACE": self.window.input.key_backspace
            }

        self.handler = Handler()
        self.handler.connect('on-connected', self.on_connected)
        self.handler.connect('join-room', self.join_room)
        self.handler.connect('room-presence', self.room_presence)
        self.handler.connect('room-message', self.room_message)
        self.handler.connect('private-message', self.private_message)
        self.handler.connect('error-message', self.room_error)
        self.handler.connect('error', self.information)

    def main_loop(self, stdscr):
        """
        main loop waiting for the user to press a key
        """
        while 1:
            doupdate()
            try:
                key = stdscr.getkey()
            except:
                continue
            if str(key) in self.key_func.keys():
                self.key_func[key]()
            elif str(key) == 'KEY_RESIZE':
                self.window.resize(stdscr)
                self.window.refresh(self.rooms)
            elif len(key) >= 4:
                continue
            elif ord(key) == 10:
                self.execute()
            elif ord(key) == 8 or ord(key) == 127:
                self.window.input.key_backspace()
            elif ord(key) < 32:
                continue
            else:
                if ord(key) == 27 and ord(stdscr.getkey()) == 91:
                    last = ord(stdscr.getkey()) # FIXME: ugly ugly workaround.
                    if last == 51:
                        self.window.input.key_dc()
                    continue
                elif ord(key) > 190 and ord(key) < 225:
                    key = key+stdscr.getkey()
                elif ord(key) == 226:
                    key = key+stdscr.getkey()
                    key = key+stdscr.getkey()
                self.window.do_command(key)

    def current_room(self):
        """
        returns the current room, the one we are viewing
        """
        return self.rooms[0]

    def get_room_by_name(self, name):
        """
        returns the room that has this name
        """
        for room in self.rooms:
            if room.name == name:
                return room
        return None

    def init_curses(self, stdscr):
        """
        ncurses initialization
        """
        curses.start_color()
        curses.noecho()
        curses.curs_set(0)
        curses.use_default_colors()
        stdscr.keypad(True)
        curses.init_pair(1, curses.COLOR_WHITE,
                         curses.COLOR_BLUE)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1) # Admin
        curses.init_pair(3, curses.COLOR_BLUE, -1) # Participant
        curses.init_pair(5, curses.COLOR_WHITE, -1) # Visitor
        curses.init_pair(6, curses.COLOR_CYAN, -1)
        curses.init_pair(7, curses.COLOR_GREEN, -1)
        curses.init_pair(8, curses.COLOR_MAGENTA, -1)
        curses.init_pair(9, curses.COLOR_YELLOW, -1)
        curses.init_pair(10, curses.COLOR_WHITE,
                         curses.COLOR_CYAN) # current room
        curses.init_pair(11, curses.COLOR_WHITE,
                         curses.COLOR_BLUE) # normal room
        curses.init_pair(12, curses.COLOR_WHITE,
                         curses.COLOR_MAGENTA) # new message room
        curses.init_pair(13, curses.COLOR_WHITE,
                         curses.COLOR_RED) # highlight room
        curses.init_pair(14, curses.COLOR_WHITE,
                         curses.COLOR_YELLOW)
        curses.init_pair(15, curses.COLOR_WHITE, # new message in private room
                         curses.COLOR_GREEN)

    def reset_curses(self):
        """
        Reset terminal capabilities to what they were before ncurses
        init
        """
        curses.echo()
        curses.nocbreak()
        curses.endwin()

    def on_connected(self, jid):
        """
        We are connected when authentification confirmation is received
        """
        self.information(_("Welcome on Poezio \o/!"))
        self.information(_("Your JID is %s") % jid)

    def join_room(self, room, nick):
        """
        join the specified room (muc), using the specified nick
        """
        r = Room(room, nick, self.window)
        self.current_room().set_color_state(11)
        if self.current_room().nb == 0:
            self.rooms.append(r)
        else:
            for ro in self.rooms:
                if ro.nb == 0:
                    self.rooms.insert(self.rooms.index(ro), r)
                    break
        while self.current_room().nb != r.nb:
            self.rooms.insert(0, self.rooms.pop())
        self.window.refresh(self.rooms)

    def auto_completion(self):
        """
        Called when Tab is pressed, complete the nickname in the input
        """
        self.window.input.auto_completion(self.current_room().users)

    def rotate_rooms_right(self, args=None):
        """
        rotate the rooms list to the right
        """
        self.current_room().set_color_state(11)
        self.rooms.append(self.rooms.pop(0))
        self.window.refresh(self.rooms)

    def rotate_rooms_left(self, args=None):
        """
        rotate the rooms list to the right
        """
        self.current_room().set_color_state(11)
        self.rooms.insert(0, self.rooms.pop())
        self.window.refresh(self.rooms)

    def scroll_page_down(self, args=None):
        self.current_room().scroll_down()
        self.window.refresh(self.rooms)

    def scroll_page_up(self, args=None):
        self.current_room().scroll_up(self.window.size)
        self.window.refresh(self.rooms)

    def room_error(self, room, error, msg):
        """
        Display the error on the room window
        """
        if not error:
            return
        room = self.get_room_by_name(room)
        code = error.getAttr('code')
        typ = error.getAttr('type')
        if error.getTag('text'):
            body = error.getTag('text').getData()
        else:
            body = _('Unknown error')
        self.add_message_to_room(room, _('Error: %(code)s-%(msg)s: %(body)s' %
                                   {'msg':msg, 'code':code, 'body':body}))
        if code == '401':
            room.add(_('To provide a password in order to join the room, type "/join / password" (replace "password" by the real password)'))
        self.window.refresh(self.rooms)

    def private_message(self, stanza):
        """
        When a private message is received
        """
        jid = stanza.getFrom()
        nick_from = stanza.getFrom().getResource()
        room_from = stanza.getFrom().getStripped()
        room = self.get_room_by_name(jid) # get the tab with the private conversation
        if not room: # It's the first message we receive: create the tab
            room = self.open_private_window(room_from, nick_from, False)
        body = stanza.getBody()
        self.add_message_to_room(room, body, None, nick_from)
        self.window.input.refresh()
        doupdate()

    def open_private_window(self, room_name, user_nick, focus=True):
        complete_jid = room_name+'/'+user_nick
        for room in self.rooms: # if the room exists, focus it and return
            if room.jid:
                if room.jid == complete_jid:
                    self.command_win(str(room.nb))
                    return
        # create the new tab
        own_nick = self.get_room_by_name(room_name).own_nick
        r = Room(complete_jid, own_nick, self.window, complete_jid)
        # insert it in the rooms
        if self.current_room().nb == 0:
            self.rooms.append(r)
        else:
            for ro in self.rooms:
                if ro.nb == 0:
                    self.rooms.insert(self.rooms.index(ro), r)
                    break
        if focus:               # focus the room if needed
            while self.current_room().nb != r.nb:
                self.rooms.insert(0, self.rooms.pop())
        # self.window.new_room(r)
        self.window.refresh(self.rooms)
        return r

    def room_message(self, stanza, date=None):
        """
        Display the message on the room window
        """
        delay_tag = stanza.getTag('delay', namespace='urn:xmpp:delay')
        if delay_tag and not date:
            delayed = True
            date = common.datetime_tuple(delay_tag.getAttr('stamp'))
        else:
            delayed = False
        if stanza.getType() != 'groupchat':
            return  # ignore all messages not comming from a MUC
        nick_from = stanza.getFrom().getResource()
        room_from = stanza.getFrom().getStripped()
        if (self.ignores.has_key(room_from)) and (nick_from in self.ignores[room_from]):
            return
        room = self.get_room_by_name(room_from)
	if not room:
	    self.information(_("message received for a non-existing room: %s") % (room_from))
            return
        body = stanza.getBody()
        subject = stanza.getSubject()
        if subject:
            if nick_from:
                self.add_message_to_room(room, _("%(nick)s changed the subject to: %(subject)s") % {'nick':nick_from, 'subject':subject}, date)
            else:
                self.add_message_to_room(room, _("The subject is: %(subject)s") % {'subject':subject}, date)
            room.topic = subject.encode('utf-8').replace('\n', '|')
            if room == self.current_room():
                self.window.topic_win.refresh(room.topic)
        elif body:
            if body.startswith('/me '):
                self.add_message_to_room(room, "* "+nick_from + ' ' + body[4:], date)
            else:
                date = date if delayed == True else None
                self.add_message_to_room(room, body, date, nick_from)
        self.window.refresh(self.rooms)
        doupdate()

    def room_presence(self, stanza):
        """
        Display the presence on the room window and update the
        presence information of the concerned user
        """
        from_nick = stanza.getFrom().getResource()
        from_room = stanza.getFrom().getStripped()
	room = self.get_room_by_name(from_room)
	if not room:
            return
        else:
            msg = None
            affiliation = stanza.getAffiliation()
            show = stanza.getShow()
            status = stanza.getStatus()
            role = stanza.getRole()
            if not room.joined:     # user in the room BEFORE us.
                room.users.append(User(from_nick, affiliation, show, status,
                                       role))
                if from_nick.encode('utf-8') == room.own_nick:
                    room.joined = True
                    self.add_message_to_room(room, _("Your nickname is %s") % (from_nick))
                else:
                    self.add_message_to_room(room, _("%s is in the room") % (from_nick))
            else:
                change_nick = stanza.getStatusCode() == '303'
                kick = stanza.getStatusCode() == '307'
                user = room.get_user_by_name(from_nick)
                # New user
                if not user:
                    room.users.append(User(from_nick, affiliation,
                                           show, status, role))
                    hide_exit_join = config.get('hide_exit_join', -1)
                    if hide_exit_join != 0:
                        self.add_message_to_room(room, _("%(nick)s joined the room %(roomname)s") % {'nick':from_nick, 'roomname': room.name})
                # nick change
                elif change_nick:
                    if user.nick == room.own_nick:
                        room.own_nick = stanza.getNick().encode('utf-8')
                        # also change our nick in all private discussion of this room
                        for _room in self.rooms:
                            if _room.jid is not None and is_jid_the_same(_room.jid, room.name):
                                _room.own_nick = stanza.getNick()
                    user.change_nick(stanza.getNick())
                    self.add_message_to_room(room, _('%(old)s is now known as %(new)s') % {'old':from_nick, 'new':stanza.getNick()})
                    # rename the private tabs if needed
                    private_room = self.get_room_by_name(stanza.getFrom())
                    if private_room:
                        self.add_message_to_room(private_room, _('%(old_nick)s is now known as %(new_nick)s') % {'old_nick':from_nick, 'new_nick':stanza.getNick()})
                        new_jid = private_room.name.split('/')[0]+'/'+stanza.getNick()
                        private_room.jid = new_jid
                        private_room.name = new_jid

                # kick
                elif kick:
                    room.users.remove(user)
                    try:
                        reason = stanza.getReason().encode('utf-8')
                    except:
                        reason = ''
                    try:
                        by = stanza.getActor().encode('utf-8')
                    except:
                        by = None
                    if from_nick == room.own_nick: # we are kicked
                        room.disconnect()
                        if by:
                            self.add_message_to_room(room,  _("You have been kicked by %(by)s. Reason: %(reason)s") % {'by':by, 'reason':reason})
                        else:
                            self.add_message_to_room(room, _("You have been kicked. Reason: %s") % (reason.encode('utf-8')))
                    else:
                        if by:
                            self.add_message_to_room(room, _("%(nick)s has been kicked by %(by)s. Reason: %(reason)s") % {'nick':from_nick, 'by':by, 'reason':reason})
                        else:
                            self.add_message_to_room(room, _("%(nick)s has been kicked. Reason: %(reason)s") % {'nick':from_nick, 'reason':reason})
                # user quit
                elif status == 'offline' or role == 'none':
                    room.users.remove(user)
                    hide_exit_join = config.get('hide_exit_join', -1) if config.get('hide_exit_join', -1) >= -1 else -1
                    if hide_exit_join == -1 or user.has_talked_since(hide_exit_join):
                        self.add_message_to_room(room, _('%s has left the room') % (from_nick))
                    private_room = self.get_room_by_name(stanza.getFrom())
                    if private_room:
                        self.add_message_to_room(private_room, _('%s has left the room') % (from_nick))
                # status change
                else:
                    # build the message
                    msg = _('%s changed his/her status: ')% from_nick
                    if affiliation != user.affiliation:
                        msg += _('affiliation: %s,') % affiliation
                    if role != user.role:
                        msg += _('role: %s,') % role
                    if show != user.show:
                        msg += _('show: %s,') % show
                    if status != user.status:
                        msg += _('status: %s,') % status
                    msg = msg[:-1] # remove the last ","
                    hide_status_change = config.get('hide_status_change', -1) if config.get('hide_status_change', -1) >= -1 else -1
                    if (hide_status_change == -1 or \
                            user.has_talked_since(hide_status_change) or\
                            user.nick == room.own_nick)\
                            and\
                            (affiliation != user.affiliation or\
                                role != user.role or\
                                show != user.show or\
                                status != user.status):
                        # display the message in the room
                        self.add_message_to_room(room, msg)
                    private_room = self.get_room_by_name(stanza.getFrom())
                    if private_room: # display the message in private
                        self.add_message_to_room(private_room, msg)
                    # finally, effectively change the user status
                    user.update(affiliation, show, status, role)
            if room == self.current_room():
                self.window.user_win.refresh(room.users)
        self.window.input.refresh()
        doupdate()

    def add_message_to_room(self, room, txt, time=None, nickname=None):
        """
        Add the message to the room and refresh the associated component
        of the interface
        """
        room.add_message(txt, time, nickname)
        if room == self.current_room():
            self.window.text_win.refresh(room)
        else:
            self.window.info_win.refresh(self.rooms, self.current_room())
        self.window.input.refresh()

    def execute(self):
        """
        Execute the /command or just send the line on the current room
        """
        line = self.window.input.get_text()
        self.window.input.clear_text()
        self.window.input.refresh()
        if line == "":
            return
        if line.startswith('/') and not line.startswith('/me '):
            command = line.strip()[:].split()[0][1:]
            args = line.strip()[:].split()[1:]
            if command in self.commands.keys():
                func = self.commands[command][0]
                func(args)
                return
            else:
                self.add_message_to_room(self.current_room(), _("Error: unknown command (%s)") % (command))
        elif self.current_room().name != 'Info':
            if self.current_room().jid is not None:
                self.muc.send_private_message(self.current_room().name, line)
                self.add_message_to_room(self.current_room(), line.decode('utf-8'), None, self.current_room().own_nick)
            else:
                self.muc.send_message(self.current_room().name, line)
        self.window.input.refresh()
        doupdate()

    def command_help(self, args):
        """
        /help <command_name>
        """
        room = self.current_room()
        if len(args) == 0:
            msg = _('Available commands are: ')
            for command in self.commands.keys():
                msg += "%s " % command
            msg += _("\nType /help <command_name> to know what each command does")
        if len(args) == 1:
            if args[0] in self.commands.keys():
                msg = self.commands[args[0]][1]
            else:
                msg = _('Unknown command: %s') % args[0]
        self.add_message_to_room(room, msg)

    def command_win(self, args):
        """
        /win <number>
        """
        if len(args) != 1:
            self.command_help(['win'])
            return
        try:
            nb = int(args[0])
        except ValueError:
            self.command_help(['win'])
            return
        if self.current_room().nb == nb:
            return
        self.current_room().set_color_state(11)
        start = self.current_room()
        self.rooms.append(self.rooms.pop(0))
        while self.current_room().nb != nb:
            self.rooms.append(self.rooms.pop(0))
            if self.current_room() == start:
                self.window.refresh(self.rooms)
                return
        self.window.refresh(self.rooms)

    def command_kick(self, args):
        """
        /kick <nick> [reason]
        """
        if len(args) < 1:
            self.command_help(['kick'])
            return
        nick = args[0]
        if len(args) >= 2:
            reason = ' '.join(args[1:])
        else:
            reason = ''
        if self.current_room().name == 'Info' or not self.current_room().joined:
            return
        roomname = self.current_room().name
        self.muc.eject_user(roomname, 'kick', nick, reason)

    def command_join(self, args):
        """
        /join [room][/nick] [password]
        """
        password = None
        if len(args) == 0:
            r = self.current_room()
            if r.name == 'Info':
                return
            room = r.name
            nick = r.own_nick
        else:
            info = args[0].split('/')
            if len(info) == 1:
                default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
                nick = config.get('default_nick', '')
                if nick == '':
                    nick = default
            else:
                nick = info[1]
            if info[0] == '':   # happens with /join /nickname, which is OK
                r = self.current_room()
                if r.name == 'Info':
                    return
                room = r.name
                if nick == '':
                    nick = r.own_nick
            else:
                room = info[0]
            if not is_jid(room): # no server is provided, like "/join hello"
                # use the server of the current room if available
                # check if the current room's name has a server
                if is_jid(self.current_room().name):
                    room += '@%s' % jid_get_domain(self.current_room().name)
                else:           # no server could be found, print a message and return
                    self.information(_("You didn't specify a server for the room you want to join"))
                    return
            r = self.get_room_by_name(room)
        if len(args) == 2:       # a password is provided
            password = args[1]
        if r and r.joined:       # if we are already in the room
            self.information(_("already in room [%s]") % room)
            return
        self.muc.join_room(room, nick, password)
        if not r:   # if the room window exists, we don't recreate it.
            self.join_room(room, nick)
        else:
            # r.own_nick = nick
            r.users = []

    def command_bookmark(self, args):
        """
        /bookmark [room][/nick]
        """
        nick = None
        if len(args) == 0:
            room = self.current_room()
            if room.name == 'Info':
                return
            roomname = room.name
            if room.joined:
                nick = room.own_nick
        else:
            info = args[0].split('/')
            if len(info) == 2:
                nick = info[1]
            roomname = info[0]
            if roomname == '':
                roomname = self.current_room().name
        if nick:
            res = roomname+'/'+nick
        else:
            res = roomname
        bookmarked = config.get('rooms', '')
        # check if the room is already bookmarked.
        # if yes, replace it (i.e., update the associated nick)
        bookmarked = bookmarked.split(':')
        for room in bookmarked:
            if room.split('/')[0] == roomname:
                bookmarked.remove(room)
                break
        bookmarked = ':'.join(bookmarked)
        config.set_and_save('rooms', bookmarked+':'+res)

    def command_set(self, args):
        """
        /set <option> [value]
        """
        if len(args) != 2 and len(args) != 1:
            self.command_help(['set'])
            return
        option = args[0]
        if len(args) == 2:
            value = args[1]
        else:
            value = ''
        config.set_and_save(option, value)
        msg = "%s=%s" % (option, value)
        room = self.current_room()
        self.add_message_to_room(room, msg)

    def command_show(self, args):
        """
        /show <status> [msg]
        """
        possible_show = {'avail':'None',
                         'available':'None',
                         'ok':'None',
                         'here':'None',
                         'chat':'chat',
                         'away':'away',
                         'afk':'away',
                         'dnd':'dnd',
                         'busy':'dnd',
                         'xa':'xa'
                         }
        if len(args) < 1:
            return
        if not args[0] in possible_show.keys():
            self.command_help(['show'])
            return
        show = possible_show[args[0]]
        if len(args) > 1:
            msg = ' '.join(args[1:])
        else:
            msg = None
        for room in self.rooms:
            if room.joined:
                self.muc.change_show(room.name, room.own_nick, show, msg)

    def command_ignore(self, args):
        """
        /ignore <nick>
        """
        if len(args) != 1:
            self.command_help(['ignore'])
            return
        if self.current_room().name == 'Info' or not self.current_room().joined:
            return
        roomname = self.current_room().name
        nick = args[0]
        if not self.ignores.has_key(roomname):
            self.ignores[roomname] = set() # no need for any order
        if nick not in self.ignores[roomname]:
            self.ignores[roomname].add(nick)
            self.add_message_to_room(self.current_room(), _("%s is now ignored") % nick)
        else:
            self.add_message_to_room(self.current_room(), _("%s is already ignored") % nick)

    def command_unignore(self, args):
        """
        /unignore <nick>
        """
        if len(args) != 1:
            self.command_help(['unignore'])
            return
        if self.current_room().name == 'Info' or not self.current_room().joined:
            return
        roomname = self.current_room().name
        nick = args[0]
        if not self.ignores.has_key(roomname) or (nick not in self.ignores[roomname]):
            self.add_message_to_room(self.current_room(), _("%s was not ignored") % nick)
            return
        self.ignores[roomname].remove(nick)
        if self.ignores[roomname] == set():
            del self.ignores[roomname]
        self.add_message_to_room(self.current_room(), _("%s is now unignored") % nick)

    def command_away(self, args):
        """
        /away [msg]
        """
        args.insert(0, 'away')
        self.command_show(args)

    def command_busy(self, args):
        """
        /busy [msg]
        """
        args.insert(0, 'busy')
        self.command_show(args)

    def command_avail(self, args):
        """
        /avail [msg]
        """
        args.insert(0, 'available')
        self.command_show(args)

    def command_part(self, args):
        """
        /part [msg]
        """
        reason = None
        room = self.current_room()
        if room.name == 'Info':
            return
        if len(args):
            msg = ' '.join(args)
        else:
            msg = None
        if room.joined:
            self.muc.quit_room(room.name, room.own_nick, msg)
        self.rooms.remove(self.current_room())
        self.window.refresh(self.rooms)

    def command_unquery(self, args):
        """
        /unquery
        """
        room = self.current_room()
        if room.jid is not None:
            self.rooms.remove(room)
            self.window.refresh(self.rooms)

    def command_query(self, args):
        """
        /query <nick> [message]
        """
        if len(args) < 1:
            return
        nick = args[0]
        room = self.current_room()
        if room.name == "Info" or room.jid is not None:
            return
        for user in room.users:
            if user.nick == nick:
                r = self.open_private_window(room.name, user.nick)
        if room and len(args) > 1:
            msg = ' '.join(args[1:])
            self.muc.send_private_message(r.name, msg)
            self.add_message_to_room(r, msg.decode('utf-8'), None, r.own_nick)

    def command_topic(self, args):
        """
        /topic [new topic]
        """
        room = self.current_room()
        if len(args) == 0:
            self.add_message_to_room(room, _("The subject of the room is: %s") % room.topic.decode('utf-8'))
        subject = ' '.join(args)
        if not room.joined or room.name == "Info":
            return
        self.muc.change_subject(room.name, subject)

    def command_nick(self, args):
        """
        /nick <nickname>
        """
        if len(args) != 1:
            return
        nick = args[0]
        room = self.current_room()
        if not room.joined or room.name == "Info":
            return
        self.muc.change_nick(room.name, nick)

    def information(self, msg):
        """
        Displays an informational message in the "Info" room window
        """
        room = self.get_room_by_name("Info")
        self.add_message_to_room(room, msg)
        self.window.input.refresh()

    def command_quit(self, args):
        """
        /quit
        """
        if len(args):
            msg = ' '.join(args)
        else:
            msg = None
        if msg:
            self.muc.disconnect(self.rooms, msg)
            sleep(0.2)          # :(
	self.reset_curses()
        sys.exit()
