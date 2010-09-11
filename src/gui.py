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

import os
import re
import sys
import shlex
import curses
import webbrowser

from datetime import datetime

import common
import theme

import multiuserchat as muc
from handler import Handler
from config import config
from window import Window
from user import User
from room import Room
from message import Message
from keyboard import read_char
from common import is_jid_the_same, jid_get_domain, jid_get_resource, is_jid

# http://xmpp.org/extensions/xep-0045.html#errorstatus
ERROR_AND_STATUS_CODES = {
    '401': 'A password is required',
    '403': 'You are banned from the room',
    '404': 'The room does\'nt exist',
    '405': 'Your are not allowed to create a new room',
    '406': 'A reserved nick must be used',
    '407': 'You are not in the member list',
    '409': 'This nickname is already in use or has been reserved',
    '503': 'The maximum number of users has been reached',
    }

SHOW_NAME = {
    'dnd': _('busy'),
    'away': _('away'),
    'xa': _('not available'),
    'chat': _('chatty'),
    '': _('available')
    }
def doupdate():
    curses.doupdate()

class Gui(object):
    """
    User interface using ncurses
    """
    def __init__(self, xmpp):
        self.stdscr = curses.initscr()
        self.init_curses(self.stdscr)
        self.xmpp = xmpp
        self.window = Window(self.stdscr)
        self.rooms = [Room('Info', '', self.window)]
        self.ignores = {}

        self.commands = {
            'help': (self.command_help, '\_o< KOIN KOIN KOIN'),
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
            'link': (self.command_link, _("Usage: /link [option] [number]\nLink: Interact with a link in the conversation. Available options are 'open', 'copy'. Open just opens the link in the browser if it's http://, Copy just copy the link in the clipboard. An optional number can be provided, it indicates which link to interact with.")),
            'query': (self.command_query, _('Usage: /query <nick> [message]\nQuery: Open a private conversation with <nick>. This nick has to be present in the room you\'re currently in. If you specified a message after the nickname, it will immediately be sent to this user')),
            'nick': (self.command_nick, _("Usage: /nick <nickname>\nNick: Change your nickname in the current room")),
            'say': (self.command_say, _('Usage: /say <message>\nSay: Just send the message. Useful if you want your message to begin with a "/"')),
            'whois': (self.command_whois, _('Usage: /whois <nickname>\nWhois: Request many informations about the user.')),
            'theme': (self.command_theme, _('Usage: /theme\nTheme: Reload the theme defined in the config file.')),
            }

        self.key_func = {
            "KEY_LEFT": self.window.input.key_left,
            "M-D": self.window.input.key_left,
            "KEY_RIGHT": self.window.input.key_right,
            "M-C": self.window.input.key_right,
            "KEY_UP": self.window.input.key_up,
            "M-A": self.window.input.key_up,
            "KEY_END": self.window.input.key_end,
            "KEY_HOME": self.window.input.key_home,
            "KEY_DOWN": self.window.input.key_down,
            "M-B": self.window.input.key_down,
            "KEY_PPAGE": self.scroll_page_up,
            "KEY_NPAGE": self.scroll_page_down,
            "KEY_DC": self.window.input.key_dc,
            "KEY_F(5)": self.rotate_rooms_left,
            "^P": self.rotate_rooms_left,
            "KEY_F(6)": self.rotate_rooms_right,
            "^N": self.rotate_rooms_right,
            "\t": self.completion,
            "^I": self.completion,
            "KEY_BTAB": self.last_words_completion,
            "KEY_RESIZE": self.resize_window,
            "KEY_BACKSPACE": self.window.input.key_backspace,
            '^?': self.window.input.key_backspace,
            '^J': self.execute,
            '\n': self.execute,
            '^D': self.window.input.key_dc,
            '^W': self.window.input.delete_word,
            '^K': self.window.input.delete_end_of_line,
            '^U': self.window.input.delete_begining_of_line,
            '^Y': self.window.input.paste_clipboard,
            '^A': self.window.input.key_home,
            '^E': self.window.input.key_end,
            'M-f': self.window.input.jump_word_right,
            '^X': self.go_to_important_room,
            'M-b': self.window.input.jump_word_left
            }

        # Add handlers
        self.xmpp.add_event_handler("session_start", self.on_connected)
        self.xmpp.add_event_handler("groupchat_presence", self.on_groupchat_presence)
        self.xmpp.add_event_handler("groupchat_message", self.on_groupchat_message)
        self.xmpp.add_event_handler("message", self.on_message)
        self.xmpp.add_event_handler("presence", self.on_presence)
        self.xmpp.add_event_handler("roster_update", self.on_roster_update)
        # self.handler = Handler()
        # self.handler.connect('on-connected', self.on_connected)
        # self.handler.connect('join-room', self.join_room)
        # self.handler.connect('room-presence', self.room_presence)
        # self.handler.connect('room-message', self.room_message)
        # self.handler.connect('private-message', self.private_message)
        # self.handler.connect('error-message', self.room_error)
        # self.handler.connect('error', self.information)

    def on_connected(self, event):
        """
        Called when we are connected and authenticated
        """
        self.information(_("Welcome on Poezio \o/!"))
        self.information(_("Your JID is %s") % self.xmpp.fulljid)

        if not self.xmpp.anon:
            # request the roster
            self.xmpp.getRoster()
            # send initial presence
            self.xmpp.makePresence(pfrom=self.xmpp.jid).send()
        rooms = config.get('rooms', '')
        if rooms == '' or not isinstance(rooms, str):
            return
        rooms = rooms.split(':')
        for room in rooms:
            args = room.split('/')
            if args[0] == '':
                return
            roomname = args[0]
            if len(args) == 2:
                nick = args[1]
            else:
                default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
                nick = config.get('default_nick', '')
                if nick == '':
                    nick = default
            self.open_new_room(roomname, nick)
            muc.join_groupchat(self.xmpp, roomname, nick)
        # if not self.xmpp.anon:
        # Todo: SEND VCARD
        return
        if config.get('jid', '') == '': # Don't send the vcard if we're not anonymous
            self.vcard_sender.start()   # because the user ALREADY has one on the server

    def on_groupchat_presence(self, presence):
        """
        Triggered whenever a presence stanza is received from a user in a multi-user chat room.
        Display the presence on the room window and update the
        presence information of the concerned user
        """
        from_nick = presence['from'].resource
        from_room = presence['from'].bare
        room = self.get_room_by_name(from_room)
        code = presence.find('{jabber:client}status')
        status_codes = set([s.attrib['code'] for s in presence.findall('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}status')])
        # Check if it's not an error presence.
        if presence['type'] == 'error':
            return self.room_error(presence, from_room)
        if not room:
            return
        msg = None
        affiliation = presence['muc']['affiliation']
        show = presence['show']
        status = presence['status']
        role = presence['muc']['role']
        jid = presence['muc']['jid']
        typ = presence['type']
        if not room.joined:     # user in the room BEFORE us.
            # ignore redondant presence message, see bug #1509
            if from_nick not in [user.nick for user in room.users]:
                new_user = User(from_nick, affiliation, show, status, role)
                room.users.append(new_user)
                if from_nick == room.own_nick:
                    room.joined = True
                    new_user.color = theme.COLOR_OWN_NICK
                    self.add_message_to_room(room, _("Your nickname is %s") % (from_nick))
                    if '170' in status_codes:
                        self.add_message_to_room(room, 'Warning: this room is publicly logged')
        else:
            change_nick = '303' in status_codes
            kick = '307' in status_codes and typ == 'unavailable'
            user = room.get_user_by_name(from_nick)
            # New user
            if not user:
                self.on_user_join(room, from_nick, affiliation, show, status, role, jid)
            # nick change
            elif change_nick:
                self.on_user_nick_change(room, presence, user, from_nick, from_room)
            # kick
            elif kick:
                self.on_user_kicked(room, presence, user, from_nick)
            # user quit
            elif typ == 'unavailable':
                self.on_user_leave_groupchat(room, user, jid, status, from_nick, from_room)
            # status change
            else:
                self.on_user_change_status(room, user, from_nick, from_room, affiliation, role, show, status)
        if room == self.current_room():
            self.window.user_win.refresh(room.users)
        self.window.input.refresh()
        doupdate()

    def on_user_join(self, room, from_nick, affiliation, show, status, role, jid):
        """
        When a new user joins a groupchat
        """
        room.users.append(User(from_nick, affiliation,
                               show, status, role))
        hide_exit_join = config.get('hide_exit_join', -1)
        if hide_exit_join != 0:
            if not jid.full:
                self.add_message_to_room(room, _("%(spec)s [%(nick)s] joined the room") % {'nick':from_nick, 'spec':theme.CHAR_JOIN}, colorized=True)
            else:
                self.add_message_to_room(room, _("%(spec)s [%(nick)s] (%(jid)s) joined the room") % {'spec':theme.CHAR_JOIN, 'nick':from_nick, 'jid':jid.full}, colorized=True)

    def on_user_nick_change(self, room, presence, user, from_nick, from_room):
        new_nick = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item').attrib['nick']
        if user.nick == room.own_nick:
            room.own_nick = new_nick
            # also change our nick in all private discussion of this room
            for _room in self.rooms:
                if _room.jid is not None and is_jid_the_same(_room.jid, room.name):
                    _room.own_nick = new_nick
        user.change_nick(new_nick)
        self.add_message_to_room(room, _('[%(old)s] is now known as [%(new)s]') % {'old':from_nick, 'new':new_nick}, colorized=True)
        # rename the private tabs if needed
        private_room = self.get_room_by_name('%s/%s' % (from_room, from_nick))
        if private_room:
            self.add_message_to_room(private_room, _('[%(old_nick)s] is now known as [%(new_nick)s]') % {'old_nick':from_nick, 'new_nick':new_nick}, colorized=True)
            new_jid = private_room.name.split('/')[0]+'/'+new_nick
            private_room.jid = private_room.name = new_jid

    def on_user_kicked(self, room, presence, user, from_nick):
        """
        When someone is kicked
        """
        room.users.remove(user)
        by = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item/{http://jabber.org/protocol/muc#user}actor')
        reason = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item/{http://jabber.org/protocol/muc#user}reason')
        by = by.attrib['jid'] if by else ''
        reason = reason.text# if reason else ''
        if from_nick == room.own_nick: # we are kicked
            room.disconnect()
            if by:
                kick_msg = _("%(spec) [You] have been kicked by [%(by)s].") % {'spec': theme.CHAR_KICK, 'by':by}
            else:
                kick_msg = _("%(spec)s [You] have been kicked.") % {'spec':theme.CHAR_KICK}
            # try to auto-rejoin
            if config.get('autorejoin', 'false') == 'true':
                muc.join_groupchat(self.xmpp, room.name, room.own_nick)
        else:
            if by:
                kick_msg = _("%(spec)s [%(nick)s] has been kicked by %(by)s.") % {'spec':theme.CHAR_KICK, 'nick':from_nick, 'by':by}
            else:
                kick_msg = _("%(spec)s [%(nick)s] has been kicked") % {'spec':theme.CHAR_KICK, 'nick':from_nick}
        if reason:
            kick_msg += _(' Reason: %(reason)s') % {'reason': reason}
        self.add_message_to_room(room, kick_msg, colorized=True)

    def on_user_leave_groupchat(self, room, user, jid, status, from_nick, from_room):
        """
        When an user leaves a groupchat
        """
        room.users.remove(user)
        hide_exit_join = config.get('hide_exit_join', -1) if config.get('hide_exit_join', -1) >= -1 else -1
        if hide_exit_join == -1 or user.has_talked_since(hide_exit_join):
            if not jid.full:
                leave_msg = _('%(spec)s [%(nick)s] has left the room') % {'nick':from_nick, 'spec':theme.CHAR_QUIT}
            else:
                leave_msg = _('%(spec)s [%(nick)s] (%(jid)s) has left the room') % {'spec':theme.CHAR_QUIT, 'nick':from_nick, 'jid':jid.full}
            if status:
                leave_msg += ' (%s)' % status
            self.add_message_to_room(room, leave_msg, colorized=True)
        private_room = self.get_room_by_name('%s/%s' % (from_room, from_nick))
        if private_room:
            if not status:
                self.add_message_to_room(private_room, _('%(spec)s [%(nick)s] has left the room') % {'nick':from_nick, 'spec':theme.CHAR_QUIT}, colorized=True)
            else:
                self.add_message_to_room(private_room, _('%(spec)s [%(nick)s] has left the room (%(status)s)') % {'nick':from_nick, 'spec':theme.CHAR_QUIT, 'status': status}, colorized=True)

    def on_user_change_status(self, room, user, from_nick, from_room, affiliation, role, show, status):
        """
        When an user changes her status
        """
        # build the message
        msg = _('%s changed his/her status: ')% from_nick
        if affiliation != user.affiliation:
            msg += _('affiliation: %s,') % affiliation
        if role != user.role:
            msg += _('role: %s,') % role
        if show != user.show and show in list(SHOW_NAME.keys()):
            msg += _('show: %s,') % SHOW_NAME[show]
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
        private_room = self.get_room_by_name('%s/%s' % (from_room, from_nick))
        if private_room: # display the message in private
            self.add_message_to_room(private_room, msg)
        # finally, effectively change the user status
        user.update(affiliation, show, status, role)

    def on_message(self, message):
        """
        When receiving private message from a muc OR a normal message
        (from one of our contacts)
        """
        from common import debug
#        debug('message: %s\n' % message)
        if message['type'] == 'groupchat':
            return None
        # Differentiate both type of messages, and call the appropriate handler.
        jid_from = message['from']
        for room in self.rooms:
            if room.jid is None and room.name == jid_from.bare: # check all the MUC we are in
                if message['type'] == 'error':
                    return self.room_error(message, room.name)
                else:
                    return self.on_groupchat_private_message(message)
        return self.on_normal_message(message)

    def on_groupchat_private_message(self, message):
        """
        We received a Private Message (from someone in a Muc)
        """
        jid = message['from']
        nick_from = jid.resource
        room_from = jid.bare
        room = self.get_room_by_name(jid.full) # get the tab with the private conversation
        if not room: # It's the first message we receive: create the tab
            room = self.open_private_window(room_from, nick_from, False)
            if not room:
                return
        body = message['body']
        self.add_message_to_room(room, body, None, nick_from)
        self.window.input.refresh()
        doupdate()

    def on_normal_message(self, message):
        """
        When receiving "normal" messages (from someone in our roster)
        """
        from common import debug
#        debug('MESSAGE: %s\n' % (presence))

        return

    def on_presence(self, presence):
        """
        """
        from common import debug
#        debug('PRESEEEEEEEEENCE: %s\n' % (presence))
        return

    def on_roster_update(self, iq):
        """
        A subscription changed, or we received a roster item
        after a roster request, etc
        """
        from common import debug
#        debug("UPDATE: %s\n" % (iq))
        for subscriber in iq['roster']['items']:
            debug("subscriber: %s\n" % (iq['roster']['items'][subscriber]['subscription']))

    def resize_window(self):
        """
        Resize the whole screen
        """
        self.window.resize(self.stdscr)
        self.window.refresh(self.rooms)

    def main_loop(self):
        """
        main loop waiting for the user to press a key
        """
        self.refresh_window()
        while True:
            doupdate()
            char=read_char(self.stdscr)
            # search for keyboard shortcut
            if char in list(self.key_func.keys()):
                self.key_func[char]()
            else:
                if not char or len(char) > 1:
                    continue    # ignore non-handled keyboard shortcuts
                self.window.do_command(char)

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
        theme.init_colors()
        curses.noecho()
        curses.curs_set(0)
        stdscr.keypad(True)

    def reset_curses(self):
        """
        Reset terminal capabilities to what they were before ncurses
        init
        """
        # TODO remove me?
        curses.echo()
        curses.nocbreak()
        curses.endwin()

    def refresh_window(self):
        """
        Refresh everything
        """
        self.current_room().set_color_state(theme.COLOR_TAB_CURRENT)
        self.window.refresh(self.rooms)

    def open_new_room(self, room, nick, focus=True):
        """
        Open a new Tab containing a Muc room, using the specified nick
        """
        r = Room(room, nick, self.window)
        self.current_room().set_color_state(theme.COLOR_TAB_NORMAL)
        if self.current_room().nb == 0:
            self.rooms.append(r)
        else:
            for ro in self.rooms:
                if ro.nb == 0:
                    self.rooms.insert(self.rooms.index(ro), r)
                    break
        if focus:
            self.command_win("%s" % r.nb)
        self.refresh_window()

    def completion(self):
        """
        Called when Tab is pressed, complete the nickname in the input
        """
        compare_users = lambda x: x.last_talked
        self.window.input.auto_completion([user.nick for user in sorted(self.current_room().users, key=compare_users, reverse=True)])

    def last_words_completion(self):
        """
        Complete the input with words recently said
        """
        # build the list of the recent words
        char_we_dont_want = [',', '(', ')', '.']
        words = list()
        for msg in self.current_room().messages[:-9:-1]:
            if not msg:
                continue
            for word in msg.txt.split():
                for char in char_we_dont_want: # remove the chars we don't want
                    word = word.replace(char, '')
                if len(word) > 5:
                    words.append(word)
        self.window.input.auto_completion(words)

    def go_to_important_room(self):
        """
        Go to the next room with activity, in this order:
        - A personal conversation with a new message
        - A Muc with an highlight
        - A Muc with any new message
        """
        for room in self.rooms:
            if room.color_state == theme.COLOR_TAB_PRIVATE:
                self.command_win('%s' % room.nb)
                return
        for room in self.rooms:
            if room.color_state == theme.COLOR_TAB_HIGHLIGHT:
                self.command_win('%s' % room.nb)
                return
        for room in self.rooms:
            if room.color_state == theme.COLOR_TAB_NEW_MESSAGE:
                self.command_win('%s' % room.nb)
                return

    def rotate_rooms_right(self, args=None):
        """
        rotate the rooms list to the right
        """
        self.current_room().set_color_state(theme.COLOR_TAB_NORMAL)
        self.current_room().remove_line_separator()
        self.rooms.append(self.rooms.pop(0))
        self.current_room().set_color_state(theme.COLOR_TAB_CURRENT)
        self.refresh_window()

    def rotate_rooms_left(self, args=None):
        """
        rotate the rooms list to the right
        """
        self.current_room().set_color_state(theme.COLOR_TAB_NORMAL)
        self.current_room().remove_line_separator()
        self.rooms.insert(0, self.rooms.pop())
        self.current_room().set_color_state(theme.COLOR_TAB_CURRENT)
        self.refresh_window()

    def scroll_page_down(self, args=None):
        self.current_room().scroll_down(self.window.text_win.height-1)
        self.refresh_window()

    def scroll_page_up(self, args=None):
        self.current_room().scroll_up(self.window.text_win.height-1)
        self.refresh_window()

    def room_error(self, error, room_name):
        """
        Display the error on the room window
        """
        from common import debug
#        debug('ERROR: %s\n' % error)
        room = self.get_room_by_name(room_name)
        if not room:
            room = self.get_room_by_name('Info')
        msg = error['error']['type']
        condition = error['error']['condition']
        code = error['error']['code']
        body = error['error']['text']
        if not body:
            if code in list(ERROR_AND_STATUS_CODES.keys()):
                body = ERROR_AND_STATUS_CODES[code]
            else:
                body = condition or _('Unknown error')
        if code:
            self.add_message_to_room(room, _('Error: %(code)s - %(msg)s: %(body)s' %
                                             {'msg':msg, 'body':body, 'code':code}))
        else:
            self.add_message_to_room(room, _('Error: %(msg)s: %(body)s' %
                                             {'msg':msg, 'body':body}))
        if code == '401':
            self.add_message_to_room(room, _('To provide a password in order to join the room, type "/join / password" (replace "password" by the real password)'))
        if code == '409':
            if config.get('alternative_nickname', '') != '':
                self.command_join('%s/%s'% (room.name, room.own_nick+config.get('alternative_nickname', '')))
            else:
                self.add_message_to_room(room, _('You can join the room with an other nick, by typing "/join /other_nick"'))
        self.refresh_window()

    def open_private_window(self, room_name, user_nick, focus=True):
        complete_jid = room_name+'/'+user_nick
        for room in self.rooms: # if the room exists, focus it and return
            if room.jid:
                if room.jid == complete_jid:
                    self.command_win('%s' % room.nb)
                    return
        # create the new tab
        room = self.get_room_by_name(room_name)
        if not room:
            return None
        own_nick = room.own_nick
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
            self.command_win('%s' % (r.nb))
        # self.window.new_room(r)
        self.refresh_window()
        return r

    def on_groupchat_message(self, message):
        """
        Triggered whenever a message is received from a multi-user chat room.
        """
        from common import debug
#        debug('GROUPCHAT message: %s\n' % message)
        delay_tag = message.find('{urn:xmpp:delay}delay')
        if delay_tag is not None:
            delayed = True
            date = common.datetime_tuple(delay_tag.attrib['stamp'])
        else:
            # We support the OLD and deprecated XEP: http://xmpp.org/extensions/xep-0091.html
            # But it sucks, please, Jabber servers, don't do this :(
            delay_tag = message.find('{jabber:x:delay}x')
            if delay_tag is not None:
                delayed = True
                date = common.datetime_tuple(delay_tag.attrib['stamp'])
            else:
                delayed = False
                date = None
        nick_from = message['mucnick']
        room_from = message.getMucroom()
        if message['type'] == 'error': # Check if it's an error
            return self.room_error(message, from_room)
        if nick_from == room_from:
            nick_from = None
        room = self.get_room_by_name(room_from)
        if (room_from in self.ignores) and (nick_from in self.ignores[room_from]):
            return
        room = self.get_room_by_name(room_from)
        if not room:
            self.information(_("message received for a non-existing room: %s") % (room_from))
            return
        body = message['body']
        subject = message['subject']
#        debug('======== %s, %s, %s, %s====\n'% (nick_from, room_from, body, subject))
        if subject:
            if nick_from:
                self.add_message_to_room(room, _("%(nick)s changed the subject to: %(subject)s") % {'nick':nick_from, 'subject':subject}, time=date)
            else:
                self.add_message_to_room(room, _("The subject is: %(subject)s") % {'subject':subject}, time=date)
            room.topic = subject.replace('\n', '|')
            if room == self.current_room():
                self.window.topic_win.refresh(room.topic)
        elif body:
            if body.startswith('/me '):
                self.add_message_to_room(room, "* "+nick_from + ' ' + body[4:], date)
            else:
                date = date if delayed == True else None
                self.add_message_to_room(room, body, date, nick_from)
        self.refresh_window()
        doupdate()


    def add_message_to_room(self, room, txt, time=None, nickname=None, colorized=False):
        """
        Add the message to the room and refresh the associated component
        of the interface
        """
        if room != self.current_room():
            room.add_line_separator()
        room.add_message(txt, time, nickname, colorized)
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
            arg = line[2+len(command):] # jump the '/' and the ' '
            # example. on "/link 0 open", command = "link" and arg = "0 open"
            if command in list(self.commands.keys()):
                func = self.commands[command][0]
                func(arg)
                return
            else:
                self.add_message_to_room(self.current_room(), _("Error: unknown command (%s)") % (command))
        elif self.current_room().name != 'Info':
            if self.current_room().jid is not None:
                muc.send_private_message(self.xmpp, self.current_room().name, line)
                self.add_message_to_room(self.current_room(), line, None, self.current_room().own_nick)
            else:
                muc.send_groupchat_message(self.xmpp, self.current_room().name, line)
        self.window.input.refresh()
        doupdate()

    def command_help(self, arg):
        """
        /help <command_name>
        """
        args = arg.split()
        room = self.current_room()
        if len(args) == 0:
            msg = _('Available commands are: ')
            for command in list(self.commands.keys()):
                msg += "%s " % command
            msg += _("\nType /help <command_name> to know what each command does")
        if len(args) == 1:
            if args[0] in list(self.commands.keys()):
                msg = self.commands[args[0]][1]
            else:
                msg = _('Unknown command: %s') % args[0]
        self.add_message_to_room(room, msg)

    def command_whois(self, arg):
        """
        /whois <nickname>
        """
        # TODO
        return
        # check shlex here
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.add_message_to_room(self.current_room(), _("Error: %s") % (error))
        room = self.current_room()
        if len(args) != 1:
            self.add_message_to_room(room, _('whois command takes exactly one argument'))
            return
        # check if current room is a MUC
        if room.jid or room.name == 'Info':
            return
        nickname = args[0]
        self.muc.request_vcard(room.name, nickname)

    def command_theme(self, arg):
        """
        """
        theme.reload_theme()
        self.resize_window()

    def command_win(self, arg):
        """
        /win <number>
        """
        args = arg.split()
        if len(args) != 1:
            self.command_help('win')
            return
        try:
            nb = int(args[0])
        except ValueError:
            self.command_help('win')
            return
        if self.current_room().nb == nb:
            return
        self.current_room().set_color_state(theme.COLOR_TAB_NORMAL)
        self.current_room().remove_line_separator()
        start = self.current_room()
        self.rooms.append(self.rooms.pop(0))
        while self.current_room().nb != nb:
            self.rooms.append(self.rooms.pop(0))
            if self.current_room() == start:
                self.current_room().set_color_state(theme.COLOR_TAB_CURRENT)
                self.refresh_window()
                return
        self.current_room().set_color_state(theme.COLOR_TAB_CURRENT)
        self.refresh_window()

    def command_kick(self, arg):
        """
        /kick <nick> [reason]
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.add_message_to_room(self.current_room(), _("Error: %s") % (error))
        if len(args) < 1:
            self.command_help('kick')
            return
        nick = args[0]
        if len(args) >= 2:
            reason = ' '.join(args[1:])
        else:
            reason = ''
        if self.current_room().name == 'Info' or not self.current_room().joined:
            return
        roomname = self.current_room().name
        res = muc.eject_user(self.xmpp, roomname, nick, reason)
        if res['type'] == 'error':
            self.room_error(res, roomname)

    def command_say(self, arg):
        """
        /say <message>
        """
        line = arg
        if self.current_room().name != 'Info':
            if self.current_room().jid is not None:
                muc.send_private_message(self.xmpp, self.current_room().name, line)
                self.add_message_to_room(self.current_room(), line, None, self.current_room().own_nick)
            else:
                muc.send_groupchat_message(self.xmpp, self.current_room().name, line)
        self.window.input.refresh()
        doupdate()

    def command_join(self, arg):
        """
        /join [room][/nick] [password]
        """
        args = arg.split()
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
                    self.add_message_to_room(self.current_room(), _("You didn't specify a server for the room you want to join"))
                    return
            r = self.get_room_by_name(room)
        if len(args) == 2:       # a password is provided
            password = args[1]
        if r and r.joined:       # if we are already in the room
            self.command_win('%s' % (r.nb))
            return
        room = room.lower()
        self.xmpp.plugin['xep_0045'].joinMUC(room, nick, password)
        if not r:   # if the room window exists, we don't recreate it.
            self.open_new_room(room, nick)
        else:
            r.own_nick = nick
            r.users = []

    def command_bookmark(self, arg):
        """
        /bookmark [room][/nick]
        """
        args = arg.split()
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
        bookmarks = bookmarked+':'+res
        config.set_and_save('rooms', bookmarks)
        self.add_message_to_room(self.current_room(), _('Your bookmarks are now: %s') % bookmarks)

    def command_set(self, arg):
        """
        /set <option> [value]
        """
        args = arg.split()
        if len(args) != 2 and len(args) != 1:
            self.command_help('set')
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

    def command_show(self, arg):
        """
        /show <status> [msg]
        """
        args = arg.split()
        possible_show = {'avail':None,
                         'available':None,
                         'ok':None,
                         'here':None,
                         'chat':'chat',
                         'away':'away',
                         'afk':'away',
                         'dnd':'dnd',
                         'busy':'dnd',
                         'xa':'xa'
                         }
        if len(args) < 1:
            return
        if not args[0] in list(possible_show.keys()):
            self.command_help('show')
            return
        show = possible_show[args[0]]
        if len(args) > 1:
            msg = ' '.join(args[1:])
        else:
            msg = None
        for room in self.rooms:
            if room.joined:
                muc.change_show(self.xmpp, room.name, room.own_nick, show, msg)

    def command_ignore(self, arg):
        """
        /ignore <nick>
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.add_message_to_room(self.current_room(), _("Error: %s") % (error))
        if len(args) != 1:
            self.command_help('ignore')
            return
        if self.current_room().name == 'Info' or not self.current_room().joined:
            return
        roomname = self.current_room().name
        nick = args[0]
        if roomname not in self.ignores:
            self.ignores[roomname] = set() # no need for any order
        if nick not in self.ignores[roomname]:
            self.ignores[roomname].add(nick)
            self.add_message_to_room(self.current_room(), _("%s is now ignored") % nick)
        else:
            self.add_message_to_room(self.current_room(), _("%s is already ignored") % nick)

    def command_unignore(self, arg):
        """
        /unignore <nick>
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.add_message_to_room(self.current_room(), _("Error: %s") % (error))
        if len(args) != 1:
            self.command_help('unignore')
            return
        if self.current_room().name == 'Info' or not self.current_room().joined:
            return
        roomname = self.current_room().name
        nick = args[0]
        if roomname not in self.ignores or (nick not in self.ignores[roomname]):
            self.add_message_to_room(self.current_room(), _("%s was not ignored") % nick)
            return
        self.ignores[roomname].remove(nick)
        if self.ignores[roomname] == set():
            del self.ignores[roomname]
        self.add_message_to_room(self.current_room(), _("%s is now unignored") % nick)

    def command_away(self, arg):
        """
        /away [msg]
        """
        self.command_show("away "+arg)

    def command_busy(self, arg):
        """
        /busy [msg]
        """
        self.command_show("busy "+arg)

    def command_avail(self, arg):
        """
        /avail [msg]
        """
        self.command_show("available "+arg)

    def command_part(self, arg):
        """
        /part [msg]
        """
        args = arg.split()
        reason = None
        room = self.current_room()
        if room.name == 'Info':
            return
        if len(args):
            msg = ' '.join(args)
        else:
            msg = None
        if room.joined:
            muc.leave_groupchat(self.xmpp, room.name, room.own_nick, arg)
        self.rooms.remove(self.current_room())
        self.refresh_window()

    def command_unquery(self, arg):
        """
        /unquery
        """
        room = self.current_room()
        if room.jid is not None:
            self.rooms.remove(room)
            self.refresh_window()

    def command_query(self, arg):
        """
        /query <nick> [message]
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.add_message_to_room(self.current_room(), _("Error: %s") % (error))
        if len(args) < 1:
            return
        nick = args[0]
        room = self.current_room()
        if room.name == "Info" or room.jid is not None:
            return
        r = None
        for user in room.users:
            if user.nick == nick:
                r = self.open_private_window(room.name, user.nick)
        if r and len(args) > 1:
            msg = arg[len(nick)+1:]
            muc.send_private_message(self.xmpp, r.name, msg)
            self.add_message_to_room(r, msg, None, r.own_nick)

    def command_topic(self, arg):
        """
        /topic [new topic]
        """
        room = self.current_room()
        if not arg.strip():
            self.add_message_to_room(room, _("The subject of the room is: %s") % room.topic)
            return
        subject = arg
        if not room.joined or room.name == "Info" and not room.jid:
            return
        muc.change_subject(self.xmpp, room.name, subject)

    def command_link(self, arg):
        """
        /link <option> <nb>
        Opens the link in a browser, or join the room, or add the JID, or
        copy it in the clipboard
        """
        args = arg.split()
        if len(args) > 2:
            self.add_message_to_room(self.current_room(),
                                     _("Link: This command takes at most 2 arguments"))
            return
        # set the default parameters
        option = "open"
        nb = 0
        # check the provided parameters
        if len(args) >= 1:
            try:  # check if the argument is the number
                nb = int(args[0])
            except ValueError:  # nope, it's the option
                option = args[0]
        if len(args) == 2:
            try:
                nb = int(args[0])
            except ValueError:
                self.add_message_to_room(self.current_room(),
                                         _("Link: 2nd parameter should be a number"))
                return
        # find the nb-th link in the current buffer
        i = 0
        link = None
        for msg in self.current_room().messages[:-200:-1]:
            if not msg:
                continue
            matches = re.findall('"((ftp|http|https|gopher|mailto|news|nntp|telnet|wais|file|prospero|aim|webcal):(([A-Za-z0-9$_.+!*(),;/?:@&~=-])|%[A-Fa-f0-9]{2}){2,}(#([a-zA-Z0-9][a-zA-Z0-9$_.+!*(),;/?:@&~=%-]*))?([A-Za-z0-9$_+!*();/?:~-]))"', msg.txt)
            for m in matches:
                if i == nb:
                    url = m[0]
                    self.link_open(url)
                    return

    def url_open(self, url):
        """
        Use webbrowser to open the provided link
        """
        webbrowser.open(url)

    def command_nick(self, arg):
        """
        /nick <nickname>
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.add_message_to_room(self.current_room(), _("Error: %s") % (error))
        if len(args) != 1:
            return
        nick = args[0]
        room = self.current_room()
        if not room.joined or room.name == "Info":
            return
        muc.change_nick(self.xmpp, room.name, nick)

    def information(self, msg):
        """
        Displays an informational message in the "Info" room window
        """
        room = self.get_room_by_name("Info")
        self.add_message_to_room(room, msg)
        self.window.input.refresh()

    def command_quit(self, arg):
        """
        /quit
        """
        if len(arg.strip()) != 0:
            msg = arg
        else:
            msg = None
        for room in self.rooms:
            if not room.jid and room.name != 'Info':
                muc.leave_groupchat(self.xmpp, room.name, room.own_nick, msg)
        self.xmpp.disconnect()
        self.reset_curses()
        sys.exit()
