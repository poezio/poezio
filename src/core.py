# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

from gettext import gettext as _

import os
import sys
import time
import curses
import threading
import traceback

from datetime import datetime

from inspect import getargspec

import common
import theming
import logging
import singleton
import collections

from sleekxmpp.xmlstream.stanzabase import JID

log = logging.getLogger(__name__)

import multiuserchat as muc
import tabs

import xhtml
import events
import pubsub
import windows
import connection
import timed_events

from plugin_manager import PluginManager

from data_forms import DataFormsTab
from config import config, options
from logger import logger
from roster import roster
from contact import Contact, Resource
from text_buffer import TextBuffer
from keyboard import read_char
from theming import get_theme
from fifo import Fifo
from windows import g_lock

# http://xmpp.org/extensions/xep-0045.html#errorstatus
ERROR_AND_STATUS_CODES = {
    '401': _('A password is required'),
    '403': _('Permission denied'),
    '404': _('The room does\'nt exist'),
    '405': _('Your are not allowed to create a new room'),
    '406': _('A reserved nick must be used'),
    '407': _('You are not in the member list'),
    '409': _('This nickname is already in use or has been reserved'),
    '503': _('The maximum number of users has been reached'),
    }

possible_show = {'available':None,
                 'chat':'chat',
                 'away':'away',
                 'afk':'away',
                 'dnd':'dnd',
                 'busy':'dnd',
                 'xa':'xa'
                 }

Status = collections.namedtuple('Status', 'show message')

class Core(object):
    """
    User interface using ncurses
    """

    def __init__(self):
        # All uncaught exception are given to this callback, instead
        # of being displayed on the screen and exiting the program.
        self.connection_time = time.time()
        self.status = Status(show=None, message='')
        sys.excepthook = self.on_exception
        self.running = True
        self.events = events.EventHandler()
        self.xmpp = singleton.Singleton(connection.Connection)
        self.remote_fifo = None
        # a unique buffer used to store global informations
        # that are displayed in almost all tabs, in an
        # information window.
        self.information_buffer = TextBuffer()
        self.information_win_size = config.get('info_win_height', 2, 'var')
        self.information_win = windows.TextWin(20)
        self.tab_win = windows.GlobalInfoBar()
        self.information_buffer.add_window(self.information_win)
        self.tabs = []
        self.previous_tab_nb = 0
        self.own_nick = config.get('default_nick', '') or self.xmpp.boundjid.user
        # global commands, available from all tabs
        # a command is tuple of the form:
        # (the function executing the command. Takes a string as argument,
        #  a string representing the help message,
        #  a completion function, taking a Input as argument. Can be None)
        #  The completion function should return True if a completion was
        #  made ; False otherwise
        self.plugin_manager = PluginManager(self)
        self.commands = {
            'help': (self.command_help, '\_o< KOIN KOIN KOIN', self.completion_help),
            'join': (self.command_join, _("Usage: /join [room_name][@server][/nick] [password]\nJoin: Join the specified room. You can specify a nickname after a slash (/). If no nickname is specified, you will use the default_nick in the configuration file. You can omit the room name: you will then join the room you\'re looking at (useful if you were kicked). You can also provide a room_name without specifying a server, the server of the room you're currently in will be used. You can also provide a password to join the room.\nExamples:\n/join room@server.tld\n/join room@server.tld/John\n/join room2\n/join /me_again\n/join\n/join room@server.tld/my_nick password\n/join / password"), self.completion_join),
            'exit': (self.command_quit, _("Usage: /exit\nExit: Just disconnect from the server and exit poezio."), None),
            'quit': (self.command_quit, _("Usage: /quit\nQuit: Just disconnect from the server and exit poezio."), None),
            'next': (self.rotate_rooms_right, _("Usage: /next\nNext: Go to the next room."), None),
            'prev': (self.rotate_rooms_left, _("Usage: /prev\nPrev: Go to the previous room."), None),
            'win': (self.command_win, _("Usage: /win <number>\nWin: Go to the specified room."), self.completion_win),
            'w': (self.command_win, _("Usage: /w <number>\nW: Go to the specified room."), self.completion_win),
            'show': (self.command_status, _('Usage: /show <availability> [status message]\nShow: Sets your availability and (optionally) your status message. The <availability> argument is one of \"available, chat, away, afk, dnd, busy, xa\" and the optional [status message] argument will be your status message.'), self.completion_status),
            'status': (self.command_status, _('Usage: /status <availability> [status message]\nStatus: Sets your availability and (optionally) your status message. The <availability> argument is one of \"available, chat, away, afk, dnd, busy, xa\" and the optional [status message] argument will be your status message.'), self.completion_status),
            'away': (self.command_away, _("Usage: /away [message]\nAway: Sets your availability to away and (optionally) your status message. This is equivalent to '/status away [message]'"), None),
            'busy': (self.command_busy, _("Usage: /busy [message]\nBusy: Sets your availability to busy and (optionally) your status message. This is equivalent to '/status busy [message]'"), None),
            'available': (self.command_avail, _("Usage: /available [message]\nAvailable: Sets your availability to available and (optionally) your status message. This is equivalent to '/status available [message]'"), None),
           'bookmark': (self.command_bookmark, _("Usage: /bookmark [roomname][/nick]\nBookmark: Bookmark the specified room (you will then auto-join it on each poezio start). This commands uses almost the same syntaxe as /join. Type /help join for syntaxe examples. Note that when typing \"/bookmark\" on its own, the room will be bookmarked with the nickname you\'re currently using in this room (instead of default_nick)"), None),
            'set': (self.command_set, _("Usage: /set <option> [value]\nSet: Set the value of the option in your configuration file. You can, for example, change your default nickname by doing `/set default_nick toto` or your resource with `/set resource blabla`. You can also set an empty value (nothing) by providing no [value] after <option>."), None),
            'theme': (self.command_theme, _('Usage: /theme [theme_name]\nTheme: Reload the theme defined in the config file. If theme_name is provided, set that theme before reloading it.'), None),
            'list': (self.command_list, _('Usage: /list\nList: Get the list of public chatrooms on the specified server.'), self.completion_list),
            'message': (self.command_message, _('Usage: /message <jid> [optional message]\nMessage: Open a conversation with the specified JID (even if it is not in our roster), and send a message to it, if the message is specified.'), None),
            'version': (self.command_version, _('Usage: /version <jid>\nVersion: Get the software version of the given JID (usually its XMPP client and Operating System).'), None),
            'connect': (self.command_reconnect, _('Usage: /connect\nConnect: Disconnect from the remote server if you are currently connected and then connect to it again.'), None),
            'server_cycle': (self.command_server_cycle, _('Usage: /server_cycle [domain] [message]\nServer Cycle: Disconnect and reconnect in all the rooms in domain.'), None),
            'bind': (self.command_bind, _('Usage: /bind <key> <equ>\nBind: Bind a key to an other key or to a “command”. For example "/bind ^H KEY_UP" makes Control + h do the same same as the Up key.'), None),
            'load': (self.command_load, _('Usage: /load <plugin>\nLoad: Load the specified plugin'), self.plugin_manager.completion_load),
            'unload': (self.command_unload, _('Usage: /unload <plugin>\nUnload: Unload the specified plugin'), self.plugin_manager.completion_unload),
            'plugins': (self.command_plugins, _('Usage: /plugins\nPlugins: Show the plugins in use.'), None),
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
            '^L': self.full_screen_redraw,
            'M-j': self.go_to_room_number,
            }

        # Add handlers
        self.xmpp.add_event_handler('connected', self.on_connected)
        self.xmpp.add_event_handler('disconnected', self.on_disconnected)
        self.xmpp.add_event_handler('failed_auth', self.on_failed_auth)
        self.xmpp.add_event_handler("session_start", self.on_session_start)
        self.xmpp.add_event_handler("groupchat_presence", self.on_groupchat_presence)
        self.xmpp.add_event_handler("groupchat_message", self.on_groupchat_message)
        self.xmpp.add_event_handler("groupchat_subject", self.on_groupchat_subject)
        self.xmpp.add_event_handler("message", self.on_message)
        self.xmpp.add_event_handler("got_online" , self.on_got_online)
        self.xmpp.add_event_handler("got_offline" , self.on_got_offline)
        self.xmpp.add_event_handler("roster_update", self.on_roster_update)
        self.xmpp.add_event_handler("changed_status", self.on_presence)
        self.xmpp.add_event_handler("changed_subscription", self.on_changed_subscription)
        self.xmpp.add_event_handler("message_xform", self.on_data_form)
        self.xmpp.add_event_handler("chatstate_active", self.on_chatstate_active)
        self.xmpp.add_event_handler("chatstate_composing", self.on_chatstate_composing)
        self.xmpp.add_event_handler("chatstate_paused", self.on_chatstate_paused)
        self.xmpp.add_event_handler("chatstate_gone", self.on_chatstate_gone)
        self.xmpp.add_event_handler("chatstate_inactive", self.on_chatstate_inactive)

        self.timed_events = set()

        self.connected_events = {}

        self.autoload_plugins()

    def autoload_plugins(self):
        plugins = config.get('plugins_autoload', '')
        for plugin in plugins.split():
            self.plugin_manager.load(plugin)

    def start(self):
        """
        Init curses, create the first tab, etc
        """
        self.stdscr = curses.initscr()
        self.init_curses(self.stdscr)
        # Init the tab's size.
        tabs.Tab.resize(self.stdscr)
        # resize the information_win to its initial size
        self.resize_global_information_win()
        # resize the global_info_bar to its initial size
        self.resize_global_info_bar()
        default_tab = tabs.RosterInfoTab()
        default_tab.on_gain_focus()
        self.tabs.append(default_tab)
        self.information(_('Welcome to poezio!'))
        if config.get('firstrun', ''):
            self.information(_(
                'It seems that it is the first time you start poezio.\n' + \
                'The configuration help is here: http://dev.louiz.org/project/poezio/doc/HowToConfigure\n' + \
                'And the documentation for users is here: http://dev.louiz.org/project/poezio/doc/HowToUse\n' + \
                'By default, you are in poezio’s chatroom, where you can ask for help or tell us how great it is.\n' + \
                'Just press Ctrl-n.' \
            ))
        self.refresh_window()

    def resize_global_information_win(self):
        """
        Resize the global_information_win only once at each resize.
        """
        with g_lock:
            self.information_win.resize(self.information_win_size, tabs.Tab.width,
                                        tabs.Tab.height - 2 - self.information_win_size, 0)

    def resize_global_info_bar(self):
        """
        Resize the GlobalInfoBar only once at each resize
        """
        with g_lock:
            self.tab_win.resize(1, tabs.Tab.width, tabs.Tab.height - 2, 0)

    def on_exception(self, typ, value, trace):
        """
        When an exception is raised, just reset curses and call
        the original exception handler (will nicely print the traceback)
        """
        try:
            self.reset_curses()
        except:
            pass
        sys.__excepthook__(typ, value, trace)

    @property
    def informations(self):
        return self.information_buffer

    def grow_information_win(self, nb=1):
        if self.information_win_size >= self.current_tab().height -5 or \
                self.information_win_size+nb >= self.current_tab().height-4:
            return
        if self.information_win_size == 14:
            return
        self.information_win_size += nb
        if self.information_win_size > 14:
            self.information_win_size = 14
        self.resize_global_information_win()
        for tab in self.tabs:
            tab.on_info_win_size_changed()
        self.refresh_window()

    def shrink_information_win(self, nb=1):
        if self.information_win_size == 0:
            return
        self.information_win_size -= nb
        if self.information_win_size < 0:
            self.information_win_size = 0
        self.resize_global_information_win()
        for tab in self.tabs:
            tab.on_info_win_size_changed()
        self.refresh_window()

    def pop_information_win_up(self, size, time):
        """
        Temporarly increase the size of the information win of size lines
        during time seconds.
        After that delay, the size will decrease from size lines.
        """
        if time <= 0 or size <= 0:
            return
        self.grow_information_win(size)
        timed_event = timed_events.DelayedEvent(time, self.shrink_information_win, size)
        self.add_timed_event(timed_event)

    def get_status(self):
        """
        Get the last status that was previously set
        """
        return self.status

    def set_status(self, pres, msg):
        """
        Set our current status so we can remember
        it and use it back when needed (for example to display it
        or to use it when joining a new muc)
        """
        self.status = Status(show=pres, message=msg)

    def on_data_form(self, message):
        """
        When a data form is received
        """
        self.information('%s' % message)

    def on_chatstate_active(self, message):
        self.on_chatstate(message, "active")

    def on_chatstate_inactive(self, message):
        self.on_chatstate(message, "inactive")

    def on_chatstate_composing(self, message):
        self.on_chatstate(message, "composing")

    def on_chatstate_paused(self, message):
        self.on_chatstate(message, "paused")

    def on_chatstate_gone(self, message):
        self.on_chatstate(message, "gone")

    def on_chatstate(self, message, state):
        if message['type'] == 'chat':
            if not self.on_chatstate_normal_conversation(message, state):
                tab = self.get_tab_by_name(message['from'].full, tabs.PrivateTab)
                if not tab:
                    return
                self.on_chatstate_private_conversation(message, state)
        elif message['type'] == 'groupchat':
            self.on_chatstate_groupchat_conversation(message, state)

    def on_chatstate_normal_conversation(self, message, state):
        tab = self.get_tab_of_conversation_with_jid(message['from'], False)
        if not tab:
            return False
        tab.chatstate = state
        if tab == self.current_tab():
            tab.refresh_info_header()
            self.doupdate()
        return True

    def on_chatstate_private_conversation(self, message, state):
        tab = self.get_tab_by_name(message['from'].full, tabs.PrivateTab)
        if not tab:
            return
        tab.chatstate = state
        if tab == self.current_tab():
            tab.refresh_info_header()
            self.doupdate()
        return True

    def on_chatstate_groupchat_conversation(self, message, state):
        nick = message['mucnick']
        room_from = message.getMucroom()
        tab = self.get_tab_by_name(room_from, tabs.MucTab)
        if tab and tab.get_user_by_name(nick):
            tab.get_user_by_name(nick).chatstate = state
        if tab == self.current_tab():
            tab.user_win.refresh(tab.users)
            tab.input.refresh()
            self.doupdate()

    def open_new_form(self, form, on_cancel, on_send, **kwargs):
        """
        Open a new tab containing the form
        The callback are called with the completed form as parameter in
        addition with kwargs
        """
        form_tab = DataFormsTab(form, on_cancel, on_send, kwargs)
        self.add_tab(form_tab, True)

    def on_got_offline(self, presence):
        jid = presence['from']
        contact = roster.get_contact_by_jid(jid.bare)
        logger.log_roster_change(jid.bare, 'got offline')
        if not contact:
            return
        resource = contact.get_resource_by_fulljid(jid.full)
        if not resource:
            return
        # If a resource got offline, display the message in the conversation with this
        # precise resource.
        self.add_information_message_to_conversation_tab(jid.full, '\x195}%s is \x191}offline' % (resource.get_jid().full))
        contact.remove_resource(resource)
        # Display the message in the conversation with the bare JID only if that was
        # the only resource online (i.e. now the contact is completely disconnected)
        if not contact.get_highest_priority_resource(): # No resource left: that was the last one
            self.add_information_message_to_conversation_tab(jid.bare, '\x195}%s is \x191}offline' % (jid.bare))
            self.information('\x193}%s \x195}is \x191}offline' % (resource.get_jid().bare), "Roster")
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def on_got_online(self, presence):
        jid = presence['from']
        contact = roster.get_contact_by_jid(jid.bare)
        if not contact:
            # Todo, handle presence comming from contacts not in roster
            return
        logger.log_roster_change(jid.bare, 'got online')
        resource = contact.get_resource_by_fulljid(jid.full)
        assert not resource
        resource = Resource(jid.full)
        status = presence['type']
        status_message = presence['status']
        priority = presence.getPriority() or 0
        resource.set_status(status_message)
        resource.set_presence(status)
        resource.set_priority(priority)
        self.add_information_message_to_conversation_tab(jid.full, '\x195}%s is \x194}online' % (jid.full))
        if not contact.get_highest_priority_resource():
            # No connected resource yet: the user's just connecting
            if time.time() - self.connection_time > 12:
                # We do not display messages if we recently logged in
                if status_message:
                    self.information("\x193}%s \x195}is \x194}online\x195} (\x19o%s\x195})" % (resource.get_jid().bare, status_message), "Roster")
                else:
                    self.information("\x193}%s \x195}is \x194}online\x195}" % resource.get_jid().bare, "Roster")
            self.add_information_message_to_conversation_tab(jid.bare, '\x195}%s is \x194}online' % (jid.bare))
        contact.add_resource(resource)
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def add_information_message_to_conversation_tab(self, jid, msg):
        """
        Search for a ConversationTab with the given jid (full or bare), if yes, add
        the given message to it
        """
        tab = self.get_tab_by_name(jid, tabs.ConversationTab)
        if tab:
            self.add_message_to_text_buffer(tab._text_buffer, msg)

    def on_failed_connection(self):
        """
        We cannot contact the remote server
        """
        self.information(_("Connection to remote server failed"))

    def on_disconnected(self, event):
        """
        When we are disconnected from remote server
        """
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab):
                tab.disconnect()
        self.information(_("Disconnected from server."))

    def on_failed_auth(self, event):
        """
        Authentication failed
        """
        self.information(_("Authentication failed."))

    def on_connected(self, event):
        """
        Remote host responded, but we are not yet authenticated
        """
        self.information(_("Connected to server."))

    def on_session_start(self, event):
        """
        Called when we are connected and authenticated
        """
        self.connection_time = time.time()
        self.information(_("Authentication success."))
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
            jid = JID(room)
            if jid.bare == '':
                return
            if jid.resource != '':
                nick = jid.resource
            else:
                default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
                nick = config.get('default_nick', '') or default
            tab = self.get_tab_by_name(jid.bare, tabs.MucTab)
            if not tab:
                self.open_new_room(jid.bare, nick, False)
            muc.join_groupchat(self.xmpp, jid.bare, nick)

    def on_groupchat_presence(self, presence):
        """
        Triggered whenever a presence stanza is received from a user in a multi-user chat room.
        Display the presence on the room window and update the
        presence information of the concerned user
        """
        from_room = presence['from'].bare
        tab = self.get_tab_by_name(from_room, tabs.MucTab)
        if tab:
            tab.handle_presence(presence)

    def rename_private_tabs(self, room_name, old_nick, new_nick):
        """
        Call this method when someone changes his/her nick in a MUC, this updates
        the name of all the opened private conversations with him/her
        """
        tab = self.get_tab_by_name('%s/%s' % (room_name, old_nick), tabs.PrivateTab)
        if tab:
            tab.rename_user(old_nick, new_nick)
        self.on_user_rejoined_private_conversation(room_name, new_nick)

    def on_user_left_private_conversation(self, room_name, nick, status_message):
        """
        The user left the MUC: add a message in the associated private conversation
        """
        tab = self.get_tab_by_name('%s/%s' % (room_name, nick), tabs.PrivateTab)
        if tab:
            tab.user_left(status_message, nick)

    def on_user_rejoined_private_conversation(self, room_name, nick):
        """
        The user joined a MUC: add a message in the associated private conversation
        """
        tab = self.get_tab_by_name('%s/%s' % (room_name, nick), tabs.PrivateTab)
        if tab:
            tab.user_rejoined(nick)

    def disable_private_tabs(self, room_name):
        """
        Disable private tabs when leaving a room
        """
        for tab in self.tabs:
            if tab.get_name().startswith(room_name) and isinstance(tab, tabs.PrivateTab):
                tab.deactivate()

    def enable_private_tabs(self,room_name):
        """
        Enable private tabs when joining a room
        """
        for tab in self.tabs:
            if tab.get_name().startswith(room_name) and isinstance(tab, tabs.PrivateTab):
                tab.activate()

    def on_user_changed_status_in_private(self, jid, msg):
        tab = self.get_tab_by_name(jid)
        if tab: # display the message in private
            tab.add_message(msg)

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
            if tab.get_name() == jid_from.bare and isinstance(tab, tabs.MucTab):
                if message['type'] == 'error':
                    return self.room_error(message, jid_from)
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
        tab = self.get_tab_by_name(jid.full, tabs.PrivateTab) # get the tab with the private conversation
        if not tab: # It's the first message we receive: create the tab
            tab = self.open_private_window(room_from, nick_from, False)
            if not tab:
                return
        self.events.trigger('private_msg', message)
        body = xhtml.get_body_from_message_stanza(message)
        if not body:
            return
        tab.add_message(body, time=None, nickname=nick_from,
                        forced_user=self.get_tab_by_name(room_from, tabs.MucTab).get_user_by_name(nick_from))
        conversation = self.get_tab_by_name(jid.full, tabs.PrivateTab)
        if conversation and conversation.remote_wants_chatstates is None:
            if message['chat_state']:
                conversation.remote_wants_chatstates = True
            else:
                conversation.remote_wants_chatstates = False
        if 'private' in config.get('beep_on', 'highlight private').split():
            curses.beep()
        logger.log_message(jid.full.replace('/', '\\'), nick_from, body)
        if conversation is self.current_tab():
            self.refresh_window()
        else:
            conversation.state = 'private'
            self.refresh_tab_win()

    def focus_tab_named(self, tab_name):
        for tab in self.tabs:
            if tab.get_name() == tab_name:
                self.command_win('%s' % (tab.nb,))

    def get_tab_of_conversation_with_jid(self, jid, create=True):
        """
        From a JID, get the tab containing the conversation with it.
        If none already exist, and create is "True", we create it
        and return it. Otherwise, we return None
        """
        # We first check if we have a conversation opened with this precise resource
        conversation = self.get_tab_by_name(jid.full, tabs.ConversationTab)
        if not conversation:
            # If not, we search for a conversation with the bare jid
            conversation = self.get_tab_by_name(jid.bare, tabs.ConversationTab)
            if not conversation:
                if create:
                    # We create the conversation with the bare Jid if nothing was found
                    conversation = self.open_conversation_window(jid.bare, False)
                else:
                    conversation = None
        return conversation

    def on_normal_message(self, message):
        """
        When receiving "normal" messages (from someone in our roster)
        """
        jid = message['from']
        self.events.trigger('conversation_msg', message)
        body = xhtml.get_body_from_message_stanza(message)
        if not body:
            if message['type'] == 'error':
                self.information(self.get_error_message_from_error_stanza(message), 'Error')
            return
        conversation = self.get_tab_of_conversation_with_jid(jid, create=True)
        if roster.get_contact_by_jid(jid.bare):
            remote_nick = roster.get_contact_by_jid(jid.bare).get_name() or jid.user
        else:
            remote_nick = jid.user
        conversation._text_buffer.add_message(body, nickname=remote_nick, nick_color=get_theme().COLOR_REMOTE_USER)
        if conversation.remote_wants_chatstates is None:
            if message['chat_state']:
                conversation.remote_wants_chatstates = True
            else:
                conversation.remote_wants_chatstates = False
        logger.log_message(jid.bare, remote_nick, body)
        if 'private' in config.get('beep_on', 'highlight private').split():
            curses.beep()
        if self.current_tab() is not conversation:
            conversation.state = 'private'
            self.refresh_tab_win()
        else:
            self.refresh_window()

    def on_presence(self, presence):
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
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
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
            if item.attrib['subscription'] == 'remove':
                roster.remove_contact(contact.get_bare_jid())
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def on_changed_subscription(self, presence):
        """
        Triggered whenever a presence stanza with a type of subscribe, subscribed, unsubscribe, or unsubscribed is received.
        """
        if presence['type'] == 'subscribe':
            jid = presence['from'].bare
            contact = roster.get_contact_by_jid(jid)
            if not contact:
                contact = Contact(jid)
                roster.add_contact(contact, jid)
            roster.edit_groups_of_contact(contact, [])
            contact.set_ask('asked')
            self.get_tab_by_number(0).state = 'highlight'
            self.information('%s wants to subscribe to your presence'%jid, 'Roster')
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def full_screen_redraw(self):
        """
        Completely erase and redraw the screen
        """
        self.stdscr.clear()
        self.stdscr.refresh()
        self.refresh_window()

    def call_for_resize(self):
        """
        Called when we want to resize the screen
        """
        tabs.Tab.resize(self.stdscr)
        self.resize_global_information_win()
        self.resize_global_info_bar()
        with g_lock:
            for tab in self.tabs:
                if config.get('lazy_resize', 'true') == 'true':
                    tab.need_resize = True
                else:
                    tab.resize()
            self.full_screen_redraw()

    def read_keyboard(self):
        """
        Get the next keyboard key pressed and returns it.
        read_char() has a timeout: it returns None when the timeout
        occurs. In that case we do not return (we loop until we get
        a non-None value), but we check for timed events instead.
        """
        res = read_char(self.stdscr)
        while res is None:
            self.check_timed_events()
            res = read_char(self.stdscr)
        return res

    def main_loop(self):
        """
        main loop waiting for the user to press a key
        """
        # curses.ungetch(0)    # FIXME
        while self.running:
            char_list = [common.replace_key_with_bound(key)\
                             for key in self.read_keyboard()]
            # Special case for M-x where x is a number
            if len(char_list) == 1:
                char = char_list[0]
                if char.startswith('M-') and len(char) == 3:
                    try:
                        nb = int(char[2])
                    except ValueError:
                        pass
                    else:
                        if self.current_tab().nb == nb:
                            self.go_to_previous_tab()
                        else:
                            self.command_win('%d' % nb)
                    # search for keyboard shortcut
                if char in self.key_func:
                    self.key_func[char]()
                else:
                    res = self.do_command(char)
                    if res:
                        self.refresh_window()
            else:
                for char in char_list:
                    self.do_command(char)
                self.refresh_window()
            self.doupdate()

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
            if isinstance(tab, tabs.ConversationTab):
                if tab.get_name() == jid:
                    return tab
        return None

    def get_tab_by_name(self, name, typ=None):
        """
        Get the tab with the given name.
        If typ is provided, return a tab of this type only
        """
        for tab in self.tabs:
            if tab.get_name() == name:
                if (typ and isinstance(tab, typ)) or\
                        not typ:
                    return tab
        return None

    def get_tab_by_number(self, number):
        for tab in self.tabs:
            if tab.nb == number:
                return tab
        return None

    def init_curses(self, stdscr):
        """
        ncurses initialization
        """
        self.background = False  # Bool to know if curses can draw
        # or be quiet while an other console app is running.
        curses.curs_set(1)
        curses.noecho()
        curses.nonl()
        curses.raw()
        stdscr.idlok(True)
        stdscr.keypad(True)
        curses.start_color()
        curses.use_default_colors()
        theming.reload_theme()
        curses.ungetch(" ")    # H4X: without this, the screen is
        stdscr.getkey()        # erased on the first "getkey()"

    def reset_curses(self):
        """
        Reset terminal capabilities to what they were before ncurses
        init
        """
        curses.echo()
        curses.nocbreak()
        curses.curs_set(1)
        curses.endwin()

    def refresh_window(self):
        """
        Refresh everything
        """
        self.current_tab().state = 'current'
        self.current_tab().refresh()
        self.doupdate()

    def refresh_tab_win(self):
        self.current_tab().tab_win.refresh()
        if self.current_tab().input:
            self.current_tab().input.refresh()
        self.doupdate()

    def add_tab(self, new_tab, focus=False):
        """
        Appends the new_tab in the tab list and
        focus it if focus==True
        """
        if self.current_tab().nb == 0:
            self.tabs.append(new_tab)
        else:
            for ta in self.tabs:
                if ta.nb == 0:
                    self.tabs.insert(self.tabs.index(ta), new_tab)
                    break
        if focus:
            self.command_win("%s" % new_tab.nb)

    def open_new_room(self, room, nick, focus=True):
        """
        Open a new tab.MucTab containing a muc Room, using the specified nick
        """
        new_tab = tabs.MucTab(room, nick)
        self.add_tab(new_tab, focus)
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
            if tab.state == 'private':
                self.command_win('%s' % tab.nb)
                return
        for tab in self.tabs:
            if tab.state == 'highlight':
                self.command_win('%s' % tab.nb)
                return
        for tab in self.tabs:
            if tab.state == 'message':
                self.command_win('%s' % tab.nb)
                return
        for tab in self.tabs:
            if tab.state == 'disconnected':
                self.command_win('%s' % tab.nb)
                return
        for tab in self.tabs:
            if isinstance(tab, tabs.ChatTab) and not tab.input.is_empty():
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

    def get_error_message_from_error_stanza(self, stanza):
        """
        Takes a stanza of the form <message type='error'><error/></message>
        and return a well formed string containing the error informations
        """
        sender = stanza.attrib['from']
        msg = stanza['error']['type']
        condition = stanza['error']['condition']
        code = stanza['error']['code']
        body = stanza['error']['text']
        if not body:
            if code in ERROR_AND_STATUS_CODES:
                body = ERROR_AND_STATUS_CODES[code]
            else:
                body = condition or _('Unknown error')
        if code:
            message = _('%(from)s: %(code)s - %(msg)s: %(body)s') % {'from':sender, 'msg':msg, 'body':body, 'code':code}
        else:
            message = _('%(from)s: %(msg)s: %(body)s') % {'from':sender, 'msg':msg, 'body':body}
        return message

    def room_error(self, error, room_name):
        """
        Display the error in the tab
        """
        tab = self.get_tab_by_name(room_name)
        error_message = self.get_error_message_from_error_stanza(error)
        self.add_message_to_text_buffer(tab._text_buffer, error_message)
        code = error['error']['code']
        if code == '401':
            msg = _('To provide a password in order to join the room, type "/join / password" (replace "password" by the real password)')
            self.add_message_to_text_buffer(tab._text_buffer, msg)
        if code == '409':
            if config.get('alternative_nickname', '') != '':
                self.command_join('%s/%s'% (tab.name, tab.own_nick+config.get('alternative_nickname', '')))
            else:
                self.add_message_to_text_buffer(tab._text_buffer, _('You can join the room with an other nick, by typing "/join /other_nick"'))
        self.refresh_window()

    def open_conversation_window(self, jid, focus=True):
        """
        open a new conversation tab and focus it if needed
        """
        for tab in self.tabs: # if the room exists, focus it and return
            if isinstance(tab, tabs.ConversationTab):
                if tab.get_name() == jid:
                    self.command_win('%s' % tab.nb)
                    return tab
        new_tab = tabs.ConversationTab(jid)
        # insert it in the rooms
        if not focus:
            new_tab.state = "private"
        self.add_tab(new_tab, focus)
        self.refresh_window()
        return new_tab

    def open_private_window(self, room_name, user_nick, focus=True):
        complete_jid = room_name+'/'+user_nick
        for tab in self.tabs: # if the room exists, focus it and return
            if isinstance(tab, tabs.PrivateTab):
                if tab.get_name() == complete_jid:
                    self.command_win('%s' % tab.nb)
                    return tab
        # create the new tab
        tab = self.get_tab_by_name(room_name, tabs.MucTab)
        if not tab:
            return None
        new_tab = tabs.PrivateTab(complete_jid, tab.own_nick)
        if not focus:
            new_tab.state = "private"
        # insert it in the tabs
        self.add_tab(new_tab, focus)
        self.refresh_window()
        return new_tab

    def on_groupchat_subject(self, message):
        """
        triggered when the topic is changed
        """
        nick_from = message['mucnick']
        room_from = message.getMucroom()
        tab = self.get_tab_by_name(room_from, tabs.MucTab)
        subject = message['subject']
        if not subject or not tab:
            return
        if nick_from:
            self.add_message_to_text_buffer(tab._text_buffer, _("%(nick)s set the subject to: %(subject)s") % {'nick':nick_from, 'subject':subject}, time=None)
        else:
            self.add_message_to_text_buffer(tab._text_buffer, _("The subject is: %(subject)s") % {'subject':subject}, time=None)
        tab.topic = subject
        if self.get_tab_by_name(room_from, tabs.MucTab) is self.current_tab():
            self.refresh_window()

    def on_groupchat_message(self, message):
        """
        Triggered whenever a message is received from a multi-user chat room.
        """
        if message['subject']:
            return
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
            return self.room_error(message, room_from)
        tab = self.get_tab_by_name(room_from, tabs.MucTab)
        if not tab:
            self.information(_("message received for a non-existing room: %s") % (room_from))
            return
        if tab.get_user_by_name(nick_from) and\
                tab.get_user_by_name(nick_from) in tab.ignores:
            return
        self.events.trigger('muc_msg', message)
        body = xhtml.get_body_from_message_stanza(message)
        if body:
            date = date if delayed == True else None
            tab.add_message(body, date, nick_from, history=True if date else False)
            if tab is self.current_tab():
                tab.text_win.refresh()
                tab.info_header.refresh(tab, tab.text_win)
            self.refresh_tab_win()
            if 'message' in config.get('beep_on', 'highlight private').split():
                curses.beep()

    def add_message_to_text_buffer(self, buff, txt, time=None, nickname=None, history=None):
        """
        Add the message to the room if possible, else, add it to the Info window
        (in the Info tab of the info window in the RosterTab)
        """
        if not buff:
            self.information('Trying to add a message in no room: %s' % txt, 'Error')
        else:
            buff.add_message(txt, time, nickname, history=history)

    def command_help(self, arg):
        """
        /help <command_name>
        """
        args = arg.split()
        if len(args) == 0:
            msg = _('Available commands are: ')
            for command in self.commands:
                msg += "%s " % command
            for command in self.current_tab().commands:
                msg += "%s " % command
            msg += _("\nType /help <command_name> to know what each command does")
        if len(args) >= 1:
            if args[0] in self.commands:
                msg = self.commands[args[0]][1]
            elif args[0] in self.current_tab().commands:
                msg = self.current_tab().commands[args[0]][1]
            else:
                msg = _('Unknown command: %s') % args[0]
        self.information(msg, 'Help')

    def completion_help(self, the_input):
        commands = list(self.commands.keys()) + list(self.current_tab().commands.keys())
        return the_input.auto_completion(commands, ' ')

    def command_status(self, arg):
        """
        /status <status> [msg]
        """
        args = common.shell_split(arg)
        if len(args) < 1:
            return
        if not args[0] in possible_show.keys():
            self.command_help('status')
            return
        show = possible_show[args[0]]
        if len(args) == 2:
            msg = args[1]
        elif len(args) > 2:
            msg = arg[len(args[0])+1:]
        else:
            msg = None
        pres = self.xmpp.make_presence()
        if msg:
            pres['status'] = msg
        pres['type'] = show
        pres.send()
        current = self.current_tab()
        if isinstance(current, tabs.MucTab) and current.joined and show in ('away', 'xa'):
            current.send_chat_state('inactive')
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab) and tab.joined:
                muc.change_show(self.xmpp, tab.name, tab.own_nick, show, msg)
        self.set_status(show, msg)
        if isinstance(current, tabs.MucTab) and current.joined and show not in ('away', 'xa'):
            current.send_chat_state('active')

    def completion_status(self, the_input):
        return the_input.auto_completion([status for status in possible_show], ' ')

    def command_load(self, arg):
        """
        /load <plugin>
        """
        args = arg.split()
        if len(args) != 1:
            self.command_help('load')
            return
        filename = args[0]
        self.plugin_manager.load(filename)

    def command_unload(self, arg):
        """
        /unload <plugin>
        """
        args = arg.split()
        if len(args) != 1:
            self.command_help('unload')
            return
        filename = args[0]
        self.plugin_manager.unload(filename)

    def command_plugins(self, arg):
        """
        /plugins
        """
        self.information("Plugins currently in use: %s" % repr(list(self.plugin_manager.plugins.keys())), 'Info')

    def command_message(self, arg):
        """
        /message <jid> [message]
        """
        args = arg.split()
        if len(args) < 1:
            self.command_help('message')
            return
        jid = args[0]
        tab = self.open_conversation_window(jid, focus=True)
        if len(args) > 1:
            tab.command_say(arg.strip()[len(jid)+1:])

    def command_version(self, arg):
        """
        /version <jid>
        """
        def callback(res):
            if not res:
                return self.information('Could not get the software version from %s' % (jid,), 'Warning')
            version = '%s is running %s version %s on %s' % (jid,
                                                             res.get('name') or _('an unknown software'),
                                                             res.get('version') or _('unknown'),
                                                             res.get('os') or _('on an unknown platform'))
            self.information(version, 'Info')

        args = common.shell_split(arg)
        if len(args) < 1:
            return self.command_help('version')
        jid = args[0]
        self.xmpp.plugin['xep_0092'].get_version(jid, callback=callback)

    def command_reconnect(self, args):
        """
        /reconnect
        """
        self.disconnect(reconnect=True)

    def command_list(self, arg):
        """
        /list <server>
        Opens a MucListTab containing the list of the room in the specified server
        """
        args = arg.split()
        if len(args) > 1:
            self.command_help('list')
            return
        elif len(args) == 0:
            if not isinstance(self.current_tab(), tabs.MucTab):
                return self.information('Please provide a server', 'Error')
            server = JID(self.current_tab().get_name()).server
        else:
            server = arg.strip()
        list_tab = tabs.MucListTab(server)
        self.add_tab(list_tab, True)
        self.xmpp.plugin['xep_0030'].get_items(jid=server, block=False, callback=list_tab.on_muc_list_item_received)

    def command_theme(self, arg):
        args = arg.split()
        if len(args) == 1:
            self.command_set('theme %s' % (args[0],))
        warning = theming.reload_theme()
        if warning:
            self.information(warning, 'Warning')
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
            nb = arg.strip()
        if self.current_tab().nb == nb:
            return
        self.previous_tab_nb = self.current_tab().nb
        self.current_tab().on_lose_focus()
        start = self.current_tab()
        self.tabs.append(self.tabs.pop(0))
        if isinstance(nb, int):
            while self.current_tab().nb != nb:
                self.tabs.append(self.tabs.pop(0))
                if self.current_tab() == start:
                    break
        else:
            while nb not in JID(self.current_tab().get_name()).user:
                self.tabs.append(self.tabs.pop(0))
                if self.current_tab() is start:
                    break
        self.current_tab().on_gain_focus()
        self.refresh_window()

    def completion_win(self, the_input):
        l = [JID(tab.get_name()).user for tab in self.tabs]
        l.remove('')
        return the_input.auto_completion(l, ' ')

    def completion_join(self, the_input):
        """
        Try to complete the server of the MUC's jid (for now only from the currently
        open ones)
        TODO: have a history of recently joined MUCs, and use that too
        """
        txt = the_input.get_text()
        if len(txt.split()) != 2:
            # we are not on the 1st argument of the command line
            return False
        jid = JID(txt.split()[1])
        if jid.server:
            if jid.resource or jid.full.endswith('/'):
                # we are writing the resource: complete the node
                if not the_input.last_completion:
                    response = self.xmpp.plugin['xep_0030'].get_items(jid=jid.server, block=True, timeout=1)
                    if response:
                        items = response['disco_items'].get_items()
                    else:
                        return True
                    items = ['%s/%s' % (tup[0], jid.resource) for tup in items]
                    for i in range(len(jid.server) + 2 + len(jid.resource)):
                        the_input.key_backspace()
                else:
                    items = []
                the_input.auto_completion(items, '')
            else:
                # we are writing the server: complete the server
                serv_list = []
                for tab in self.tabs:
                    if isinstance(tab, tabs.MucTab):
                        serv_list.append('%s@%s'% (jid.user, JID(tab.get_name()).host))
                the_input.auto_completion(serv_list, '')
        return True

    def completion_list(self, the_input):
        muc_serv_list = []
        for tab in self.tabs:   # TODO, also from an history
            if isinstance(tab, tabs.MucTab) and\
                    tab.get_name() not in muc_serv_list:
                muc_serv_list.append(JID(tab.get_name()).server)
        if muc_serv_list:
            return the_input.auto_completion(muc_serv_list, ' ')

    def command_join(self, arg, histo_length=None):
        """
        /join [room][/nick] [password]
        """
        args = common.shell_split(arg)
        password = None
        if len(args) == 0:
            tab = self.current_tab()
            if not isinstance(tab, tabs.MucTab) and not isinstance(tab, tabs.PrivateTab):
                return
            room = JID(tab.get_name()).bare
            nick = tab.own_nick
        else:
            info = JID(args[0])
            if info.resource == '':
                default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
                nick = config.get('default_nick', '')
                if nick == '':
                    nick = default
            else:
                nick = info.resource
            if info.bare == '':   # happens with /join /nickname, which is OK
                tab = self.current_tab()
                if not isinstance(tab, tabs.MucTab):
                    return
                room = tab.get_name()
                if nick == '':
                    nick = tab.own_nick
            else:
                room = info.bare
            if room.find('@') == -1: # no server is provided, like "/join hello"
                # use the server of the current room if available
                # check if the current room's name has a server
                if isinstance(self.current_tab(), tabs.MucTab) and\
                        self.current_tab().get_name().find('@') != -1:
                    room += '@%s' % JID(self.current_tab().get_name()).domain
                else:           # no server could be found, print a message and return
                    self.information(_("You didn't specify a server for the room you want to join"), 'Error')
                    return
        room = room.lower()
        tab = self.get_tab_by_name(room, tabs.MucTab)
        if len(args) == 2:       # a password is provided
            password = args[1]
        if tab and tab.joined:       # if we are already in the room
            self.focus_tab_named(tab.name)
            return
        if room.startswith('@'):
            room = room[1:]
        current_status = self.get_status()
        if tab and not tab.joined:
            muc.join_groupchat(self.xmpp, room, nick, password,
                               histo_length, current_status.message, current_status.show)
        if not tab:
            self.open_new_room(room, nick)
            muc.join_groupchat(self.xmpp, room, nick, password,
                               histo_length, current_status.message, current_status.show)
        else:
            tab.own_nick = nick
            tab.users = []
        self.enable_private_tabs(room)

    def get_bookmark_nickname(self, room_name):
        """
        Returns the nickname associated with a bookmark
        or the default nickname
        """
        bookmarks = config.get('rooms', '').split(':')
        jid = JID(room_name)
        for bookmark in bookmarks:
            if JID(bookmark).bare == jid.bare:
                return JID(bookmark).resource
        return self.own_nick

    def command_bookmark(self, arg):
        """
        /bookmark [room][/nick]
        """
        args = arg.split()
        nick = None
        if len(args) == 0 and not isinstance(self.current_tab(), tabs.MucTab):
            return
        if len(args) == 0:
            tab = self.current_tab()
            roomname = tab.get_name()
            if tab.joined:
                nick = tab.own_nick
        else:
            info = JID(args[0])
            if info.resource != '':
                nick = info.resource
            roomname = info.bare
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
            if JID(room).bare == roomname:
                bookmarked.remove(room)
                break
        bookmarked = ':'.join(bookmarked)
        if bookmarked:
            bookmarks = bookmarked+':'+res
        else:
            bookmarks = res
        config.set_and_save('rooms', bookmarks)
        self.information(_('Your bookmarks are now: %s') % bookmarks, 'Info')

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
        self.information(msg, 'Info')

    def close_tab(self, tab=None):
        """
        Close the given tab. If None, close the current one
        """
        tab = tab or self.current_tab()
        if isinstance(tab, tabs.RosterInfoTab):
            return              # The tab 0 should NEVER be closed
        del tab.key_func      # Remove self references
        del tab.commands      # and make the object collectable
        tab.on_close()
        self.tabs.remove(tab)
        import gc
        gc.collect()
        log.debug('___ Referrers of closing tab:\n%s\n______' % gc.get_referrers(tab))
        del tab
        self.refresh_window()

    def command_server_cycle(self, arg):
        """
        Do a /cycle on each room of the given server. If none, do it on the current tab
        """
        args = common.shell_split(arg)
        tab = self.current_tab()
        message = ""

        if len(args):
            domain = args[0]
            if len(args) > 1:
                message = args[1]
        else:
            if isinstance(tab, tabs.MucTab):
                domain = JID(tab.get_name()).domain
            else:
                self.information(_("No server specified"), "Error")
                return
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab) and JID(tab.get_name()).domain == domain:
                if tab.joined:
                    muc.leave_groupchat(tab.core.xmpp, tab.get_name(), tab.own_nick, message)
                tab.joined = False
                self.command_join(tab.get_name())

    def command_bind(self, arg):
        """
        Bind a key.
        """
        args = common.shell_split(arg)
        if len(args) != 2:
            return self.command_help('bind')
        config.set_and_save(args[0], args[1], section='bindings')
        self.information('%s is now bound to %s' % (args[0], args[1]), 'Info')

    def command_pubsub(self, args):
        """
        Opens a pubsub browser on the given domain
        """
        args = common.shell_split(args)
        if len(args) != 1:
            return self.command_help('pubsub')
        domain = args[0]
        tab = self.get_tab_by_name('%s@@pubsubbrowser' % (domain,), pubsub.PubsubBrowserTab)
        if tab:
            self.command_win('%s' % tab.nb)
        else:
            new_tab = pubsub.PubsubBrowserTab(domain)
            self.add_tab(new_tab, True)
        self.refresh_window()

    def go_to_room_number(self):
        """
        Read 2 more chars and go to the tab
        with the given number
        """
        char = self.read_keyboard()[0]
        try:
            nb1 = int(char)
        except ValueError:
            return
        char = self.read_keyboard()[0]
        try:
            nb2 = int(char)
        except ValueError:
            return
        self.command_win('%s%s' % (nb1, nb2))

    def information(self, msg, typ=''):
        """
        Displays an informational message in the "Info" buffer
        """
        nb_lines = self.information_buffer.add_message(msg, nickname=typ)
        if typ != '' and typ.lower() in config.get('information_buffer_popup_on',
                                           'error roster warning help info').split():
            popup_time = config.get('popup_time', 4) + (nb_lines - 1) * 2
            self.pop_information_win_up(nb_lines, popup_time)
        else:
            if self.information_win_size != 0:
                self.information_win.refresh()
                self.current_tab().input.refresh()

    def disconnect(self, msg='', reconnect=False):
        """
        Disconnect from remote server and correctly set the states of all
        parts of the client (for example, set the MucTabs as not joined, etc)
        """
        msg = msg or ''
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab) and tab.joined:
                tab.command_part(msg)
        roster.empty()
        self.save_config()
        # Ugly fix thanks to gmail servers
        self.xmpp.disconnect(reconnect)

    def command_quit(self, arg):
        """
        /quit
        """
        if len(arg.strip()) != 0:
            msg = arg
        else:
            msg = None
        self.disconnect(msg)
        self.running = False
        self.reset_curses()
        sys.exit()

    def save_config(self):
        """
        Save config in the file just before exit
        """
        roster.save_to_config_file()
        config.set_and_save('info_win_height', self.information_win_size, 'var')

    def do_command(self, key):
        if not key:
            return
        return self.current_tab().on_input(key)

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

    def remove_timed_event(self, event):
        if event and event in self.timed_events:
            self.timed_events.remove(event)

    def add_timed_event(self, event):
        self.timed_events.add(event)

    def check_timed_events(self):
        now = datetime.now()
        for event in self.timed_events:
            if event.has_timed_out(now):
                res = event()
                if not res:
                    self.timed_events.remove(event)
                    break

    def execute(self,line):
        """
        Execute the /command or just send the line on the current room
        """
        if line == "":
            return
        if line.startswith('/'):
            command = line.strip()[:].split()[0][1:]
            arg = line[2+len(command):] # jump the '/' and the ' '
            # example. on "/link 0 open", command = "link" and arg = "0 open"
            if command in self.commands:
                func = self.commands[command][0]
                func(arg)
                return
            else:
                self.information(_("Unknown command (%s)") % (command), _('Error'))

    def doupdate(self):
        if not self.running or self.background is True:
            return
        curses.doupdate()

    def send_message(self, msg):
        """
        Function to use in plugins to send a message in the current conversation.
        Returns False if the current tab is not a conversation tab
        """
        if not isinstance(self.current_tab(), tabs.ChatTab):
            return False
        self.current_tab().command_say(msg)
        return True

    def exec_command(self, command):
        """
        Execute an external command on the local or a remote
        machine, depending on the conf. For example, to open a link in a
        browser, do exec_command("firefox http://poezio.eu"),
        and this will call the command on the correct computer.
        The remote execution is done by writing the command on a fifo.
        That fifo has to be on the machine where poezio is running, and
        accessible (through sshfs for example) from the local machine (where
        poezio is not running). A very simple daemon reads on that fifo,
        and executes any command that is read in it.
        """
        command = '%s\n' % (command,)
        if config.get('exec_remote', 'false') == 'true':
            # We just write the command in the fifo
            if not self.remote_fifo:
                try:
                    self.remote_fifo = Fifo(os.path.join(config.get('remote_fifo_path', './'), 'poezio.fifo'), 'w')
                except (OSError, IOError) as e:
                    self.information('Could not open fifo file for writing: %s' % (e,), 'Error')
                    return
            try:
                self.remote_fifo.write(command)
            except (IOError) as e:
                self.information('Could not execute [%s]: %s' % (command.strip(), e,), 'Error')
                self.remote_fifo = None
        else:
            pass

    def get_conversation_messages(self):
        """
        Returns a list of all the messages in the current chat.
        If the current tab is not a ChatTab, returns None.

        Messages are namedtuples of the form
        ('txt nick_color time str_time nickname user')
        """
        if not isinstance(self.current_tab(), tabs.ChatTab):
            return None
        return self.current_tab().get_conversation_messages()
