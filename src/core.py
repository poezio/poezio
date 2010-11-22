# Copyright 2010 Le Coz Florent <louiz@louiz.org>
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
import threading
import webbrowser

from datetime import datetime

import common
import theme
import logging

log = logging.getLogger(__name__)

import multiuserchat as muc
from connection import connection
from config import config
from tab import MucTab, InfoTab, PrivateTab, RosterInfoTab, ConversationTab
from logger import logger
from user import User
from room import Room
from roster import Roster, RosterGroup, roster
from contact import Contact, Resource
from message import Message
from text_buffer import TextBuffer
from keyboard import read_char
from common import jid_get_domain, is_jid

# http://xmpp.org/extensions/xep-0045.html#errorstatus
ERROR_AND_STATUS_CODES = {
    '401': _('A password is required'),
    '403': _('You are banned from the room'),
    '404': _('The room does\'nt exist'),
    '405': _('Your are not allowed to create a new room'),
    '406': _('A reserved nick must be used'),
    '407': _('You are not in the member list'),
    '409': _('This nickname is already in use or has been reserved'),
    '503': _('The maximum number of users has been reached'),
    }

SHOW_NAME = {
    'dnd': _('busy'),
    'away': _('away'),
    'xa': _('not available'),
    'chat': _('chatty'),
    '': _('available')
    }

resize_lock = threading.Lock()

class Core(object):
    """
    User interface using ncurses
    """
    def __init__(self, xmpp):
        self.running = True
        self.stdscr = curses.initscr()
        self.init_curses(self.stdscr)
        self.xmpp = xmpp
        default_tab = InfoTab(self, "Info") if self.xmpp.anon\
            else RosterInfoTab(self)
        default_tab.on_gain_focus()
        self.tabs = [default_tab]
        # self.roster = Roster()
        # a unique buffer used to store global informations
        # that are displayed in almost all tabs, in an
        # information window.
        self.information_buffer = TextBuffer()
        self.information_win_size = 2 # Todo, get this from config
        self.ignores = {}
        self.resize_timer = None
        self.previous_tab_nb = 0
        self.own_nick = config.get('own_nick', self.xmpp.boundjid.bare)
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
            'show': (self.command_show, _("Usage: /show <availability> [status]\nShow: Change your availability and (optionaly) your status. The <availability> argument is one of \"avail, available, ok, here, chat, away, afk, dnd, busy, xa\" and the optional [status] argument will be your status message")),
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
            'recolor': (self.command_recolor, _('Usage: /recolor\nRecolor: Re-assign a color to all participants of the current room, based on the last time they talked. Use this if the participants currently talking have too many identical colors.')),
            }

        self.key_func = {
            "KEY_PPAGE": self.scroll_page_up,
            "KEY_NPAGE": self.scroll_page_down,
            "KEY_F(5)": self.rotate_rooms_left,
            "^P": self.rotate_rooms_left,
            'kLFT3': self.rotate_rooms_left,
            "KEY_F(6)": self.rotate_rooms_right,
            "^N": self.rotate_rooms_right,
            'kRIT3': self.rotate_rooms_right,
            "KEY_F(7)": self.shrink_information_win,
            "KEY_F(8)": self.grow_information_win,
            "KEY_RESIZE": self.call_for_resize,
            'M-e': self.go_to_important_room,
            'M-r': self.go_to_roster,
            'M-z': self.go_to_previous_tab,
            'M-v': self.move_separator,
            }

        # Add handlers
        self.xmpp.add_event_handler("session_start", self.on_connected)
        self.xmpp.add_event_handler("groupchat_presence", self.on_groupchat_presence)
        self.xmpp.add_event_handler("groupchat_message", self.on_groupchat_message)
        self.xmpp.add_event_handler("groupchat_subject", self.on_groupchat_subject)
        self.xmpp.add_event_handler("message", self.on_message)
        self.xmpp.add_event_handler("got_online" , self.on_got_online)
        self.xmpp.add_event_handler("got_offline" , self.on_got_offline)
        self.xmpp.add_event_handler("roster_update", self.on_roster_update)
        self.xmpp.add_event_handler("changed_status", self.on_presence)


    def grow_information_win(self):
        """
        """
        if self.information_win_size == 14:
            return
        self.information_win_size += 1
        for tab in self.tabs:
            tab.on_info_win_size_changed()
        self.refresh_window()

    def shrink_information_win(self):
        """
        """
        if self.information_win_size == 0:
            return
        self.information_win_size -= 1
        for tab in self.tabs:
            tab.on_info_win_size_changed()
        self.refresh_window()

    def on_got_offline(self, presence):
        jid = presence['from']
        contact = roster.get_contact_by_jid(jid.bare)
        if not contact:
            return
        resource = contact.get_resource_by_fulljid(jid.full)
        assert resource
        self.information('%s is offline' % (resource.get_jid()), "Roster")
        contact.remove_resource(resource)
        if isinstance(self.current_tab(), RosterInfoTab):
            self.refresh_window()

    def on_got_online(self, presence):
        jid = presence['from']
        contact = roster.get_contact_by_jid(jid.bare)
        if not contact:
            # Todo, handle presence comming from contacts not in roster
            return
        resource = contact.get_resource_by_fulljid(jid.full)
        assert not resource
        resource = Resource(jid.full)
        status = presence['type']
        status_message = presence['status']
        priority = presence.getPriority() or 0
        resource.set_status(status_message)
        resource.set_presence(status)
        resource.set_priority(priority)
        contact.add_resource(resource)
        self.information("%s is online (%s)" % (resource.get_jid().full, status), "Roster")

    def on_connected(self, event):
        """
        Called when we are connected and authenticated
        """
        self.information(_("Welcome on Poezio \o/!"))
        self.information(_("Your JID is %s") % self.xmpp.boundjid.full)

        if not self.xmpp.anon:
            # request the roster
            self.xmpp.getRoster()
            # send initial presence
            self.xmpp.makePresence().send()
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
            self.open_new_room(roomname, nick, False)
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
                    self.add_message_to_text_buffer(room, _("Your nickname is %s") % (from_nick))
                    if '170' in status_codes:
                        self.add_message_to_text_buffer(room, 'Warning: this room is publicly logged')
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
        self.refresh_window()
        self.doupdate()

    def on_user_join(self, room, from_nick, affiliation, show, status, role, jid):
        """
        When a new user joins a groupchat
        """
        room.users.append(User(from_nick, affiliation,
                               show, status, role))
        hide_exit_join = config.get('hide_exit_join', -1)
        if hide_exit_join != 0:
            if not jid.full:
                self.add_message_to_text_buffer(room, _('%(spec)s "[%(nick)s]" joined the room') % {'nick':from_nick.replace('"', '\\"'), 'spec':theme.CHAR_JOIN.replace('"', '\\"')}, colorized=True)
            else:
                self.add_message_to_text_buffer(room, _('%(spec)s "[%(nick)s]" "(%(jid)s)" joined the room') % {'spec':theme.CHAR_JOIN.replace('"', '\\"'), 'nick':from_nick.replace('"', '\\"'), 'jid':jid.full}, colorized=True)

    def on_user_nick_change(self, room, presence, user, from_nick, from_room):
        new_nick = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item').attrib['nick']
        if user.nick == room.own_nick:
            room.own_nick = new_nick
            # also change our nick in all private discussion of this room
            for _tab in self.tabs:
                if isinstance(_tab, PrivateTab) and _tab.get_name().split('/', 1)[0] == room.name:
                    _tab.get_room().own_nick = new_nick
        user.change_nick(new_nick)
        self.add_message_to_text_buffer(room, _('"[%(old)s]" is now known as "[%(new)s]"') % {'old':from_nick.replace('"', '\\"'), 'new':new_nick.replace('"', '\\"')}, colorized=True)
        # rename the private tabs if needed
        private_room = self.get_room_by_name('%s/%s' % (from_room, from_nick))
        if private_room:
            self.add_message_to_text_buffer(private_room, _('"[%(old_nick)s]" is now known as "[%(new_nick)s]"') % {'old_nick':from_nick.replace('"', '\\"'), 'new_nick':new_nick.replace('"', '\\"')}, colorized=True)
            new_jid = private_room.name.split('/', 1)[0]+'/'+new_nick
            private_room.name = new_jid

    def on_user_kicked(self, room, presence, user, from_nick):
        """
        When someone is kicked
        """
        room.users.remove(user)
        by = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item/{http://jabber.org/protocol/muc#user}actor')
        reason = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item/{http://jabber.org/protocol/muc#user}reason')
        by = by.attrib['jid'] if by is not None else None
        reason = reason.text if reason else ''
        if from_nick == room.own_nick: # we are kicked
            room.disconnect()
            if by:
                kick_msg = _('%(spec)s [You] have been kicked by "[%(by)s]"') % {'spec': theme.CHAR_KICK.replace('"', '\\"'), 'by':by}
            else:
                kick_msg = _('%(spec)s [You] have been kicked.') % {'spec':theme.CHAR_KICK.replace('"', '\\"')}
            # try to auto-rejoin
            if config.get('autorejoin', 'false') == 'true':
                muc.join_groupchat(self.xmpp, room.name, room.own_nick)
        else:
            if by:
                kick_msg = _('%(spec)s "[%(nick)s]" has been kicked by "[%(by)s]"') % {'spec':theme.CHAR_KICK.replace('"', '\\"'), 'nick':from_nick.replace('"', '\\"'), 'by':by.replace('"', '\\"')}
            else:
                kick_msg = _('%(spec)s "[%(nick)s]" has been kicked') % {'spec':theme.CHAR_KICK, 'nick':from_nick.replace('"', '\\"')}
        if reason:
            kick_msg += _(' Reason: %(reason)s') % {'reason': reason}
        self.add_message_to_text_buffer(room, kick_msg, colorized=True)

    def on_user_leave_groupchat(self, room, user, jid, status, from_nick, from_room):
        """
        When an user leaves a groupchat
        """
        room.users.remove(user)
        if room.own_nick == user.nick:
            # We are now out of the room. Happens with some buggy (? not sure) servers
            room.disconnect()
        hide_exit_join = config.get('hide_exit_join', -1) if config.get('hide_exit_join', -1) >= -1 else -1
        if hide_exit_join == -1 or user.has_talked_since(hide_exit_join):
            if not jid.full:
                leave_msg = _('%(spec)s "[%(nick)s]" has left the room') % {'nick':from_nick.replace('"', '\\"'), 'spec':theme.CHAR_QUIT.replace('"', '\\"')}
            else:
                leave_msg = _('%(spec)s "[%(nick)s]" "(%(jid)s)" has left the room') % {'spec':theme.CHAR_QUIT.replace('"', '\\"'), 'nick':from_nick.replace('"', '\\"'), 'jid':jid.full.replace('"', '\\"')}
            if status:
                leave_msg += ' (%s)' % status
            self.add_message_to_text_buffer(room, leave_msg, colorized=True)
        private_room = self.get_room_by_name('%s/%s' % (from_room, from_nick))
        if private_room:
            if not status:
                self.add_message_to_text_buffer(private_room, _('%(spec)s "[%(nick)s]" has left the room') % {'nick':from_nick.replace('"', '\\"'), 'spec':theme.CHAR_QUIT.replace('"', '\\"')}, colorized=True)
            else:
                self.add_message_to_text_buffer(private_room, _('%(spec)s "[%(nick)s]" has left the room "(%(status)s)"') % {'nick':from_nick.replace('"', '\\"'), 'spec':theme.CHAR_QUIT, 'status': status.replace('"', '\\"')}, colorized=True)

    def on_user_change_status(self, room, user, from_nick, from_room, affiliation, role, show, status):
        """
        When an user changes her status
        """
        # build the message
        display_message = False # flag to know if something significant enough
        # to be displayed has changed
        msg = _('"%s" changed: ')% from_nick.replace('"', '\\"')
        if affiliation != user.affiliation:
            msg += _('affiliation: %s, ') % affiliation
            display_message = True
        if role != user.role:
            msg += _('role: %s, ') % role
            display_message = True
        if show != user.show and show in list(SHOW_NAME.keys()):
            msg += _('show: %s, ') % SHOW_NAME[show]
            display_message = True
        if status and status != user.status:
            msg += _('status: %s, ') % status
            display_message = True
        if not display_message:
            return
        msg = msg[:-2] # remove the last ", "
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
            self.add_message_to_text_buffer(room, msg, colorized=True)
        private_room = self.get_room_by_name('%s/%s' % (from_room, from_nick))
        if private_room: # display the message in private
            self.add_message_to_text_buffer(private_room, msg, colorized=True)
        # finally, effectively change the user status
        user.update(affiliation, show, status, role)

    def on_message(self, message):
        """
        When receiving private message from a muc OR a normal message
        (from one of our contacts)
        """
        if message['type'] == 'groupchat':
            return
        # Differentiate both type of messages, and call the appropriate handler.
        jid_from = message['from']
        for tab in self.tabs:
            if isinstance(tab, MucTab) and tab.get_name() == jid_from.bare: # check all the MUC we are in
                if message['type'] == 'error':
                    return self.room_error(message, tab.get_room().name)
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
        self.add_message_to_text_buffer(room, body, None, nick_from)
        self.refresh_window()
        self.doupdate()

    def focus_tab_named(self, tab_name):
        for tab in self.tabs:
            if tab.get_name() == tab_name:
                self.command_win('%s' % (tab.nb,))

    def on_normal_message(self, message):
        """
        When receiving "normal" messages (from someone in our roster)
        """
        jid = message['from']
        body = message['body']
        if not body:
            return
        # We first check if we have a conversation opened with this precise resource
        conversation = self.get_tab_by_name(jid.full)
        if not conversation:
            # If not, we search for a conversation with the bare jid
            conversation = self.get_tab_by_name(jid.bare)
            if not conversation:
                # We create the conversation with the bare Jid if nothing was found
                conversation = self.open_conversation_window(jid.bare, False)
            # room = self.open_conversation_window(jid, False)
        self.add_message_to_text_buffer(conversation.get_room(), body, None, jid.full)
        if self.current_tab() is not conversation:
            conversation.set_color_state(theme.COLOR_TAB_PRIVATE)
        self.refresh_window()
        return

    def on_presence(self, presence):
        """
        """
        jid = presence['from']
        contact = roster.get_contact_by_jid(jid.bare)
        if not contact:
            return
        resource = contact.get_resource_by_fulljid(jid.full)
        if not resource:
            return
        status = presence['type']
        status_message = presence['status']
        priority = presence.getPriority() or 0
        resource.set_presence(status)
        resource.set_priority(priority)
        resource.set_status(status_message)
        if isinstance(self.current_tab(), RosterInfoTab):
            self.refresh_window()

    def on_roster_update(self, iq):
        """
        A subscription changed, or we received a roster item
        after a roster request, etc
        """
        for item in iq.findall('{jabber:iq:roster}query/{jabber:iq:roster}item'):
            jid = item.attrib['jid']
            contact = roster.get_contact_by_jid(jid)
            if not contact:
                contact = Contact(jid)
                roster.add_contact(contact, jid)
            if 'ask' in item.attrib:
                contact.set_ask(item.attrib['ask'])
            else:
                contact.set_ask(None)
            if 'name' in item.attrib:
                contact.set_name(item.attrib['name'])
            else:
                contact.set_name(None)
            if item.attrib['subscription']:
                contact.set_subscription(item.attrib['subscription'])
            groups = item.findall('{jabber:iq:roster}group')
            roster.edit_groups_of_contact(contact, [group.text for group in groups])
        if isinstance(self.current_tab(), RosterInfoTab):
            self.refresh_window()

    def call_for_resize(self):
        """
        Starts a very short timer. If no other terminal resize
        occured in this delay then poezio is REALLY resize.
        This is to avoid multiple unnecessary software resizes (this
        can be heavy on resource on slow computers or networks)
        """
        with resize_lock:
            if self.resize_timer:
                # a recent terminal resize occured.
                # Cancel the programmed software resize
                self.resize_timer.cancel()
            # add the new timer
            self.resize_timer = threading.Timer(0.1, self.resize_window)
            self.resize_timer.start()
        # self.resize_window()

    def resize_window(self):
        """
        Resize the whole screen
        """
        with resize_lock:
           # self.resize_timer = None
            for tab in self.tabs:
                tab.resize()
            self.refresh_window()

    def main_loop(self):
        """
        main loop waiting for the user to press a key
        """
        self.refresh_window()
        while self.running:
            self.doupdate()
            char=read_char(self.stdscr)
            # search for keyboard shortcut
            if char in list(self.key_func.keys()):
                self.key_func[char]()
            else:
                self.do_command(char)

    def current_tab(self):
        """
        returns the current room, the one we are viewing
        """
        return self.tabs[0]

    def get_conversation_by_jid(self, jid):
        """
        Return the room of the ConversationTab with the given jid
        """
        for tab in self.tabs:
            if isinstance(tab, ConversationTab):
                if tab.get_name() == jid:
                    return tab.get_room()
        return None

    def get_tab_by_name(self, name):
        """
        Get the tab with the given name.
        """
        for tab in self.tabs:
            if tab.get_name() == name:
                return tab
        return None

    def get_room_by_name(self, name):
        """
        returns the room that has this name
        """
        for tab in self.tabs:
            if (isinstance(tab, MucTab) or
                isinstance(tab, PrivateTab)) and tab.get_name() == name:
                return tab.get_room()
        return None

    def init_curses(self, stdscr):
        """
        ncurses initialization
        """
        curses.curs_set(1)
        curses.noecho()
        # curses.raw()
        theme.init_colors()
        stdscr.keypad(True)

    def reset_curses(self):
        """
        Reset terminal capabilities to what they were before ncurses
        init
        """
        curses.echo()
        curses.nocbreak()
        curses.endwin()

    def refresh_window(self):
        """
        Refresh everything
        """
        self.current_tab().set_color_state(theme.COLOR_TAB_CURRENT)
        self.current_tab().refresh(self.tabs, self.information_buffer, roster)
        self.doupdate()

    def open_new_room(self, room, nick, focus=True):
        """
        Open a new MucTab containing a muc Room, using the specified nick
        """
        r = Room(room, nick)
        new_tab = MucTab(self, r)
        if self.current_tab().nb == 0:
            self.tabs.append(new_tab)
        else:
            for ta in self.tabs:
                if ta.nb == 0:
                    self.tabs.insert(self.tabs.index(ta), new_tab)
                    break
        if focus:
            self.command_win("%s" % new_tab.nb)
        self.refresh_window()

    def go_to_roster(self):
        self.command_win('0')

    def go_to_previous_tab(self):
        self.command_win('%s' % (self.previous_tab_nb,))

    def go_to_important_room(self):
        """
        Go to the next room with activity, in this order:
        - A personal conversation with a new message
        - A Muc with an highlight
        - A Muc with any new message
        """
        for tab in self.tabs:
            if tab.get_color_state() == theme.COLOR_TAB_PRIVATE:
                self.command_win('%s' % tab.nb)
                return
        for tab in self.tabs:
            if tab.get_color_state() == theme.COLOR_TAB_HIGHLIGHT:
                self.command_win('%s' % tab.nb)
                return
        for tab in self.tabs:
            if tab.get_color_state() == theme.COLOR_TAB_NEW_MESSAGE:
                self.command_win('%s' % tab.nb)
                return

    def rotate_rooms_right(self, args=None):
        """
        rotate the rooms list to the right
        """
        self.current_tab().on_lose_focus()
        self.tabs.append(self.tabs.pop(0))
        self.current_tab().on_gain_focus()
        self.refresh_window()

    def rotate_rooms_left(self, args=None):
        """
        rotate the rooms list to the right
        """
        self.current_tab().on_lose_focus()
        self.tabs.insert(0, self.tabs.pop())
        self.current_tab().on_gain_focus()
        self.refresh_window()

    def scroll_page_down(self, args=None):
        self.current_tab().on_scroll_down()
        self.refresh_window()

    def scroll_page_up(self, args=None):
        self.current_tab().on_scroll_up()
        self.refresh_window()

    def room_error(self, error, room_name):
        """
        Display the error on the room window
        """
        room = self.get_room_by_name(room_name)
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
            msg = _('Error: %(code)s - %(msg)s: %(body)s') % {'msg':msg, 'body':body, 'code':code}
            self.add_message_to_text_buffer(room, msg)
        else:
            msg = _('Error: %(msg)s: %(body)s') % {'msg':msg, 'body':body}
            self.add_message_to_text_buffer(room, msg)
        if code == '401':
            msg = _('To provide a password in order to join the room, type "/join / password" (replace "password" by the real password)')
            self.add_message_to_text_buffer(room, msg)
        if code == '409':
            if config.get('alternative_nickname', '') != '':
                self.command_join('%s/%s'% (room.name, room.own_nick+config.get('alternative_nickname', '')))
            else:
                self.add_message_to_text_buffer(room, _('You can join the room with an other nick, by typing "/join /other_nick"'))
        self.refresh_window()

    def open_conversation_window(self, jid, focus=True):
        """
        open a new conversation tab and focus it if needed
        """
        text_buffer = TextBuffer()
        new_tab = ConversationTab(self, text_buffer, jid)
        # insert it in the rooms
        if self.current_tab().nb == 0:
            self.tabs.append(new_tab)
        else:
            for ta in self.tabs:
                if ta.nb == 0:
                    self.tabs.insert(self.tabs.index(ta), new_tab)
                    break
        if focus:               # focus the room if needed
            self.command_win('%s' % (new_tab.nb))
        self.refresh_window()
        return new_tab

    def open_private_window(self, room_name, user_nick, focus=True):
        complete_jid = room_name+'/'+user_nick
        for tab in self.tabs: # if the room exists, focus it and return
            if isinstance(tab, PrivateTab):
                if tab.get_name() == complete_jid:
                    self.command_win('%s' % tab.nb)
                    return
        # create the new tab
        room = self.get_room_by_name(room_name)
        if not room:
            return None
        own_nick = room.own_nick
        r = Room(complete_jid, own_nick) # PrivateRoom here
        new_tab = PrivateTab(self, r)
        # insert it in the tabs
        if self.current_tab().nb == 0:
            self.tabs.append(new_tab)
        else:
            for ta in self.tabs:
                if ta.nb == 0:
                    self.tabs.insert(self.tabs.index(ta), new_tab)
                    break
        if focus:               # focus the room if needed
            self.command_win('%s' % (new_tab.nb))
        # self.window.new_room(r)
        self.refresh_window()
        return r

    def on_groupchat_subject(self, message):
        """
        triggered when the topic is changed
        """
        nick_from = message['mucnick']
        room_from = message.getMucroom()
        room = self.get_room_by_name(room_from)
        subject = message['subject']
        if not subject:
            return
        self.add_message_to_text_buffer(room, _("%(nick)s set the subject to: %(subject)s") % {'nick':nick_from, 'subject':subject}, time=None)
        room.topic = subject.replace('\n', '|')
        self.refresh_window()

    def on_groupchat_message(self, message):
        """
        Triggered whenever a message is received from a multi-user chat room.
        """
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
        if not room:
            self.information(_("message received for a non-existing room: %s") % (room_from))
            return
        body = message['body']
        if body:
            date = date if delayed == True else None
            # if not delayed:
            #     logger.groupchat(room_from, nick_from, body)
            self.add_message_to_text_buffer(room, body, date, nick_from)
            self.refresh_window()
            self.doupdate()

    def add_message_to_text_buffer(self, room, txt, time=None, nickname=None, colorized=False):
        """
        Add the message to the room if possible, else, add it to the Info window
        (in the Info tab of the info window in the RosterTab)
        """
        if not room:
            self.information('Error, trying to add a message in no room: %s' % txt)
        else:
            room.add_message(txt, time, nickname, colorized)
        self.refresh_window()

    def command_help(self, arg):
        """
        /help <command_name>
        """
        args = arg.split()
        if len(args) == 0:
            msg = _('Available commands are: ')
            for command in list(self.commands.keys()):
                msg += "%s " % command
            msg += _("\nType /help <command_name> to know what each command does")
        if len(args) >= 1:
            if args[0] in list(self.commands.keys()):
                msg = self.commands[args[0]][1]
            else:
                msg = _('Unknown command: %s') % args[0]
        self.information(msg)

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
            return self.information(str(error), _("Error"))
        room = self.current_room()
        if len(args) != 1:
            self.add_message_to_text_buffer(room, _('whois command takes exactly one argument'))
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

    def command_recolor(self, arg):
        """
        Re-assign color to the participants of the room
        """
        tab = self.current_tab()
        if not isinstance(tab, MucTab):
            return
        room = tab.get_room()
        i = 0
        compare_users = lambda x: x.last_talked
        users = list(room.users)
        # search our own user, to remove it from the room
        for user in users:
            if user.nick == room.own_nick:
                users.remove(user)
        nb_color = len(theme.LIST_COLOR_NICKNAMES)
        for user in sorted(users, key=compare_users, reverse=True):
            user.color = theme.LIST_COLOR_NICKNAMES[i % nb_color]
            i+= 1
        self.refresh_window()

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
        if self.current_tab().nb == nb:
            return
        self.previous_tab_nb = self.current_tab().nb
        self.current_tab().on_lose_focus()
        start = self.current_tab()
        self.tabs.append(self.tabs.pop(0))
        while self.current_tab().nb != nb:
            self.tabs.append(self.tabs.pop(0))
            if self.current_tab() == start:
                self.current_tab().set_color_state(theme.COLOR_TAB_CURRENT)
                self.refresh_window()
                return
        self.current_tab().on_gain_focus()
        self.refresh_window()

    def command_kick(self, arg):
        """
        /kick <nick> [reason]
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.information(str(error), _("Error"))
        if len(args) < 1:
            self.command_help('kick')
            return
        nick = args[0]
        if len(args) >= 2:
            reason = ' '.join(args[1:])
        else:
            reason = ''
        if not isinstance(self.current_tab(), MucTab) or not self.current_tab().get_room().joined:
            return
        roomname = self.current_tab().get_name()
        res = muc.eject_user(self.xmpp, roomname, nick, reason)
        if res['type'] == 'error':
            self.room_error(res, roomname)

    def command_join(self, arg):
        """
        /join [room][/nick] [password]
        """
        args = arg.split()
        password = None
        if len(args) == 0:
            t = self.current_tab()
            if not isinstance(t, MucTab) and not isinstance(t, PrivateTab):
                return
            room = t.get_name()
            nick = t.get_room().own_nick
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
                t = self.current_tab()
                if not isinstance(t, MucTab):
                    return
                room = t.get_name()
                if nick == '':
                    nick = t.get_room().own_nick
            else:
                room = info[0]
            if not is_jid(room): # no server is provided, like "/join hello"
                # use the server of the current room if available
                # check if the current room's name has a server
                if isinstance(self.current_tab(), MucTab) and\
                        is_jid(self.current_tab().get_name()):
                    room += '@%s' % jid_get_domain(self.current_tab().get_name())
                else:           # no server could be found, print a message and return
                    self.information(_("You didn't specify a server for the room you want to join"), 'Error')
                    return
        r = self.get_room_by_name(room)
        if len(args) == 2:       # a password is provided
            password = args[1]
        if r and r.joined:       # if we are already in the room
            self.focus_tab_named(r.name)
            return
        room = room.lower()
        if r and not r.joined:
            muc.join_groupchat(self.xmpp, room, nick, password)
        if not r:   # if the room window exists, we don't recreate it.
            self.open_new_room(room, nick)
            muc.join_groupchat(self.xmpp, room, nick, password)
        else:
            r.own_nick = nick
            r.users = []

    def command_bookmark(self, arg):
        """
        /bookmark [room][/nick]
        """
        args = arg.split()
        nick = None
        if not isinstance(self.current_tab(), MucTab):
            return
        if len(args) == 0:
            room = self.current_tab().get_room()
            roomname = self.current_tab().get_name()
            if room.joined:
                nick = room.own_nick
        else:
            info = args[0].split('/')
            if len(info) == 2:
                nick = info[1]
            roomname = info[0]
            if roomname == '':
                roomname = self.current_tab().get_name()
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
        if bookmarked:
            bookmarks = bookmarked+':'+res
        else:
            bookmarks = res
        config.set_and_save('rooms', bookmarks)
        self.information(_('Your bookmarks are now: %s') % bookmarks)

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
        self.information(msg)

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
        for tab in self.tabs:
            if isinstance(tab, MucTab) and tab.get_room().joined:
                muc.change_show(self.xmpp, tab.get_room().name, tab.get_room().own_nick, show, msg)

    def command_ignore(self, arg):
        """
        /ignore <nick>
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.information(str(error), _("Error"))
        if len(args) != 1:
            self.command_help('ignore')
            return
        if not isinstance(self.current_tab(), MucTab):
            return
        roomname = self.current_tab().get_name()
        nick = args[0]
        if roomname not in self.ignores:
            self.ignores[roomname] = set() # no need for any order
        if nick not in self.ignores[roomname]:
            self.ignores[roomname].add(nick)
            self.information(_("%s is now ignored") % nick, 'info')
        else:
            self.information(_("%s is alread ignored") % nick, 'info')

    def command_unignore(self, arg):
        """
        /unignore <nick>
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.information(str(error), _("Error"))
        if len(args) != 1:
            self.command_help('unignore')
            return
        if not isinstance(self.current_tab(), MucTab):
            return
        roomname = self.current_tab().get_name()
        nick = args[0]
        if roomname not in self.ignores or (nick not in self.ignores[roomname]):
            self.information(_("%s was not ignored") % nick, info)
            return
        self.ignores[roomname].remove(nick)
        if not self.ignores[roomname]:
            del self.ignores[roomname]
        self.information(_("%s is now unignored") % nick, 'info')

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
        if not isinstance(self.current_tab(), MucTab) and\
                not isinstance(self.current_tab(), PrivateTab):
            return
        args = arg.split()
        reason = None
        room = self.current_tab().get_room()
        if len(args):
            msg = ' '.join(args)
        else:
            msg = None
        if isinstance(self.current_tab(), MucTab) and\
                self.current_tab().get_room().joined:
            muc.leave_groupchat(self.xmpp, room.name, room.own_nick, arg)
        self.close_tab()

    def close_tab(self, tab=None):
        """
        Close the given tab. If None, close the current one
        """
        tab = tab or self.current_tab()
        if isinstance(tab, RosterInfoTab) or\
                isinstance(tab, InfoTab):
            return              # The tab 0 should NEVER be closed
        tab.on_close()
        self.tabs.remove(tab)
        self.rotate_rooms_left()
        del tab

    def command_query(self, arg):
        """
        /query <nick> [message]
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.information(str(error), _("Error"))
        if len(args) < 1 or not isinstance(self.current_tab(), MucTab):
            return
        nick = args[0]
        room = self.current_tab().get_room()
        r = None
        for user in room.users:
            if user.nick == nick:
                r = self.open_private_window(room.name, user.nick)
        if r and len(args) > 1:
            msg = arg[len(nick)+1:]
            muc.send_private_message(self.xmpp, r.name, msg)
            self.add_message_to_text_buffer(r, msg, None, r.own_nick)

    def command_unquery(self, arg):
        """
        /unquery
        Closes the Conversation or the Private tab
        """
        if isinstance(self.current_tab(), ConversationTab) or\
                isinstance(self.current_tab(), PrivateTab):
            self.close_tab()

    def command_topic(self, arg):
        """
        /topic [new topic]
        """
        if not isinstance(self.current_tab(), MucTab):
            return
        room = self.current_tab().get_room()
        if not arg.strip():
            self.add_message_to_text_buffer(room, _("The subject of the room is: %s") % room.topic)
            return
        subject = arg
        muc.change_subject(self.xmpp, room.name, subject)

    def command_link(self, arg):
        """
        /link <option> <nb>
        Opens the link in a browser, or join the room, or add the JID, or
        copy it in the clipboard
        """
        if not isinstance(self.current_tab(), MucTab) and\
                not isinstance(self.current_tab(), PrivateTab):
            return
        args = arg.split()
        if len(args) > 2:
            # INFO
            # self.add_message_to_text_buffer(self.current_room(),
            #                          _("Link: This command takes at most 2 arguments"))
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
                # INFO
                # self.add_message_to_text_buffer(self.current_room(),
                #                          _("Link: 2nd parameter should be a number"))
                return
        # find the nb-th link in the current buffer
        i = 0
        link = None
        for msg in self.current_tab().get_room().messages[:-200:-1]:
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

    def move_separator(self):
        """
        Move the new-messages separator at the bottom on the current
        text.
        """
        try:
            room = self.current_tab().get_room()
        except:
            return
        room.remove_line_separator()
        room.add_line_separator()
        self.refresh_window()

    def command_nick(self, arg):
        """
        /nick <nickname>
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.information(str(error), _("Error"))
        if not isinstance(self.current_tab(), MucTab):
            return
        if len(args) != 1:
            return
        nick = args[0]
        room = self.current_tab().get_room()
        if not room.joined or room.name == "Info":
            return
        muc.change_nick(self.xmpp, room.name, nick)

    def information(self, msg, typ=''):
        """
        Displays an informational message in the "Info" room window
        """
        self.information_buffer.add_message(msg, nickname=typ)
        self.refresh_window()

    def command_quit(self, arg):
        """
        /quit
        """
        if len(arg.strip()) != 0:
            msg = arg
        else:
            msg = None
        for tab in self.tabs:
            if isinstance(tab, MucTab):
                muc.leave_groupchat(self.xmpp, tab.get_room().name, tab.get_room().own_nick, msg)
        self.xmpp.disconnect()
        self.running = False
        self.reset_curses()

    def do_command(self, key):
        if not key:
            return
        res = self.current_tab().on_input(key)
        if res:
            self.refresh_window()

    def on_roster_enter_key(self, roster_row):
        """
        when enter is pressed on the roster window
        """
        if isinstance(roster_row, Contact):
            if not self.get_conversation_by_jid(roster_row.get_bare_jid()):
                self.open_conversation_window(roster_row.get_bare_jid())
            else:
                self.focus_tab_named(roster_row.get_bare_jid())
        if isinstance(roster_row, Resource):
            if not self.get_conversation_by_jid(roster_row.get_jid().full):
                self.open_conversation_window(roster_row.get_jid().full)
            else:
                self.focus_tab_named(roster_row.get_jid().full)
        self.refresh_window()

    def execute(self,line):
        """
        Execute the /command or just send the line on the current room
        """
        if line == "":
            return
        if line.startswith('//'):
            self.command_say(line[1:])
        elif line.startswith('/') and not line.startswith('/me '):
            command = line.strip()[:].split()[0][1:]
            arg = line[2+len(command):] # jump the '/' and the ' '
            # example. on "/link 0 open", command = "link" and arg = "0 open"
            if command in list(self.commands.keys()):
                func = self.commands[command][0]
                func(arg)
                return
            else:
                self.information(_("unknown command (%s)") % (command), _('Error'))
        else:
            self.command_say(line)

    def command_say(self, line):
        if isinstance(self.current_tab(), PrivateTab):
            muc.send_private_message(self.xmpp, self.current_tab().get_name(), line)
        elif isinstance(self.current_tab(), ConversationTab): # todo, special case # hu, I can't remember what special case was needed when I wrote that…
            muc.send_private_message(self.xmpp, self.current_tab().get_name(), line)
        if isinstance(self.current_tab(), PrivateTab) or\
                isinstance(self.current_tab(), ConversationTab):
            self.add_message_to_text_buffer(self.current_tab().get_room(), line, None, self.own_nick)
        elif isinstance(self.current_tab(), MucTab):
            muc.send_groupchat_message(self.xmpp, self.current_tab().get_name(), line)
        self.doupdate()

    def doupdate(self):
        self.current_tab().just_before_refresh()
        curses.doupdate()

# # global core object
core = Core(connection)

