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
import ssl

from functools import reduce
from hashlib import sha1
from datetime import datetime
from xml.etree import cElementTree as ET

import common
import theming
import logging
import singleton
import collections

from sleekxmpp import JID, InvalidJID
from common import safeJID
from sleekxmpp.xmlstream.stanzabase import StanzaBase
from sleekxmpp.xmlstream.handler import Callback

log = logging.getLogger(__name__)

import multiuserchat as muc
import tabs

import xhtml
import events
import pubsub
import windows
import connection
import timed_events
import bookmark

from plugin_manager import PluginManager

from data_forms import DataFormsTab
from config import config
from logger import logger
from roster import roster
from contact import Contact, Resource
from text_buffer import TextBuffer
from keyboard import read_char
from theming import get_theme
from fifo import Fifo
from windows import g_lock
from daemon import Executor

# http://xmpp.org/extensions/xep-0045.html#errorstatus
ERROR_AND_STATUS_CODES = {
    '401': _('A password is required'),
    '403': _('Permission denied'),
    '404': _('The room doesn’t exist'),
    '405': _('Your are not allowed to create a new room'),
    '406': _('A reserved nick must be used'),
    '407': _('You are not in the member list'),
    '409': _('This nickname is already in use or has been reserved'),
    '503': _('The maximum number of users has been reached'),
    }

# http://xmpp.org/extensions/xep-0086.html
DEPRECATED_ERRORS = {
    '302': _('Redirect'),
    '400': _('Bad request'),
    '401': _('Not authorized'),
    '402': _('Payment required'),
    '403': _('Forbidden'),
    '404': _('Not found'),
    '405': _('Not allowed'),
    '406': _('Not acceptable'),
    '407': _('Registration required'),
    '408': _('Request timeout'),
    '409': _('Conflict'),
    '500': _('Internal server error'),
    '501': _('Feature not implemented'),
    '502': _('Remote server error'),
    '503': _('Service unavailable'),
    '504': _('Remote server timeout'),
    '510': _('Disconnected'),
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
    “Main” class of poezion
    """

    def __init__(self):
        # All uncaught exception are given to this callback, instead
        # of being displayed on the screen and exiting the program.
        sys.excepthook = self.on_exception
        self.connection_time = time.time()
        self.status = Status(show=None, message='')
        self.running = True
        self.xmpp = singleton.Singleton(connection.Connection)
        self.xmpp.core = self
        roster.set_node(self.xmpp.client_roster)
        self.paused = False
        self.remote_fifo = None
        # a unique buffer used to store global informations
        # that are displayed in almost all tabs, in an
        # information window.
        self.information_buffer = TextBuffer()
        self.information_win_size = config.get('info_win_height', 2, 'var')
        self.information_win = windows.TextWin(300)
        self.information_buffer.add_window(self.information_win)

        self.tab_win = windows.GlobalInfoBar()
        # Number of xml tabs opened, used to avoid useless memory consumption
        self.xml_tabs = 0
        self.xml_buffer = TextBuffer()

        self.tabs = []
        self._current_tab_nb = 0
        self.previous_tab_nb = 0

        self.own_nick = config.get('default_nick', '') or self.xmpp.boundjid.user

        self.plugins_autoloaded = False
        self.plugin_manager = PluginManager(self)
        self.events = events.EventHandler()

        # global commands, available from all tabs
        # a command is tuple of the form:
        # (the function executing the command. Takes a string as argument,
        #  a string representing the help message,
        #  a completion function, taking a Input as argument. Can be None)
        #  The completion function should return True if a completion was
        #  made ; False otherwise
        self.commands = {
            'help': (self.command_help, '\_o< KOIN KOIN KOIN', self.completion_help),
            'join': (self.command_join, _("Usage: /join [room_name][@server][/nick] [password]\nJoin: Join the specified room. You can specify a nickname after a slash (/). If no nickname is specified, you will use the default_nick in the configuration file. You can omit the room name: you will then join the room you\'re looking at (useful if you were kicked). You can also provide a room_name without specifying a server, the server of the room you're currently in will be used. You can also provide a password to join the room.\nExamples:\n/join room@server.tld\n/join room@server.tld/John\n/join room2\n/join /me_again\n/join\n/join room@server.tld/my_nick password\n/join / password"), self.completion_join),
            'exit': (self.command_quit, _("Usage: /exit\nExit: Just disconnect from the server and exit poezio."), None),
            'quit': (self.command_quit, _("Usage: /quit\nQuit: Just disconnect from the server and exit poezio."), None),
            'next': (self.rotate_rooms_right, _("Usage: /next\nNext: Go to the next room."), None),
            'prev': (self.rotate_rooms_left, _("Usage: /prev\nPrev: Go to the previous room."), None),
            'win': (self.command_win, _("Usage: /win <number>\nWin: Go to the specified room."), self.completion_win),
            'w': (self.command_win, _("Usage: /w <number>\nW: Go to the specified room."), self.completion_win),
            'move_tab': (self.command_move_tab, _("Usage: /move_tab <source> <destination>\nMove Tab: Insert the <source> tab at the position of <destination>. This will make the following tabs shift in some cases (refer to the documentation). A tab can be designated by its number or by the beginning of its address."), self.completion_move_tab),
            'show': (self.command_status, _('Usage: /show <availability> [status message]\nShow: Sets your availability and (optionally) your status message. The <availability> argument is one of \"available, chat, away, afk, dnd, busy, xa\" and the optional [status message] argument will be your status message.'), self.completion_status),
            'status': (self.command_status, _('Usage: /status <availability> [status message]\nStatus: Sets your availability and (optionally) your status message. The <availability> argument is one of \"available, chat, away, afk, dnd, busy, xa\" and the optional [status message] argument will be your status message.'), self.completion_status),
            'bookmark_local': (self.command_bookmark_local, _("Usage: /bookmark_local [roomname][/nick]\nBookmark Local: Bookmark locally the specified room (you will then auto-join it on each poezio start). This commands uses almost the same syntaxe as /join. Type /help join for syntaxe examples. Note that when typing \"/bookmark\" on its own, the room will be bookmarked with the nickname you\'re currently using in this room (instead of default_nick)"), self.completion_bookmark_local),
            'bookmark': (self.command_bookmark, _("Usage: /bookmark [roomname][/nick] [autojoin] [password]\nBookmark: Bookmark online the specified room (you will then auto-join it on each poezio start if autojoin is specified and is 'true'). This commands uses almost the same syntaxe as /join. Type /help join for syntaxe examples. Note that when typing \"/bookmark\" on its own, the room will be bookmarked with the nickname you\'re currently using in this room (instead of default_nick)"), self.completion_bookmark),
            'set': (self.command_set, _("Usage: /set [plugin|][section] <option> [value]\nSet: Set the value of an option in your configuration file. You can, for example, change your default nickname by doing `/set default_nick toto` or your resource with `/set resource blabla`. You can also set options in specific sections with `/set bindings M-i ^i` or in specific plugin with `/set mpd_client| host 127.0.0.1`"), self.completion_set),
            'theme': (self.command_theme, _('Usage: /theme [theme_name]\nTheme: Reload the theme defined in the config file. If theme_name is provided, set that theme before reloading it.'), self.completion_theme),
            'list': (self.command_list, _('Usage: /list\nList: Get the list of public chatrooms on the specified server.'), self.completion_list),
            'message': (self.command_message, _('Usage: /message <jid> [optional message]\nMessage: Open a conversation with the specified JID (even if it is not in our roster), and send a message to it, if the message is specified.'), self.completion_version),
            'version': (self.command_version, _('Usage: /version <jid>\nVersion: Get the software version of the given JID (usually its XMPP client and Operating System).'), self.completion_version),
            'connect': (self.command_reconnect, _('Usage: /connect\nConnect: Disconnect from the remote server if you are currently connected and then connect to it again.'), None),
            'server_cycle': (self.command_server_cycle, _('Usage: /server_cycle [domain] [message]\nServer Cycle: Disconnect and reconnect in all the rooms in domain.'), self.completion_server_cycle),
            'bind': (self.command_bind, _('Usage: /bind <key> <equ>\nBind: Bind a key to an other key or to a “command”. For example "/bind ^H KEY_UP" makes Control + h do the same same as the Up key.'), None),
            'load': (self.command_load, _('Usage: /load <plugin>\nLoad: Load the specified plugin'), self.plugin_manager.completion_load),
            'unload': (self.command_unload, _('Usage: /unload <plugin>\nUnload: Unload the specified plugin'), self.plugin_manager.completion_unload),
            'plugins': (self.command_plugins, _('Usage: /plugins\nPlugins: Show the plugins in use.'), None),
            'presence': (self.command_presence, _('Usage: /presence <JID> [type] [status]\nPresence: Send a directed presence to <JID> and using [type] and [status] if provided.'), self.completion_presence),
            'rawxml': (self.command_rawxml, _('Usage: /rawxml\nRawXML: Send a custom xml stanza.'), None),
            'invite': (self.command_invite, _("Usage: /invite <jid> <room> [reason]\nInvite: Invite jid in room with reason."), self.completion_invite),
            'decline': (self.command_decline, _("Usage: /decline <room> [reason]\nDecline: Decline the invitation to room with or without reason."), self.completion_decline),
            'invitations': (self.command_invitations, _("Usage: /invites\nInvites: Show the pending invitations."), None),
            'bookmarks': (self.command_bookmarks, _("Usage: /bookmarks\nBookmarks: Show the current bookmarks."), None),
            'remove_bookmark': (self.command_remove_bookmark, _("Usage: /remove_bookmark [jid]\nRemove Bookmark: Remove the specified bookmark, or the bookmark on the current tab, if any."), self.completion_remove_bookmark),
            'xml_tab': (self.command_xml_tab, _("Usage: /xml_tab\nXML Tab: Open an XML tab."), None),
            'runkey': (self.command_runkey, _("Usage: /runkey <key>\nRunkey: Execute the action defined for <key>."), self.completion_runkey),
            'self': (self.command_self, _("Usage: /self\nSelf: Remind you of who you are."), None),
            'activity': (self.command_activity, _("Usage: /activity <jid>\nActivity: Informs you of the last activity of a JID."), self.completion_activity),
        }

        # We are invisible
        if config.get('send_initial_presence', 'true').lower() == 'false':
            del self.commands['status']
            del self.commands['show']

        self.key_func = KeyDict()
        # Key bindings associated with handlers
        # and pseudo-keys used to map actions below.
        key_func = {
            "KEY_PPAGE": self.scroll_page_up,
            "KEY_NPAGE": self.scroll_page_down,
            "^B": self.scroll_line_up,
            "^F": self.scroll_line_down,
            "^X": self.scroll_half_down,
            "^S": self.scroll_half_up,
            "KEY_F(5)": self.rotate_rooms_left,
            "^P": self.rotate_rooms_left,
            'kLFT3': self.rotate_rooms_left,
            "KEY_F(6)": self.rotate_rooms_right,
            "^N": self.rotate_rooms_right,
            'kRIT3': self.rotate_rooms_right,
            "KEY_F(4)": self.toggle_left_pane,
            "KEY_F(7)": self.shrink_information_win,
            "KEY_F(8)": self.grow_information_win,
            "KEY_RESIZE": self.call_for_resize,
            'M-e': self.go_to_important_room,
            'M-r': self.go_to_roster,
            'M-z': self.go_to_previous_tab,
            '^L': self.full_screen_redraw,
            'M-j': self.go_to_room_number,
            'M-d': self.scroll_info_up,
            'M-c': self.scroll_info_down,
        ######## actions mappings ##########
            '_bookmark': self.command_bookmark,
            '_bookmark_local': self.command_bookmark_local,
            '_close_tab': self.close_tab,
            '_disconnect': self.disconnect,
            '_quit': self.command_quit,
            '_reconnect': self.command_reconnect,
            '_redraw_screen': self.full_screen_redraw,
            '_reload_theme': self.command_theme,
            '_remove_bookmark': self.command_remove_bookmark,
            '_room_left': self.rotate_rooms_left,
            '_room_right': self.rotate_rooms_right,
            '_show_roster': self.go_to_roster,
            '_scroll_down': self.scroll_page_down,
            '_scroll_up': self.scroll_page_up,
            '_scroll_info_up': self.scroll_info_up,
            '_scroll_info_down': self.scroll_info_down,
            '_server_cycle': self.command_server_cycle,
            '_show_bookmarks': self.command_bookmarks,
            '_show_important_room': self.go_to_important_room,
            '_show_invitations': self.command_invitations,
            '_show_plugins': self.command_plugins,
            '_show_xmltab': self.command_xml_tab,
            '_toggle_pane': self.toggle_left_pane,
        ###### status actions ######
            '_available': lambda: self.command_status('available'),
            '_away': lambda: self.command_status('away'),
            '_chat': lambda: self.command_status('chat'),
            '_dnd': lambda: self.command_status('dnd'),
            '_xa': lambda: self.command_status('xa'),
        ##### Custom actions ########
            '_exc_': lambda arg: self.try_execute(arg),
        }
        self.key_func.update(key_func)

        # Add handlers
        self.xmpp.add_event_handler('connected', self.on_connected)
        self.xmpp.add_event_handler('disconnected', self.on_disconnected)
        self.xmpp.add_event_handler('no_auth', self.on_failed_auth)
        self.xmpp.add_event_handler("session_start", self.on_session_start)
        self.xmpp.add_event_handler("groupchat_presence", self.on_groupchat_presence)
        self.xmpp.add_event_handler("groupchat_message", self.on_groupchat_message)
        self.xmpp.add_event_handler("groupchat_invite", self.on_groupchat_invite)
        self.xmpp.add_event_handler("groupchat_decline", self.on_groupchat_decline)
        self.xmpp.add_event_handler("groupchat_config_status", self.on_status_codes)
        self.xmpp.add_event_handler("groupchat_subject", self.on_groupchat_subject)
        self.xmpp.add_event_handler("message", self.on_message)
        self.xmpp.add_event_handler("got_online" , self.on_got_online)
        self.xmpp.add_event_handler("got_offline" , self.on_got_offline)
        self.xmpp.add_event_handler("roster_update", self.on_roster_update)
        self.xmpp.add_event_handler("changed_status", self.on_presence)
        self.xmpp.add_event_handler("roster_subscription_request", self.on_subscription_request)
        self.xmpp.add_event_handler("roster_subscription_authorized", self.on_subscription_authorized)
        self.xmpp.add_event_handler("roster_subscription_remove", self.on_subscription_remove)
        self.xmpp.add_event_handler("roster_subscription_removed", self.on_subscription_removed)
        self.xmpp.add_event_handler("message_xform", self.on_data_form)
        self.xmpp.add_event_handler("chatstate_active", self.on_chatstate_active)
        self.xmpp.add_event_handler("chatstate_composing", self.on_chatstate_composing)
        self.xmpp.add_event_handler("chatstate_paused", self.on_chatstate_paused)
        self.xmpp.add_event_handler("chatstate_gone", self.on_chatstate_gone)
        self.xmpp.add_event_handler("chatstate_inactive", self.on_chatstate_inactive)
        self.xmpp.add_event_handler("attention", self.on_attention)
        self.xmpp.add_event_handler("ssl_cert", self.validate_ssl)
        self.all_stanzas = Callback('custom matcher', connection.MatchAll(None), self.incoming_stanza)
        self.xmpp.register_handler(self.all_stanzas)

        self.initial_joins = []

        self.timed_events = set()

        self.connected_events = {}

        self.pending_invites = {}

    def sighup_handler(self, num, stack):
        """
        Handle SIGHUP (1)
        When caught, reload all the possible files.
        """
        log.debug("SIGHUP caught, reloading the files…")
        # reload all log files
        log.debug("Reloading the log files…")
        logger.reload_all()
        log.debug("Log files reloaded.")
        # reload the theme
        log.debug("Reloading the theme…")
        self.command_theme("")
        log.debug("Theme reloaded.")
        # reload the config from the disk
        log.debug("Reloading the config…")
        config.__init__(config.file_name)
        log.debug("Config reloaded.")

    def autoload_plugins(self):
        """
        Load the plugins on startup.
        """
        plugins = config.get('plugins_autoload', '')
        for plugin in plugins.split():
            self.plugin_manager.load(plugin)
        self.plugins_autoloaded = True

    def start(self):
        """
        Init curses, create the first tab, etc
        """
        self.stdscr = curses.initscr()
        self.init_curses(self.stdscr)
        self.call_for_resize()
        default_tab = tabs.RosterInfoTab()
        default_tab.on_gain_focus()
        self.tabs.append(default_tab)
        self.information(_('Welcome to poezio!'))
        if config.get('firstrun', ''):
            self.information(_(
                'It seems that it is the first time you start poezio.\n' + \
                'The online help is here http://poezio.eu/en/documentation.php.\n' + \
                'By default, you are in poezio’s chatroom, where you can ask for help or tell us how great it is.\n' + \
                'Just press Ctrl-n.' \
            ))
        self.refresh_window()

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

    def main_loop(self):
        """
        main loop waiting for the user to press a key
        """
        def replace_line_breaks(key):
            if key == '^J':
                return '\n'
            return key
        def separate_chars_from_bindings(char_list):
            """
            returns a list of lists. For example if you give
            ['a', 'b', 'KEY_BACKSPACE', 'n', 'u'], this function returns
            [['a', 'b'], ['KEY_BACKSPACE'], ['n', 'u']]

            This way, in case of lag (for example), we handle the typed text
            by “batch” as much as possible (instead of one char at a time,
            which implies a refresh after each char, which is very slow),
            but we still handle the special chars (backspaces, arrows,
            ctrl+x ou alt+x, etc) one by one, which avoids the issue of
            printing them OR ignoring them in that case.  This should
            resolve the “my ^W are ignored when I lag ;(”.
            """
            res = []
            current = []
            for char in char_list:
                assert(len(char) > 0)
                if len(char) == 1:
                    current.append(char)
                else:
                    # special case for the ^I key, it’s considered as \t
                    # only when pasting some text, otherwise that’s the ^I
                    # (or M-i) key, which stands for completion by default.
                    if char == '^I' and len(char_list) != 1:
                        current.append('\t')
                        continue
                    if current:
                        res.append(current)
                        current = []
                    res.append([char])
            if current:
                res.append(current)
            return res
        while self.running:
            if self.paused: continue
            big_char_list = [common.replace_key_with_bound(key)\
                             for key in self.read_keyboard()]
            # whether to refresh after ALL keys have been handled
            for char_list in separate_chars_from_bindings(big_char_list):
                if self.paused:
                    self.current_tab().input.do_command(char_list[0])
                    self.current_tab().input.prompt()
                    continue
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
                    func = self.key_func.get(char, None)
                    if func:
                        func()
                    else:
                        res = self.do_command(replace_line_breaks(char), False)
                else:
                    self.do_command(''.join(char_list), True)
            self.doupdate()

    def save_config(self):
        """
        Save config in the file just before exit
        """
        roster.save_to_config_file()
        config.set_and_save('info_win_height', self.information_win_size, 'var')

    def on_roster_enter_key(self, roster_row):
        """
        when enter is pressed on the roster window
        """
        if isinstance(roster_row, Contact):
            if not self.get_conversation_by_jid(roster_row.bare_jid, False):
                self.open_conversation_window(roster_row.bare_jid)
            else:
                self.focus_tab_named(roster_row.bare_jid)
        if isinstance(roster_row, Resource):
            if not self.get_conversation_by_jid(roster_row.jid.full, False):
                self.open_conversation_window(roster_row.jid.full)
            else:
                self.focus_tab_named(roster_row.jid.full)
        self.refresh_window()

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

    def insert_input_text(self, text):
        """
        Insert the given text into the current input
        """
        self.do_command(text, True)


##################### Anything related to command execution ###################

    def execute(self, line):
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
            e = Executor(command.strip())
            try:
                e.start()
            except ValueError as e: # whenever shlex fails
                self.information('%s' % (e,), 'Error')


    def do_command(self, key, raw):
        if not key:
            return
        return self.current_tab().on_input(key, raw)


    def try_execute(self, line):
        """
        Try to execute a command in the current tab
        """
        line = '/' + line
        try:
            self.current_tab().execute_command(line)
        except:
            import traceback
            log.debug('Execute failed:\n%s', traceback.format_exc())


########################## TImed Events #######################################

    def remove_timed_event(self, event):
        """Remove an existing timed event"""
        if event and event in self.timed_events:
            self.timed_events.remove(event)

    def add_timed_event(self, event):
        """Add a new timed event"""
        self.timed_events.add(event)

    def check_timed_events(self):
        """Check for the execution of timed events"""
        now = datetime.now()
        for event in self.timed_events:
            if event.has_timed_out(now):
                res = event()
                if not res:
                    self.timed_events.remove(event)
                    break


####################### XMPP-related actions ##################################

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

    def get_bookmark_nickname(self, room_name):
        """
        Returns the nickname associated with a bookmark
        or the default nickname
        """
        bm = bookmark.get_by_jid(room_name)
        if bm:
            return bm.nick
        return self.own_nick

    def disconnect(self, msg='', reconnect=False):
        """
        Disconnect from remote server and correctly set the states of all
        parts of the client (for example, set the MucTabs as not joined, etc)
        """
        msg = msg or ''
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab) and tab.joined:
                tab.command_part(msg)
        self.save_config()
        # Ugly fix thanks to gmail servers
        self.xmpp.disconnect(reconnect)

    def send_message(self, msg):
        """
        Function to use in plugins to send a message in the current conversation.
        Returns False if the current tab is not a conversation tab
        """
        if not isinstance(self.current_tab(), tabs.ChatTab):
            return False
        self.current_tab().command_say(msg)
        return True

    def get_error_message(self, stanza, deprecated=False):
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
            if deprecated:
                if code in DEPRECATED_ERRORS:
                    body = DEPRECATED_ERRORS[code]
                else:
                    body = condition or _('Unknown error')
            else:
                if code in ERROR_AND_STATUS_CODES:
                    body = ERROR_AND_STATUS_CODES[code]
                else:
                    body = condition or _('Unknown error')
        if code:
            message = _('%(from)s: %(code)s - %(msg)s: %(body)s') % {'from':sender, 'msg':msg, 'body':body, 'code':code}
        else:
            message = _('%(from)s: %(msg)s: %(body)s') % {'from':sender, 'msg':msg, 'body':body}
        return message


####################### Tab logic-related things ##############################

    ### Tab getters ###

    def current_tab(self):
        """
        returns the current room, the one we are viewing
        """
        self.current_tab_nb = self.current_tab_nb
        return self.tabs[self.current_tab_nb]

    def get_conversation_by_jid(self, jid, create=True):
        """
        From a JID, get the tab containing the conversation with it.
        If none already exist, and create is "True", we create it
        and return it. Otherwise, we return None
        """
        jid = safeJID(jid)
        # We first check if we have a conversation opened with this precise resource
        conversation = self.get_tab_by_name(jid.full, tabs.ConversationTab)
        if not conversation:
            # If not, we search for a conversation with the bare jid
            conversation = self.get_tab_by_name(jid.bare, tabs.ConversationTab)
            if not conversation:
                if create:
                    # We create the conversation with the full Jid if nothing was found
                    conversation = self.open_conversation_window(jid.full, False)
                else:
                    conversation = None
        return conversation

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
        if 0 <= number < len(self.tabs):
            return self.tabs[number]
        return None

    def add_tab(self, new_tab, focus=False):
        """
        Appends the new_tab in the tab list and
        focus it if focus==True
        """
        self.tabs.append(new_tab)
        if focus:
            self.command_win("%s" % new_tab.nb)

    def insert_tab_nogaps(self, old_pos, new_pos):
        """
        Move tabs without creating gaps
        old_pos: old position of the tab
        new_pos: desired position of the tab
        """
        tab = self.tabs[old_pos]
        if new_pos < old_pos:
            self.tabs.pop(old_pos)
            self.tabs.insert(new_pos, tab)
        elif new_pos > old_pos:
            self.tabs.insert(new_pos, tab)
            self.tabs.remove(tab)
        else:
            return False
        return True

    def insert_tab_gaps(self, old_pos, new_pos):
        """
        Move tabs and create gaps in the eventual remaining space
        old_pos: old position of the tab
        new_pos: desired position of the tab
        """
        tab = self.tabs[old_pos]
        target = None if new_pos >= len(self.tabs) else self.tabs[new_pos]
        if not target:
            if new_pos < len(self.tabs):
                self.tabs[new_pos], self.tabs[old_pos] = self.tabs[old_pos], tabs.GapTab()
            else:
                self.tabs.append(self.tabs[old_pos])
                self.tabs[old_pos] = tabs.GapTab()
        else:
            if new_pos > old_pos:
                self.tabs.insert(new_pos, tab)
                self.tabs[old_pos] = tabs.GapTab()
                i = self.tabs.index(tab)
            elif new_pos < old_pos:
                self.tabs[old_pos] = tabs.GapTab()
                self.tabs.insert(new_pos, tab)
            else:
                return False
            done = False
            # Remove the first Gap on the right in the list
            # in order to prevent global shifts when there is empty space
            while not done:
                i += 1
                if i >= len(self.tabs):
                    done = True
                elif not self.tabs[i]:
                    self.tabs.pop(i)
                    done = True
        # Remove the trailing gaps
        i = len(self.tabs) - 1
        while isinstance(self.tabs[i], tabs.GapTab):
            self.tabs.pop()
            i -= 1
        return True

    def insert_tab(self, old_pos, new_pos=99999):
        """
        Insert a tab at a position, changing the number of the following tabs
        returns False if it could not move the tab, True otherwise
        """
        if old_pos <= 0 or old_pos >= len(self.tabs):
            return False
        elif new_pos <= 0:
            return False
        elif new_pos ==old_pos:
            return False
        elif not self.tabs[old_pos]:
            return False
        if config.get('create_gaps', 'false').lower() == 'true':
            return self.insert_tab_gaps(old_pos, new_pos)
        return self.insert_tab_nogaps(old_pos, new_pos)

    ### Move actions (e.g. go to next room) ###

    def rotate_rooms_right(self, args=None):
        """
        rotate the rooms list to the right
        """
        self.current_tab().on_lose_focus()
        self.current_tab_nb += 1
        while not self.tabs[self.current_tab_nb]:
            self.current_tab_nb += 1
        self.current_tab().on_gain_focus()
        self.refresh_window()

    def rotate_rooms_left(self, args=None):
        """
        rotate the rooms list to the right
        """
        self.current_tab().on_lose_focus()
        self.current_tab_nb -= 1
        while not self.tabs[self.current_tab_nb]:
            self.current_tab_nb -= 1
        self.current_tab().on_gain_focus()
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

    def go_to_roster(self):
        self.command_win('0')

    def go_to_previous_tab(self):
        self.command_win('%s' % (self.previous_tab_nb,))

    def go_to_important_room(self):
        """
        Go to the next room with activity, in the order defined in the
        dict tabs.STATE_PRIORITY
        """
        # shortcut
        priority = tabs.STATE_PRIORITY
        tab_refs = {}
        # put all the active tabs in a dict of lists by state
        for tab in self.tabs:
            if not tab:
                continue
            if tab.state not in tab_refs:
                tab_refs[tab.state] = [tab]
            else:
                tab_refs[tab.state].append(tab)
        # sort the state by priority and remove those with negative priority
        states = sorted(tab_refs.keys(), key=(lambda x: priority.get(x, 0)), reverse=True)
        states = [state for state in states if priority.get(state, -1) >= 0]

        for state in states:
            for tab in tab_refs[state]:
                if tab.nb < self.current_tab_nb and tab_refs[state][-1].nb > self.current_tab_nb:
                    continue
                self.command_win('%s' % tab.nb)
                return
        return

    def focus_tab_named(self, tab_name):
        for tab in self.tabs:
            if tab.get_name() == tab_name:
                self.command_win('%s' % (tab.nb,))

    @property
    def current_tab_nb(self):
        return self._current_tab_nb

    @current_tab_nb.setter
    def current_tab_nb(self, value):
        if value >= len(self.tabs):
            self._current_tab_nb = 0
        elif value < 0:
            self._current_tab_nb = len(self.tabs) - 1
        else:
            self._current_tab_nb = value

    ### Opening actions ###

    def open_conversation_window(self, jid, focus=True):
        """
        Open a new conversation tab and focus it if needed
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
        """
        Open a Private conversation in a MUC and focus if needed.
        """
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
        if hasattr(tab, 'directed_presence'):
            new_tab.directed_presence = tab.directed_presence
        if not focus:
            new_tab.state = "private"
        # insert it in the tabs
        self.add_tab(new_tab, focus)
        self.refresh_window()
        tab.privates.append(new_tab)
        return new_tab

    def open_new_room(self, room, nick, focus=True):
        """
        Open a new tab.MucTab containing a muc Room, using the specified nick
        """
        new_tab = tabs.MucTab(room, nick)
        self.add_tab(new_tab, focus)
        self.refresh_window()

    def open_new_form(self, form, on_cancel, on_send, **kwargs):
        """
        Open a new tab containing the form
        The callback are called with the completed form as parameter in
        addition with kwargs
        """
        form_tab = DataFormsTab(form, on_cancel, on_send, kwargs)
        self.add_tab(form_tab, True)

    ### Modifying actions ###
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

    def disable_private_tabs(self, room_name, reason='\x195}You left the chatroom\x193}'):
        """
        Disable private tabs when leaving a room
        """
        for tab in self.tabs:
            if isinstance(tab, tabs.PrivateTab) and tab.get_name().startswith(room_name):
                tab.deactivate(reason=reason)

    def enable_private_tabs(self, room_name, reason='\x195}You joined the chatroom\x193}'):
        """
        Enable private tabs when joining a room
        """
        for tab in self.tabs:
            if tab.get_name().startswith(room_name) and isinstance(tab, tabs.PrivateTab):
                tab.activate(reason=reason)

    def on_user_changed_status_in_private(self, jid, msg):
        tab = self.get_tab_by_name(jid)
        if tab: # display the message in private
            tab.add_message(msg)

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
        nb = tab.nb
        if config.get('create_gaps', 'false').lower() == 'true':
            if nb >= len(self.tabs) - 1:
                self.tabs.remove(tab)
            else:
                self.tabs[nb] = tabs.GapTab()
        else:
            self.tabs.remove(tab)
        if tab and tab.get_name() in logger.fds:
            logger.fds[tab.get_name()].close()
            log.debug("Log file for %s closed.", tab.get_name())
            del logger.fds[tab.get_name()]
        if self.current_tab_nb >= len(self.tabs):
            self.current_tab_nb = len(self.tabs) - 1
        while not self.tabs[self.current_tab_nb]:
            self.current_tab_nb -= 1
        self.refresh_window()
        import gc
        gc.collect()
        log.debug('___ Referrers of closing tab:\n%s\n______', gc.get_referrers(tab))
        del tab

    def add_information_message_to_conversation_tab(self, jid, msg):
        """
        Search for a ConversationTab with the given jid (full or bare), if yes, add
        the given message to it
        """
        tab = self.get_tab_by_name(jid, tabs.ConversationTab)
        if tab:
            self.add_message_to_text_buffer(tab._text_buffer, msg)


####################### Curses and ui-related stuff ###########################

    def doupdate(self):
        if not self.running or self.background is True:
            return
        curses.doupdate()

    def information(self, msg, typ=''):
        """
        Displays an informational message in the "Info" buffer
        """
        filter_messages = config.get('filter_info_messages', '').split(':')
        for words in filter_messages:
            if words and words in msg:
                log.debug('Did not show the message:\n\t%s> %s', typ, msg)
                return False
        nb_lines = self.information_buffer.add_message(msg, nickname=typ)
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()
        elif typ != '' and typ.lower() in config.get('information_buffer_popup_on',
                                           'error roster warning help info').split():
            popup_time = config.get('popup_time', 4) + (nb_lines - 1) * 2
            self.pop_information_win_up(nb_lines, popup_time)
        else:
            if self.information_win_size != 0:
                self.information_win.refresh()
                self.current_tab().input.refresh()
        return True

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

    @property
    def informations(self):
        return self.information_buffer

    def refresh_window(self):
        """
        Refresh everything
        """
        self.current_tab().state = 'current'
        self.current_tab().refresh()
        self.doupdate()

    def refresh_tab_win(self):
        """
        Refresh the window containing the tab list
        """
        self.current_tab().refresh_tab_win()
        if self.current_tab().input:
            self.current_tab().input.refresh()
        self.doupdate()

    def scroll_page_down(self, args=None):
        """
        Scroll a page down, if possible.
        Returns True on success, None on failure.
        """
        if self.current_tab().on_scroll_down():
            self.refresh_window()
            return True

    def scroll_page_up(self, args=None):
        """
        Scroll a page up, if possible.
        Returns True on success, None on failure.
        """
        if self.current_tab().on_scroll_up():
            self.refresh_window()
            return True

    def scroll_line_up(self, args=None):
        """
        Scroll a line up, if possible.
        Returns True on success, None on failure.
        """
        if self.current_tab().on_line_up():
            self.refresh_window()
            return True

    def scroll_line_down(self, args=None):
        """
        Scroll a line down, if possible.
        Returns True on success, None on failure.
        """
        if self.current_tab().on_line_down():
            self.refresh_window()
            return True

    def scroll_half_up(self, args=None):
        """
        Scroll half a screen down, if possible.
        Returns True on success, None on failure.
        """
        if self.current_tab().on_half_scroll_up():
            self.refresh_window()
            return True

    def scroll_half_down(self, args=None):
        """
        Scroll half a screen down, if possible.
        Returns True on success, None on failure.
        """
        if self.current_tab().on_half_scroll_down():
            self.refresh_window()
            return True

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

    def scroll_info_up(self):
        self.information_win.scroll_up(self.information_win.height)
        if not isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.information_win.refresh()
        else:
            info = self.current_tab().information_win
            info.scroll_up(info.height)
            self.refresh_window()

    def scroll_info_down(self):
        self.information_win.scroll_down(self.information_win.height)
        if not isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.information_win.refresh()
        else:
            info = self.current_tab().information_win
            info.scroll_down(info.height)
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

    def toggle_left_pane(self):
        """
        Enable/disable the left panel.
        """
        enabled = config.get('enable_vertical_tab_list', 'false')
        config.set_and_save('enable_vertical_tab_list', 'false' if enabled == 'true' else 'true')
        self.call_for_resize()

    def resize_global_information_win(self):
        """
        Resize the global_information_win only once at each resize.
        """
        with g_lock:
            self.information_win.resize(self.information_win_size, tabs.Tab.width,
                                        tabs.Tab.height - 1 - self.information_win_size - tabs.Tab.tab_win_height(), 0)

    def resize_global_info_bar(self):
        """
        Resize the GlobalInfoBar only once at each resize
        """
        with g_lock:
            self.tab_win.resize(1, tabs.Tab.width, tabs.Tab.height - 2, 0)
            if config.get('enable_vertical_tab_list', 'false') == 'true':
                height, width = self.stdscr.getmaxyx()
                truncated_win = self.stdscr.subwin(height, config.get('vertical_tab_list_size', 20), 0, 0)
                self.left_tab_win = windows.VerticalGlobalInfoBar(truncated_win)
            else:
                self.left_tab_win = None

    def add_message_to_text_buffer(self, buff, txt, time=None, nickname=None, history=None):
        """
        Add the message to the room if possible, else, add it to the Info window
        (in the Info tab of the info window in the RosterTab)
        """
        if not buff:
            self.information('Trying to add a message in no room: %s' % txt, 'Error')
        else:
            buff.add_message(txt, time, nickname, history=history)

    def full_screen_redraw(self):
        """
        Completely erase and redraw the screen
        """
        self.stdscr.clear()
        self.refresh_window()

    def call_for_resize(self):
        """
        Called when we want to resize the screen
        """
        # If we have the tabs list on the left, we just give a truncated
        # window to each Tab class, so the draw themself in the portion
        # of the screen that the can occupy, and we draw the tab list
        # on the left remaining space
        if config.get('enable_vertical_tab_list', 'false') == 'true':
            scr = self.stdscr.subwin(0, config.get('vertical_tab_list_size', 20))
        else:
            scr = self.stdscr
        tabs.Tab.resize(scr)
        self.resize_global_info_bar()
        self.resize_global_information_win()
        with g_lock:
            for tab in self.tabs:
                if config.get('lazy_resize', 'true') == 'true':
                    tab.need_resize = True
                else:
                    tab.resize()
            if self.tabs:
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

####################### Commands and completions ##############################

    def command_help(self, arg):
        """
        /help <command_name>
        """
        args = arg.split()
        if not args:
            msg = _('Available commands are: ')
            for command in self.commands:
                msg += "%s " % command
            for command in self.current_tab().commands:
                msg += "%s " % command
            msg += _("\nType /help <command_name> to know what each command does")
        if args:
            if args[0] in self.commands:
                msg = self.commands[args[0]][1]
            elif args[0] in self.current_tab().commands:
                msg = self.current_tab().commands[args[0]][1]
            else:
                msg = _('Unknown command: %s') % args[0]
        self.information(msg, 'Help')

    def completion_help(self, the_input):
        """Completion for /help."""
        commands = list(self.commands.keys()) + list(self.current_tab().commands.keys())
        return the_input.auto_completion(commands, ' ', quotify=False)

    def command_runkey(self, arg):
        """
        /runkey <key>
        """
        def replace_line_breaks(key):
            if key == '^J':
                return '\n'
            return key
        char = arg.strip()
        func = self.key_func.get(char, None)
        if func:
            func()
        else:
            res = self.do_command(replace_line_breaks(char), False)
            if res:
                self.refresh_window()

    def completion_runkey(self, the_input):
        """
        Completion for /runkey
        """
        list_ = []
        list_.extend(self.key_func.keys())
        list_.extend(self.current_tab().key_func.keys())
        return the_input.auto_completion(list_, '', quotify=False)

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
        else:
            msg = None
        pres = self.xmpp.make_presence()
        if msg:
            pres['status'] = msg
        pres['type'] = show
        self.events.trigger('send_normal_presence', pres)
        pres.send()
        current = self.current_tab()
        if isinstance(current, tabs.MucTab) and current.joined and show in ('away', 'xa'):
            current.send_chat_state('inactive')
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab) and tab.joined:
                muc.change_show(self.xmpp, tab.name, tab.own_nick, show, msg)
            if hasattr(tab, 'directed_presence'):
                del tab.directed_presence
        self.set_status(show, msg)
        if isinstance(current, tabs.MucTab) and current.joined and show not in ('away', 'xa'):
            current.send_chat_state('active')

    def completion_status(self, the_input):
        """
        Completion of /status
        """
        return the_input.auto_completion([status for status in possible_show], ' ')

    def command_presence(self, arg):
        """
        /presence <JID> [type] [status]
        """
        args = common.shell_split(arg)
        if len(args) == 1:
            jid, type, status = args[0], None, None
        elif len(args) == 2:
            jid, type, status = args[0], args[1], None
        elif len(args) == 3:
            jid, type, status = args[0], args[1], args[2]
        else:
            return
        if jid == '.' and isinstance(self.current_tab(), tabs.ChatTab):
            jid = self.current_tab().get_name()
        if type == 'available':
            type = None
        try:
            pres = self.xmpp.make_presence(pto=jid, ptype=type, pstatus=status)
            self.events.trigger('send_normal_presence', pres)
            pres.send()
        except :
            import traceback
            self.information(_('Could not send directed presence'), 'Error')
            log.debug(_("Could not send directed presence:\n") + traceback.format_exc())
        tab = self.get_tab_by_name(jid)
        if tab:
            if type in ('xa', 'away'):
                tab.directed_presence = False
                chatstate = 'inactive'
            else:
                tab.directed_presence = True
                chatstate = 'active'
            if tab == self.current_tab():
                tab.send_chat_state(chatstate, True)
            if isinstance(tab, tabs.MucTab):
                for private in tab.privates:
                    private.directed_presence = tab.directed_presence
                if self.current_tab() in tab.privates:
                    self.current_tab().send_chat_state(chatstate, True)

    def completion_presence(self, the_input):
        """
        Completion of /presence
        """
        text = the_input.get_text()
        args = text.split()
        n = len(args)
        if text.endswith(' '):
            n += 1
        if n == 2:
            return the_input.auto_completion([jid for jid in roster.jids()], '')
        elif n == 3:
            return the_input.auto_completion([status for status in possible_show], '')

    def command_theme(self, arg=''):
        """/theme <theme name>"""
        args = arg.split()
        if args:
            self.command_set('theme %s' % (args[0],))
        warning = theming.reload_theme()
        if warning:
            self.information(warning, 'Warning')
        self.refresh_window()

    def completion_theme(self, the_input):
        """ Completion for /theme"""
        themes_dir = config.get('themes_dir', '')
        themes_dir = themes_dir or\
        os.path.join(os.environ.get('XDG_DATA_HOME') or\
                         os.path.join(os.environ.get('HOME'), '.local', 'share'),
                     'poezio', 'themes')
        themes_dir = os.path.expanduser(themes_dir)
        try:
            names = os.listdir(themes_dir)
        except OSError as e:
            log.debug(_('Completion failed: %s'), e)
            return
        theme_files = [name[:-3] for name in names if name.endswith('.py')]
        if not 'default' in theme_files:
            theme_files.append('default')
        return the_input.auto_completion(theme_files, '', quotify=False)

    def command_win(self, arg):
        """
        /win <number>
        """
        arg = arg.strip()
        if not arg:
            self.command_help('win')
            return
        try:
            nb = int(arg.split()[0])
        except ValueError:
            nb = arg
        if self.current_tab_nb == nb:
            return
        self.previous_tab_nb = self.current_tab_nb
        self.current_tab().on_lose_focus()
        if isinstance(nb, int):
            if 0 <= nb < len(self.tabs):
                self.current_tab_nb = nb
        else:
            for tab in self.tabs:
                if nb in safeJID(tab.get_name()).user:
                    self.current_tab_nb = tab.nb
        self.current_tab().on_gain_focus()
        self.refresh_window()

    def completion_win(self, the_input):
        """Completion for /win"""
        l =  [safeJID(tab.get_name()).user for tab in self.tabs]
        l.remove('')
        return the_input.auto_completion(l, ' ', quotify=False)

    def command_move_tab(self, arg):
        """
        /move_tab old_pos new_pos
        """
        args = common.shell_split(arg)
        current_tab = self.current_tab()
        if len(args) != 2:
            return self.command_help('move_tab')
        def get_nb_from_value(value):
            ref = None
            try:
                ref = int(value)
            except ValueError:
                old_tab = None
                for tab in self.tabs:
                    if not old_tab and value in safeJID(tab.get_name()).user:
                        old_tab = tab
                if not old_tab:
                    self.information("Tab %s does not exist" % args[0], "Error")
                    return None
                ref = old_tab.nb
            return ref
        old = get_nb_from_value(args[0])
        new = get_nb_from_value(args[1])
        if new is None or old is None:
            return self.information('Unable to move the tab.', 'Info')
        result = self.insert_tab(old, new)
        if not result:
            self.information('Unable to move the tab.', 'Info')
        else:
            self.current_tab_nb = self.tabs.index(current_tab)
        self.refresh_window()

    def completion_move_tab(self, the_input):
        """Completion for /move_tab"""
        nodes = [safeJID(tab.get_name()).user for tab in self.tabs]
        return the_input.auto_completion(nodes, ' ', quotify=True)

    def command_list(self, arg):
        """
        /list <server>
        Opens a MucListTab containing the list of the room in the specified server
        """
        arg = arg.split()
        if len(arg) > 1:
            return self.command_help('list')
        elif arg:
            server = safeJID(arg[0]).server
        else:
            if not isinstance(self.current_tab(), tabs.MucTab):
                return self.information('Please provide a server', 'Error')
            server = safeJID(self.current_tab().get_name()).server
        list_tab = tabs.MucListTab(server)
        self.add_tab(list_tab, True)
        self.xmpp.plugin['xep_0030'].get_items(jid=server, block=False, callback=list_tab.on_muc_list_item_received)

    def completion_list(self, the_input):
        """Completion for /list"""
        muc_serv_list = []
        for tab in self.tabs:   # TODO, also from an history
            if isinstance(tab, tabs.MucTab) and\
                    tab.get_name() not in muc_serv_list:
                muc_serv_list.append(safeJID(tab.get_name()).server)
        if muc_serv_list:
            return the_input.auto_completion(muc_serv_list, ' ', quotify=False)

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
        jid = safeJID(args[0])
        if jid.resource or jid not in roster:
            self.xmpp.plugin['xep_0092'].get_version(jid, callback=callback)
        elif jid in roster:
            for resource in roster[jid].resources:
                self.xmpp.plugin['xep_0092'].get_version(resource.jid, callback=callback)
            else:
                self.xmpp.plugin['xep_0092'].get_version(jid, callback=callback)

    def completion_version(self, the_input):
        """Completion for /version"""
        n = len(the_input.get_text().split())
        if n > 2 or (n == 2 and the_input.get_text().endswith(' ')):
            return
        comp = reduce(lambda x, y: x+y, (jid.resources for jid in roster if len(jid)), [])
        comp = (str(res.jid) for res in comp)
        return the_input.auto_completion(sorted(comp), '', quotify=False)

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
            room = safeJID(tab.get_name()).bare
            nick = tab.own_nick
        else:
            info = safeJID(args[0])
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
                    room += '@%s' % safeJID(self.current_tab().get_name()).domain
                else:           # no server could be found, print a message and return
                    self.information(_("You didn't specify a server for the room you want to join"), 'Error')
                    return
        room = room.lower()
        if room in self.pending_invites:
            del self.pending_invites[room]
        tab = self.get_tab_by_name(room, tabs.MucTab)
        if len(args) == 2:       # a password is provided
            password = args[1]
        if tab and tab.joined:       # if we are already in the room
            self.focus_tab_named(tab.name)
            if tab.own_nick == nick:
                self.information('/join: Nothing to do.', 'Info')
            else:
                tab.own_nick = nick
                tab.command_cycle('')
            return

        if room.startswith('@'):
            room = room[1:]
        current_status = self.get_status()
        if not histo_length:
            histo_length= config.get('muc_history_length', 20)
            if histo_length == -1:
                histo_length= None
        if histo_length is not None:
            histo_length= str(histo_length)
        if tab and not tab.joined:
            seconds = (int(time.time()) - tab.last_connection) if tab.last_connection != 0 else 0
            muc.join_groupchat(self.xmpp, room, nick, password,
                               histo_length, current_status.message, current_status.show, seconds=seconds)
        if not tab:
            self.open_new_room(room, nick)
            muc.join_groupchat(self.xmpp, room, nick, password,
                               histo_length, current_status.message, current_status.show)
        else:
            tab.own_nick = nick
            tab.users = []
        if tab and tab.joined:
            self.enable_private_tabs(room)
            tab.state = "normal"
            if tab == self.current_tab():
                tab.refresh()
                self.doupdate()

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
        jid = safeJID(txt.split()[1])
        if jid.server:
            if jid.resource or jid.full.endswith('/'):
                # we are writing the resource: complete the node
                if not the_input.last_completion:
                    try:
                        response = self.xmpp.plugin['xep_0030'].get_items(jid=jid.server, block=True, timeout=1)
                    except:
                        response = None
                    if response:
                        items = response['disco_items'].get_items()
                    else:
                        return True
                    items = ['%s/%s' % (tup[0], jid.resource) for tup in items]
                    for _ in range(len(jid.server) + 2 + len(jid.resource)):
                        the_input.key_backspace()
                else:
                    items = []
                items.extend(list(self.pending_invites.keys()))
                the_input.auto_completion(items, '')
            else:
                # we are writing the server: complete the server
                serv_list = []
                for tab in self.tabs:
                    if isinstance(tab, tabs.MucTab):
                        serv_list.append('%s@%s'% (jid.user, safeJID(tab.get_name()).host))
                serv_list.extend(list(self.pending_invites.keys()))
                the_input.auto_completion(serv_list, '')
        return True

    def command_bookmark_local(self, arg=''):
        """
        /bookmark_local [room][/nick]
        """
        args = common.shell_split(arg)
        nick = None
        if len(args) == 0 and not isinstance(self.current_tab(), tabs.MucTab):
            return
        if len(args) == 0:
            tab = self.current_tab()
            roomname = tab.get_name()
            if tab.joined:
                nick = tab.own_nick
        elif args[0] == '*':
            for tab in self.tabs:
                if isinstance(tab, tabs.MucTab):
                    b = bookmark.get_by_jid(tab.get_name())
                    if not b:
                        b = bookmark.Bookmark(tab.get_name(), autojoin=True, method="local")
                        bookmark.bookmarks.append(b)
                    else:
                        b.method = "local"
            bookmark.save_local()
            bookmark.save_remote(self.xmpp)
            self.information('Bookmarks added and saved.', 'Info')
            return
        else:
            info = safeJID(args[0])
            if info.resource != '':
                nick = info.resource
            roomname = info.bare
            if not roomname:
                if not isinstance(self.current_tab(), tabs.MucTab):
                    return
                roomname = self.current_tab().get_name()

        bm = bookmark.get_by_jid(roomname)
        if not bm:
            bm = bookmark.Bookmark(jid=roomname)
            bookmark.bookmarks.append(bm)
            self.information('Bookmark added.', 'Info')
        else:
            self.information('Bookmark updated.', 'Info')
        if nick:
            bm.nick = nick
        bm.autojoin = True
        bm.method = "local"
        bookmark.save_local()
        self.information(_('Your local bookmarks are now: %s') %
                [b for b in bookmark.bookmarks if b.method == 'local'], 'Info')

    def completion_bookmark_local(self, the_input):
        """Completion for /bookmark_local"""
        txt = the_input.get_text()
        args = common.shell_split(txt)
        n = len(args)
        if txt.endswith(' '):
            n += 1

        if len(args) == 1:
            jid = safeJID('')
        else:
            jid = safeJID(args[1])
        if len(args) > 2:
            return
        if jid.server and (jid.resource or jid.full.endswith('/')):
            tab = self.get_tab_by_name(jid.bare, tabs.MucTab)
            nicks = [tab.own_nick] if tab else []
            default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
            nick = config.get('default_nick', '')
            if not nick:
                if not default in nicks:
                    nicks.append(default)
            else:
                if not nick in nicks:
                    nicks.append(nick)
            jids_list = ['%s/%s' % (jid.bare, nick) for nick in nicks]
            return the_input.auto_completion(jids_list, '')
        muc_list = [tab.get_name() for tab in self.tabs if isinstance(tab, tabs.MucTab)]
        muc_list.append('*')
        return the_input.auto_completion(muc_list, '')

    def command_bookmark(self, arg=''):
        """
        /bookmark [room][/nick] [autojoin] [password]
        """

        if config.get('use_remote_bookmarks', 'true').lower() == 'false':
            self.command_bookmark_local(arg)
            return
        args = common.shell_split(arg)
        nick = None
        if len(args) == 0 and not isinstance(self.current_tab(), tabs.MucTab):
            return
        if len(args) == 0:
            tab = self.current_tab()
            roomname = tab.get_name()
            if tab.joined:
                nick = tab.own_nick
            autojoin = True
            password = None
        elif args[0] == '*':
            if len(args) > 1:
                autojoin = False if args[1].lower() == 'false' else True
            else:
                autojoin = True
            for tab in self.tabs:
                if isinstance(tab, tabs.MucTab):
                    b = bookmark.get_by_jid(tab.get_name())
                    if not b:
                        b = bookmark.Bookmark(tab.get_name(), autojoin=autojoin,
                                method=bookmark.preferred)
                        bookmark.bookmarks.append(b)
                    else:
                        b.method = bookmark.preferred
            if bookmark.save_remote(self.xmpp, self):
                bookmark.save_local()
                self.information("Bookmarks added.", "Info")
            else:
                self.information("Could not add the bookmarks.", "Info")
            return
        else:
            info = safeJID(args[0])
            if info.resource != '':
                nick = info.resource
            roomname = info.bare
            if roomname == '':
                if not isinstance(self.current_tab(), tabs.MucTab):
                    return
                roomname = self.current_tab().get_name()
            if len(args) > 1:
                autojoin = False if args[1].lower() == 'false' else True
            else:
                autojoin = True
            if len(args) > 2:
                password = args[2]
            else:
                password = None
        bm = bookmark.get_by_jid(roomname)
        if not bm:
            bm = bookmark.Bookmark(roomname)
            bookmark.bookmarks.append(bm)
        bm.method = config.get('use_bookmarks_method', 'pep')
        if nick:
            bm.nick = nick
        if password:
            bm.password = password
        if autojoin:
            bm.autojoin = autojoin
        if bookmark.save_remote(self.xmpp):
            self.information('Bookmark added.', 'Info')
        self.information(_('Your remote bookmarks are now: %s') %
                [b for b in bookmark.bookmarks if b.method in ('pep', 'privatexml')], 'Info')

    def completion_bookmark(self, the_input):
        """Completion for /bookmark"""
        txt = the_input.get_text()
        args = common.shell_split(txt)
        n = len(args)
        if txt.endswith(' '):
            n += 1

        if len(args) == 1:
            jid = safeJID('')
        else:
            jid = safeJID(args[1])

        if len(args) == 2:
            return the_input.auto_completion(['true', 'false'], '')
        if len(args) == 3:
            return

        if jid.server and (jid.resource or jid.full.endswith('/')):
            tab = self.get_tab_by_name(jid.bare, tabs.MucTab)
            nicks = [tab.own_nick] if tab else []
            default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
            nick = config.get('default_nick', '')
            if not nick:
                if not default in nicks:
                    nicks.append(default)
            else:
                if not nick in nicks:
                    nicks.append(nick)
            jids_list = ['%s/%s' % (jid.bare, nick) for nick in nicks]
            return the_input.auto_completion(jids_list, '')
        muc_list = [tab.get_name() for tab in self.tabs if isinstance(tab, tabs.MucTab)]
        muc_list.append('*')
        return the_input.auto_completion(muc_list, '')

    def command_bookmarks(self, arg=''):
        """/bookmarks"""
        self.information(_('Your remote bookmarks are: %s') %
                [b for b in bookmark.bookmarks if b.method in ('pep', 'privatexml')], 'Info')
        self.information(_('Your local bookmarks are: %s') %
                [b for b in bookmark.bookmarks if b.method is 'local'], 'Info')

    def command_remove_bookmark(self, arg=''):
        """/remove_bookmark [jid]"""
        args = common.shell_split(arg)
        if not args:
            tab = self.current_tab()
            if isinstance(tab, tabs.MucTab) and bookmark.get_by_jid(tab.get_name()):
                bookmark.remove(tab.get_name())
                bookmark.save(self.xmpp)
                if bookmark.save(self.xmpp):
                    self.information('Bookmark deleted', 'Info')
            else:
                self.information('No bookmark to remove', 'Info')
        else:
            if bookmark.get_by_jid(args[0]):
                bookmark.remove(args[0])
                if bookmark.save(self.xmpp):
                    self.information('Bookmark deleted', 'Info')

            else:
                self.information('No bookmark to remove', 'Info')

    def completion_remove_bookmark(self, the_input):
        """Completion for /remove_bookmark"""
        return the_input.auto_completion([bm.jid for bm in bookmark.bookmarks], '')

    def command_set(self, arg):
        """
        /set [module|][section] <option> <value>
        """
        args = common.shell_split(arg)
        if len(args) != 2 and len(args) != 3:
            self.command_help('set')
            return
        if len(args) == 2:
            option = args[0]
            value = args[1]
            config.set_and_save(option, value)
        elif len(args) == 3:
            if '|' in args[0]:
                plugin_name, section = args[0].split('|')[:2]
                if not section:
                    section = plugin_name
                option = args[1]
                value = args[2]
                if not plugin_name in self.plugin_manager.plugins:
                    return
                plugin = self.plugin_manager.plugins[plugin_name]
                plugin.config.set_and_save(option, value, section)
            else:
                section = args[0]
                option = args[1]
                value = args[2]
                config.set_and_save(option, value, section)
        msg = "%s=%s" % (option, value)
        # Remove all gaptabs if switching from gaps to nogaps
        if option == 'create_gaps' and value.lower() == 'false':
            self.tabs = list(filter(lambda x: bool(x), self.tabs))
        self.information(msg, 'Info')

    def completion_set(self, the_input):
        """Completion for /set"""
        text = the_input.get_text()
        args = common.shell_split(text)
        n = len(args)
        empty = False
        if text.endswith(' '):
            n += 1
            empty = True
        if n == 2:
            if not empty and '|' in args[1]:
                plugin_name, section = args[1].split('|')[:2]
                if not plugin_name in self.plugin_manager.plugins:
                        return the_input.auto_completion([],'')
                plugin = self.plugin_manager.plugins[plugin_name]
                end_list = ['%s|%s' % (plugin_name, section) for section in plugin.config.sections()]
            else:
                end_list = config.options('Poezio')
        elif n == 3:
            if '|' in args[1]:
                plugin_name, section = args[1].split('|')[:2]
                if not plugin_name in self.plugin_manager.plugins:
                        return the_input.auto_completion([''],'')
                plugin = self.plugin_manager.plugins[plugin_name]
                end_list = plugin.config.options(section or plugin_name)
            elif not config.has_option('Poezio', args[1]):
                if config.has_section(args[1]):
                    end_list = config.options(args[1])
                    end_list.append('')
                else:
                    end_list = []
            else:
                end_list = [config.get(args[1], ''), '']
        elif n == 4:
            if '|' in args[1]:
                plugin_name, section = args[1].split('|')[:2]
                if not plugin_name in self.plugin_manager.plugins:
                        return the_input.auto_completion([],'')
                plugin = self.plugin_manager.plugins[plugin_name]
                end_list = [plugin.config.get(args[2], '', section or plugin_name), '']
            else:
                if not config.has_section(args[1]):
                    end_list = ['']
                else:
                    end_list = [config.get(args[2], '', args[1]), '']
        return the_input.auto_completion(end_list, '')

    def command_server_cycle(self, arg=''):
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
                domain = safeJID(tab.get_name()).domain
            else:
                self.information(_("No server specified"), "Error")
                return
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab) and safeJID(tab.get_name()).domain == domain:
                if tab.joined:
                    muc.leave_groupchat(tab.core.xmpp, tab.get_name(), tab.own_nick, message)
                tab.joined = False
                self.command_join('"%s/%s"' %(tab.get_name(), tab.own_nick))

    def completion_server_cycle(self, the_input):
        """Completion for /server_cycle"""
        txt = the_input.get_text()
        args = txt.split()
        n = len(args)
        if txt.endswith(' '):
            n += 1
        if n == 2:
            serv_list = []
            for tab in self.tabs:
                if isinstance(tab, tabs.MucTab):
                    serv = safeJID(tab.get_name()).server
                    if not serv in serv_list:
                        serv_list.append(serv)
            return the_input.auto_completion(serv_list, ' ')

    def command_activity(self, arg):
        """
        /activity <jid>
        """
        def callback(iq):
            if iq['type'] != 'result':
                if iq['error']['type'] == 'auth':
                    self.information('You are not allowed to see the activity of this contact.', 'Error')
                else:
                    self.information('Error retrieving the activity', 'Error')
                return
            seconds = iq['last_activity']['seconds']
            status = iq['last_activity']['status']
            from_ = iq['from']
            if not safeJID(from_).user:
                msg = 'The uptime of %s is %s.' % (
                        from_,
                        common.parse_secs_to_str(seconds))
            else:
                msg = 'The last activity of %s was %s ago%s' % (
                    from_,
                    common.parse_secs_to_str(seconds),
                    (' and his/her last status was %s' % status) if status else '',)
            self.information(msg, 'Info')
        jid = safeJID(arg)
        self.xmpp.plugin['xep_0012'].get_last_activity(jid, block=False, callback=callback)

    def completion_activity(self, the_input):
            return the_input.auto_completion([jid for jid in roster.jids()], '', quotify=False)

    def command_invite(self, arg):
        """/invite <to> <room> [reason]"""
        args = common.shell_split(arg)
        if len(args) < 2:
            return
        reason = args[2] if len(args) > 2 else ''
        to = safeJID(args[0])
        room = safeJID(args[1])
        self.xmpp.plugin['xep_0045'].invite(room, to, reason)

    def completion_invite(self, the_input):
        """Completion for /invite"""
        txt = the_input.get_text()
        args = common.shell_split(txt)
        n = len(args)
        if txt.endswith(' '):
            n += 1
        if n == 2:
            return the_input.auto_completion([jid for jid in roster.jids()], '')
        elif n == 3:
            rooms = []
            for tab in self.tabs:
                if isinstance(tab, tabs.MucTab) and tab.joined:
                    rooms.append(tab.get_name())
            return the_input.auto_completion(rooms, '')

    def command_decline(self, arg):
        """/decline <room@server.tld> [reason]"""
        args = common.shell_split(arg)
        if not len(args):
            return
        jid = safeJID(args[0])
        if jid.bare not in self.pending_invites:
            return
        reason = args[1] if len(args) > 1 else ''
        del self.pending_invites[jid.bare]
        self.xmpp.plugin['xep_0045'].decline_invite(jid.bare, self.pending_invites[jid.bare], reason)

    def completion_decline(self, the_input):
        """Completion for /decline"""
        txt = the_input.get_text()
        args = common.shell_split(txt)
        n = len(args)
        if txt.endswith(' '):
            n += 1
        if n == 2:
            return the_input.auto_completion(list(self.pending_invites.keys()), '')

    ### Commands without a completion in this class ###

    def command_invitations(self, arg=''):
        """/invitations"""
        build = ""
        for invite in self.pending_invites:
            build += "%s by %s" % (invite, safeJID(self.pending_invites[invite]).bare)
        if self.pending_invites:
            build = "You are invited to the following rooms:\n" + build
        else:
            build = "You are do not have any pending invitation."
        self.information(build, 'Info')

    def command_quit(self, arg=''):
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

    def command_bind(self, arg):
        """
        Bind a key.
        """
        args = common.shell_split(arg)
        if len(args) < 1:
            return self.command_help('bind')
        elif len(args) < 2:
            args.append("")
        config.set_and_save(args[0], args[1], section='bindings')
        if args[1]:
            self.information('%s is now bound to %s' % (args[0], args[1]), 'Info')
        else:
            self.information('%s is now unbound' % args[0], 'Info')

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

    def command_rawxml(self, arg):
        """
        /rawxml <xml stanza>
        """
        if not arg:
            return

        try:
            StanzaBase(self.xmpp, xml=ET.fromstring(arg)).send()
        except:
            import traceback
            self.information(_('Could not send custom stanza'), 'Error')
            log.debug(_("Could not send custom stanza:\n") + traceback.format_exc())

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

    def command_plugins(self, arg=''):
        """
        /plugins
        """
        self.information("Plugins currently in use: %s" % repr(list(self.plugin_manager.plugins.keys())), 'Info')

    def command_message(self, arg):
        """
        /message <jid> [message]
        """
        args = common.shell_split(arg)
        if len(args) < 1:
            self.command_help('message')
            return
        jid = safeJID(args[0])
        if not jid.user and not jid.domain and not jid.resource:
            return self.information('Invalid JID.', 'Error')
        tab = self.open_conversation_window(jid.full, focus=True)
        if len(args) > 1:
            tab.command_say(args[1])

    def command_reconnect(self, args=None):
        """
        /reconnect
        """
        self.disconnect(reconnect=True)

    def command_xml_tab(self, arg=''):
        """/xml_tab"""
        self.xml_tabs += 1
        tab = tabs.XMLTab()
        self.add_tab(tab, True)

    def command_self(self, arg=None):
        """
        /self
        """
        status = self.get_status()
        show, message = status.show, status.message
        nick = self.own_nick
        jid = self.xmpp.boundjid.full
        info = 'Your JID is %s\nYour current status is "%s" (%s)\nYour default nickname is %s' % (
                jid,
                message,
                show if show else 'available',
                nick)
        self.information(info, 'Info')


####################### XMPP Event Handlers  ##################################

    ### Invites ###

    def on_groupchat_invite(self, message):
        jid = message['from']
        if jid.bare in self.pending_invites:
            return
        # there are 2 'x' tags in the messages, making message['x'] useless
        invite = StanzaBase(self.xmpp, xml=message.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}invite'))
        inviter = invite['from']
        reason = invite['reason']
        password = invite['password']
        msg = "You are invited to the room %s by %s" % (jid.full, inviter.full)
        if reason:
            msg += "because: %s" % reason
        if password:
            msg += ". The password is \"%s\"." % password
        self.information(msg, 'Info')
        if 'invite' in config.get('beep_on', 'invite').split():
            curses.beep()
        self.pending_invites[jid.bare] = inviter.full

    def on_groupchat_decline(self, decline):
        pass

    ### "classic" messages ###

    def on_message(self, message):
        """
        When receiving private message from a muc OR a normal message
        (from one of our contacts)
        """
        if message.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}invite') != None:
            return
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

    def on_normal_message(self, message):
        """
        When receiving "normal" messages (from someone in our roster)
        """
        jid = message['from']
        body = xhtml.get_body_from_message_stanza(message)
        if message['type'] == 'error':
            return self.information(self.get_error_message(message, deprecated=True), 'Error')
        if not body:
            return
        conversation = self.get_conversation_by_jid(jid, create=True)
        self.events.trigger('conversation_msg', message, conversation)
        body = xhtml.get_body_from_message_stanza(message)
        if jid.bare in roster:
            remote_nick = roster[jid.bare].name or jid.user
        else:
            remote_nick = jid.user
        delay_tag = message.find('{urn:xmpp:delay}delay')
        if delay_tag is not None:
            delayed = True
            date = common.datetime_tuple(delay_tag.attrib['stamp'])
        else:
            delayed = False
            date = None
        conversation._text_buffer.add_message(body, date, nickname=remote_nick, nick_color=get_theme().COLOR_REMOTE_USER, history=delayed)
        if conversation.remote_wants_chatstates is None and not delayed:
            if message['chat_state']:
                conversation.remote_wants_chatstates = True
            else:
                conversation.remote_wants_chatstates = False
        logger.log_message(jid.bare, remote_nick, body)
        if 'private' in config.get('beep_on', 'highlight private').split():
            if config.get_by_tabname('disable_beep', 'false', jid.bare, False).lower() != 'true':
                curses.beep()
        if self.current_tab() is not conversation:
            conversation.state = 'private'
            self.refresh_tab_win()
        else:
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
        old_state = tab.state
        if not tab:
            self.information(_("message received for a non-existing room: %s") % (room_from))
            return
        if tab.get_user_by_name(nick_from) and\
                tab.get_user_by_name(nick_from) in tab.ignores:
            return
        self.events.trigger('muc_msg', message, tab)
        body = xhtml.get_body_from_message_stanza(message)
        if body:
            date = date if delayed == True else None
            if tab.add_message(body, date, nick_from, history=True if date else False):
                self.events.trigger('highlight', message, tab)
            if tab is self.current_tab():
                tab.text_win.refresh()
                tab.info_header.refresh(tab, tab.text_win)
                tab.input.refresh()
                self.doupdate()
            elif tab.state != old_state:
                self.refresh_tab_win()
                self.current_tab().input.refresh()
                self.doupdate()
            if 'message' in config.get('beep_on', 'highlight private').split():
                if config.get_by_tabname('disable_beep', 'false', room_from, False).lower() != 'true':
                    curses.beep()

    def on_groupchat_private_message(self, message):
        """
        We received a Private Message (from someone in a Muc)
        """
        jid = message['from']
        nick_from = jid.resource
        room_from = jid.bare
        body = xhtml.get_body_from_message_stanza(message)
        tab = self.get_tab_by_name(jid.full, tabs.PrivateTab) # get the tab with the private conversation
        ignore = config.get_by_tabname('ignore_private', 'false',
                room_from).lower() == 'true'
        if not tab: # It's the first message we receive: create the tab
            if body and not ignore:
                tab = self.open_private_window(room_from, nick_from, False)
        if ignore:
            self.events.trigger('ignored_private', message, tab)
            msg = config.get_by_tabname('private_auto_response', None, room_from)
            if msg and body:
                self.xmpp.send_message(mto=jid.full, mbody=msg, mtype='chat')
            return
        self.events.trigger('private_msg', message, tab)
        if not body or not tab:
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
            if config.get_by_tabname('disable_beep', 'false', jid.full, False).lower() != 'true':
                curses.beep()
        logger.log_message(jid.full.replace('/', '\\'), nick_from, body)
        if conversation is self.current_tab():
            self.refresh_window()
        else:
            conversation.state = 'private'
            self.refresh_tab_win()

    ### Chatstates ###

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
        tab = self.get_conversation_by_jid(message['from'], False)
        if not tab:
            return False
        self.events.trigger('normal_chatstate', message, tab)
        tab.chatstate = state
        if tab == self.current_tab():
            tab.refresh_info_header()
            self.doupdate()
        return True

    def on_chatstate_private_conversation(self, message, state):
        """
        Chatstate received in a private conversation from a MUC
        """
        tab = self.get_tab_by_name(message['from'].full, tabs.PrivateTab)
        if not tab:
            return
        self.events.trigger('private_chatstate', message, tab)
        tab.chatstate = state
        if tab == self.current_tab():
            tab.refresh_info_header()
            self.doupdate()
        return True

    def on_chatstate_groupchat_conversation(self, message, state):
        """
        Chatstate received in a MUC
        """
        nick = message['mucnick']
        room_from = message.getMucroom()
        tab = self.get_tab_by_name(room_from, tabs.MucTab)
        if tab and tab.get_user_by_name(nick):
            self.events.trigger('muc_chatstate', message, tab)
            tab.get_user_by_name(nick).chatstate = state
        if tab == self.current_tab():
            tab.user_win.refresh(tab.users)
            tab.input.refresh()
            self.doupdate()

    ### subscription-related handlers ###

    def on_roster_update(self, iq):
        """
        The roster was received.
        """
        for item in iq['roster']:
            jid = item['jid']
            if item['subscription'] == 'remove':
                del roster[jid]
            else:
                roster.update_contact_groups(jid)
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def on_subscription_request(self, presence):
        """subscribe received"""
        jid = presence['from'].bare
        contact = roster[jid]
        if contact.subscription in ('from', 'both'):
            return
        elif contact.subscription == 'to':
            self.xmpp.sendPresence(pto=jid, ptype='subscribed')
            self.xmpp.sendPresence(pto=jid)
        else:
            roster.update_contact_groups(contact)
            contact.pending_in = True
            self.information('%s wants to subscribe to your presence' % jid, 'Roster')
            self.get_tab_by_number(0).state = 'highlight'
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def on_subscription_authorized(self, presence):
        """subscribed received"""
        jid = presence['from'].bare
        contact = roster[jid]
        if contact.subscription not in ('both', 'from'):
            self.information('%s accepted your contact proposal' % jid, 'Roster')
        if contact.pending_out:
            contact.pending_out = False
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def on_subscription_remove(self, presence):
        """unsubscribe received"""
        jid = presence['from'].bare
        contact = roster[jid]
        if not contact:
            return
        self.information('%s does not want to receive your status anymore.' % jid, 'Roster')
        self.get_tab_by_number(0).state = 'highlight'
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def on_subscription_removed(self, presence):
        """unsubscribed received"""
        jid = presence['from'].bare
        contact = roster[jid]
        if not contact:
            return
        if contact.pending_out:
            self.information('%s rejected your contact proposal' % jid, 'Roster')
            contact.pending_out = False
        else:
            self.information('%s does not want you to receive his/her/its status anymore.'%jid, 'Roster')
        self.get_tab_by_number(0).state = 'highlight'
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    ### Presence-related handlers ###

    def on_presence(self, presence):
        if presence.match('presence/muc') or presence.xml.find('{http://jabber.org/protocol/muc#user}x'): 
            return
        jid = presence['from']
        contact = roster[jid.bare]
        if contact is None:
            return
        self.events.trigger('normal_presence', presence, contact[jid.full])
        tab = self.get_conversation_by_jid(jid, create=False)
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()
        elif self.current_tab() == tab:
            tab.refresh()
            self.doupdate()

    def on_got_offline(self, presence):
        """
        A JID got offline
        """
        if presence.match('presence/muc') or presence.xml.find('{http://jabber.org/protocol/muc#user}x'):
            return
        jid = presence['from']
        logger.log_roster_change(jid.bare, 'got offline')
        # If a resource got offline, display the message in the conversation with this
        # precise resource.
        if jid.resource:
            self.add_information_message_to_conversation_tab(jid.full, '\x195}%s is \x191}offline' % (jid.full))
        self.add_information_message_to_conversation_tab(jid.bare, '\x195}%s is \x191}offline' % (jid.bare))
        self.information('\x193}%s \x195}is \x191}offline' % (jid.bare), 'Roster')
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def on_got_online(self, presence):
        """
        A JID got online
        """
        if presence.match('presence/muc') or presence.xml.find('{http://jabber.org/protocol/muc#user}x'):
            return
        jid = presence['from']
        contact = roster[jid.bare]
        if contact is None:
            # Todo, handle presence coming from contacts not in roster
            return
        logger.log_roster_change(jid.bare, 'got online')
        resource = Resource(jid.full, {
            'priority': presence.get_priority() or 0,
            'status': presence['status'],
            'show': presence['show'],
            })
        self.events.trigger('normal_presence', presence, resource)
        self.add_information_message_to_conversation_tab(jid.full, '\x195}%s is \x194}online' % (jid.full))
        if time.time() - self.connection_time > 20:
            # We do not display messages if we recently logged in
            if presence['status']:
                self.information("\x193}%s \x195}is \x194}online\x195} (\x19o%s\x195})" % (resource.jid.bare, presence['status']), "Roster")
            else:
                self.information("\x193}%s \x195}is \x194}online\x195}" % resource.jid.bare, "Roster")
            self.add_information_message_to_conversation_tab(jid.bare, '\x195}%s is \x194}online' % (jid.bare))
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def on_groupchat_presence(self, presence):
        """
        Triggered whenever a presence stanza is received from a user in a multi-user chat room.
        Display the presence on the room window and update the
        presence information of the concerned user
        """
        from_room = presence['from'].bare
        tab = self.get_tab_by_name(from_room, tabs.MucTab)
        if tab:
            self.events.trigger('muc_presence', presence, tab)
            tab.handle_presence(presence)


    ### Connection-related handlers ###

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
        if not self.plugins_autoloaded: # Do not reload plugins on reconnection
            self.autoload_plugins()
        self.information(_("Authentication success."))
        self.information(_("Your JID is %s") % self.xmpp.boundjid.full)
        if not self.xmpp.anon:
            # request the roster
            self.xmpp.get_roster()
            # send initial presence
            if config.get('send_initial_presence', 'true').lower() == 'true':
                pres = self.xmpp.make_presence()
                self.events.trigger('send_normal_presence', pres)
                pres.send()
        bookmark.get_local()
        if not self.xmpp.anon and not config.get('use_remote_bookmarks', 'true').lower() == 'false':
            bookmark.get_remote(self.xmpp)
        for bm in [item for item in bookmark.bookmarks if item.autojoin]:
            tab = self.get_tab_by_name(bm.jid, tabs.MucTab)
            if not tab:
                self.open_new_room(bm.jid, bm.nick, False)
            nick = bm.nick if bm.nick else self.own_nick
            self.initial_joins.append(bm.jid)
            histo_length= config.get('muc_history_length', 20)
            if histo_length == -1:
                histo_length= None
            if histo_length is not None:
                histo_length= str(histo_length)
            muc.join_groupchat(self.xmpp, bm.jid, nick, None, histo_length)

    ### Other handlers ###

    def on_status_codes(self, message):
        """
        Handle groupchat messages with status codes.
        Those are received when a room configuration change occurs.
        """
        room_from = message['from']
        tab = self.get_tab_by_name(room_from, tabs.MucTab)
        status_codes = set([s.attrib['code'] for s in message.findall('{%s}x/{%s}status' % (tabs.NS_MUC_USER, tabs.NS_MUC_USER))])
        if '101' in status_codes:
            self.information('Your affiliation in the room %s changed' % room_from, 'Info')
        elif tab and status_codes:
            show_unavailable = '102' in status_codes
            hide_unavailable = '103' in status_codes
            non_priv = '104' in status_codes
            logging_on = '170' in status_codes
            logging_off= '171' in status_codes
            non_anon = '172' in status_codes
            semi_anon = '173' in status_codes
            full_anon = '174' in status_codes
            modif = False
            if show_unavailable or hide_unavailable or non_priv or logging_off\
                    or non_anon or semi_anon or full_anon:
                tab.add_message('\x19%(info_col)s}Info: A configuration change not privacy-related occured.' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
                modif = True
            if show_unavailable:
                tab.add_message('\x19%(info_col)s}Info: The unavailable members are now shown.' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
            elif hide_unavailable:
                tab.add_message('\x19%(info_col)s}Info: The unavailable members are now hidden.' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
            if non_anon:
                tab.add_message('\x191}Warning:\x19%(info_col)s} The room is now not anonymous. (public JID)' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
            elif semi_anon:
                tab.add_message('\x19%(info_col)s}Info: The room is now semi-anonymous. (moderators-only JID)' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
            elif full_anon:
                tab.add_message('\x19%(info_col)s}Info: The room is now fully anonymous.' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
            if logging_on:
                tab.add_message('\x191}Warning: \x19%(info_col)s}This room is publicly logged' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
            elif logging_off:
                tab.add_message('\x19%(info_col)s}Info: This room is not logged anymore.' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
            if modif:
                self.refresh_window()

    def on_groupchat_subject(self, message):
        """
        Triggered when the topic is changed.
        """
        nick_from = message['mucnick']
        room_from = message.getMucroom()
        tab = self.get_tab_by_name(room_from, tabs.MucTab)
        subject = message['subject']
        if not subject or not tab:
            return
        if nick_from:
            self.add_message_to_text_buffer(tab._text_buffer,
                    _("\x19%(info_col)s}%(nick)s set the subject to: %(subject)s") %
                    {'info_col': get_theme().COLOR_INFORMATION_TEXT[0], 'nick':nick_from, 'subject':subject},
                    time=None)
        else:
            self.add_message_to_text_buffer(tab._text_buffer, _("\x19%(info_col)s}The subject is: %(subject)s") %
                    {'subject':subject, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]},
                    time=None)
        tab.topic = subject
        if self.get_tab_by_name(room_from, tabs.MucTab) is self.current_tab():
            self.refresh_window()

    def on_data_form(self, message):
        """
        When a data form is received
        """
        self.information('%s' % message)

    def on_attention(self, message):
        """
        Attention probe received.
        """
        jid_from = message['from']
        self.information('%s requests your attention!' % jid_from, 'Info')
        for tab in self.tabs:
            if tab.get_name() == jid_from:
                tab.state = 'attention'
                self.refresh_tab_win()
                return
        for tab in self.tabs:
            if tab.get_name() == jid_from.bare:
                tab.state = 'attention'
                self.refresh_tab_win()
                return
        self.information('%s tab not found.' % jid_from, 'Error')

    def room_error(self, error, room_name):
        """
        Display the error in the tab
        """
        tab = self.get_tab_by_name(room_name)
        error_message = self.get_error_message(error)
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

    def outgoing_stanza(self, stanza):
        """
        We are sending a new stanza, write it in the xml buffer if needed.
        """
        if self.xml_tabs:
            self.add_message_to_text_buffer(self.xml_buffer, '\x191}<--\x19o %s' % stanza)
            if isinstance(self.current_tab(), tabs.XMLTab):
                self.current_tab().refresh()
                self.doupdate()

    def incoming_stanza(self, stanza):
        """
        We are receiving a new stanza, write it in the xml buffer if needed.
        """
        if self.xml_tabs:
            self.add_message_to_text_buffer(self.xml_buffer, '\x192}-->\x19o %s' % stanza)
            if isinstance(self.current_tab(), tabs.XMLTab):
                self.current_tab().refresh()
                self.doupdate()

    def validate_ssl(self, pem):
        """
        Check the server certificate using the sleekxmpp ssl_cert event
        """
        if config.get('ignore_certificate', 'false').lower() == 'true':
            return
        cert = config.get('certificate', '')
        der = ssl.PEM_cert_to_DER_cert(pem)
        found_cert = sha1(der).hexdigest()
        if cert:
            if found_cert == cert:
                log.debug('Cert %s OK', found_cert)
                return
            else:
                saved_input = self.current_tab().input
                log.debug('\nWARNING: CERTIFICATE CHANGED old: %s, new: %s\n', cert, found_cert)
                input = windows.YesNoInput(text="WARNING! Certificate hash changed to %s. Accept? (y/n)" % found_cert)
                self.current_tab().input = input
                input.resize(1, self.current_tab().width, self.current_tab().height-1, 0)
                input.refresh()
                self.doupdate()
                self.paused = True
                while input.value is None:
                    pass
                self.current_tab().input = saved_input
                self.paused = False
                if input.value:
                    self.information('Setting new certificate: old: %s, new: %s' % (cert, found_cert), 'Info')
                    log.debug('Setting certificate to %s', found_cert)
                    config.set_and_save('certificate', found_cert)
                else:
                    self.information('You refused to validate the certificate. You are now disconnected', 'Info')
                    self.xmpp.disconnect()
        else:
            log.debug('First time. Setting certificate to %s', found_cert)
            config.set_and_save('certificate', found_cert)




class KeyDict(dict):
    """
    A dict, with a wrapper for get() that will return a custom value
    if the key starts with _exc_
    """
    def get(self, k, d=None):
        if isinstance(k, str) and k.startswith('_exc_') and len(k) > 5:
            return lambda: dict.get(self, '_exc_')(k[5:])
        return dict.get(self, k, d)


