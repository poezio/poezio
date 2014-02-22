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
import pipes
import ssl

from functools import reduce
from hashlib import sha1
from threading import Event
from datetime import datetime
from xml.etree import cElementTree as ET

import pep
import common
import theming
import logging
import singleton
import collections

from sleekxmpp import JID, InvalidJID
from common import safeJID
from sleekxmpp.xmlstream.stanzabase import StanzaBase
from sleekxmpp.xmlstream.handler import Callback
from sleekxmpp.xmlstream.matcher import StanzaPath

log = logging.getLogger(__name__)

import multiuserchat as muc
import tabs

import fixes
import decorators
import xhtml
import events
import pubsub
import windows
import connection
import timed_events
import bookmark

from plugin_manager import PluginManager

from data_forms import DataFormsTab
from config import config, firstrun, options as config_opts
from logger import logger
from roster import roster
from contact import Contact, Resource
from text_buffer import TextBuffer, CorrectionError
from keyboard import keyboard
from theming import get_theme, dump_tuple
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
Command = collections.namedtuple('Command', 'func desc comp short usage')

class Core(object):
    """
    “Main” class of poezion
    """

    def __init__(self):
        # All uncaught exception are given to this callback, instead
        # of being displayed on the screen and exiting the program.
        sys.excepthook = self.on_exception
        self.connection_time = time.time()
        status = config.get('status', None)
        status = possible_show.get(status, None)
        self.status = Status(show=status,
                message=config.get('status_message', ''))
        self.running = True
        self.xmpp = singleton.Singleton(connection.Connection)
        self.xmpp.core = self
        roster.set_node(self.xmpp.client_roster)
        decorators.refresh_wrapper.core = self
        self.paused = False
        self.event = Event()
        self.debug = False
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
        self.xml_tab = False
        self.xml_buffer = TextBuffer()

        self.tabs = []
        self._current_tab_nb = 0
        self.previous_tab_nb = 0

        self.own_nick = config.get('default_nick', '') or self.xmpp.boundjid.user or os.environ.get('USER') or 'poezio'

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
        self.commands = {}
        self.register_initial_commands()

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
            "M-[-D": self.rotate_rooms_left,
            'kLFT3': self.rotate_rooms_left,
            "KEY_F(6)": self.rotate_rooms_right,
            "^N": self.rotate_rooms_right,
            "M-[-C": self.rotate_rooms_right,
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
            'M-D': self.scroll_info_up,
            'M-C': self.scroll_info_down,
            'M-k': self.escape_next_key,
        ######## actions mappings ##########
            '_bookmark': self.command_bookmark,
            '_bookmark_local': self.command_bookmark_local,
            '_close_tab': self.close_tab,
            '_disconnect': self.disconnect,
            '_quit': self.command_quit,
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
        self.xmpp.add_event_handler('failed_auth', self.on_failed_auth)
        self.xmpp.add_event_handler('no_auth', self.on_no_auth)
        self.xmpp.add_event_handler("session_start", self.on_session_start)
        self.xmpp.add_event_handler("session_start", self.on_session_start_features)
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
        self.xmpp.add_event_handler("presence_error", self.on_presence_error)
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
        if config.get('enable_user_tune', 'true') != 'false':
            self.xmpp.add_event_handler("user_tune_publish", self.on_tune_event)
        if config.get('enable_user_nick', 'true') != 'false':
            self.xmpp.add_event_handler("user_nick_publish", self.on_nick_received)
        if config.get('enable_user_mood', 'true') != 'false':
            self.xmpp.add_event_handler("user_mood_publish", self.on_mood_event)
        if config.get('enable_user_activity', 'true') != 'false':
            self.xmpp.add_event_handler("user_activity_publish", self.on_activity_event)
        if config.get('enable_user_gaming', 'true') != 'false':
            self.xmpp.add_event_handler("user_gaming_publish", self.on_gaming_event)

        self.initial_joins = []

        self.timed_events = set()

        self.connected_events = {}

        self.pending_invites = {}

        # a dict of the form {'config_option': [list, of, callbacks]}
        # Whenever a configuration option is changed (using /set or by
        # reloading a new config using a signal), all the associated
        # callbacks are triggered.
        # Use Core.add_configuration_handler("option", callback) to add a
        # handler
        # Note that the callback will be called when it’s changed in the global section, OR
        # in a special section.
        # As a special case, handlers can be associated with the empty
        # string option (""), they will be called for every option change
        # The callback takes two argument: the config option, and the new
        # value
        self.configuration_change_handlers = {"": []}
        self.add_configuration_handler("create_gaps", self.on_gaps_config_change)
        self.add_configuration_handler("plugins_dir", self.on_plugins_dir_config_change)
        self.add_configuration_handler("plugins_conf_dir", self.on_plugins_conf_dir_config_change)
        self.add_configuration_handler("connection_timeout_delay", self.xmpp.set_keepalive_values)
        self.add_configuration_handler("connection_check_interval", self.xmpp.set_keepalive_values)
        self.add_configuration_handler("themes_dir", theming.update_themes_dir)
        self.add_configuration_handler("", self.on_any_config_change)

    def on_any_config_change(self, option, value):
        """
        Update the roster, in case a roster option changed.
        """
        roster.modified()

    def add_configuration_handler(self, option, callback):
        """
        Add a callback, associated with the given option. It will be called
        each time the configuration option is changed using /set or by
        reloading the configuration with a signal
        """
        if option not in self.configuration_change_handlers:
            self.configuration_change_handlers[option] = []
        self.configuration_change_handlers[option].append(callback)

    def trigger_configuration_change(self, option, value):
        """
        Triggers all the handlers associated with the given configuration
        option
        """
        # First call the callbacks associated with any configuration change
        for callback in self.configuration_change_handlers[""]:
            callback(option, value)
        # and then the callbacks associated with this specific option, if
        # any
        if option not in self.configuration_change_handlers:
            return
        for callback in self.configuration_change_handlers[option]:
            callback(option, value)

    def on_gaps_config_change(self, option, value):
        """
        Called when the option create_gaps is changed.
        Remove all gaptabs if switching from gaps to nogaps.
        """
        if value.lower() == "false":
            self.tabs = list(filter(lambda x: bool(x), self.tabs))

    def on_plugins_dir_config_change(self, option, value):
        """
        Called when the plugins_dir option is changed
        """
        path = os.path.expanduser(value)
        self.plugin_manager.on_plugins_dir_change(path)

    def on_plugins_conf_dir_config_change(self, option, value):
        """
        Called when the plugins_conf_dir option is changed
        """
        path = os.path.expanduser(value)
        self.plugin_manager.on_plugins_conf_dir_change(path)

    def sigusr_handler(self, num, stack):
        """
        Handle SIGUSR1 (10)
        When caught, reload all the possible files.
        """
        log.debug("SIGUSR1 caught, reloading the files…")
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
        # Copy the old config in a dict
        old_config = config.to_dict()
        config.read_file(config.file_name)
        # Compare old and current config, to trigger the callbacks of all
        # modified options
        for section in config.sections():
            old_section = old_config.get(section, {})
            for option in config.options(section):
                old_value = old_section.get(option)
                new_value = config.get(option, "", section)
                if new_value != old_value:
                    self.trigger_configuration_change(option, new_value)
        log.debug("Config reloaded.")
        # in case some roster options have changed
        roster.modified()

    def exit_from_signal(self, *args, **kwargs):
        """
        Quit when receiving SIGHUP or SIGTERM

        do not save the config because it is not a normal exit
        (and only roster UI things are not yet saved)
        """
        log.debug("Either SIGHUP or SIGTERM received. Exiting…")
        if config.get('enable_user_mood', 'true') != 'false':
            self.xmpp.plugin['xep_0107'].stop(block=False)
        if config.get('enable_user_activity', 'true') != 'false':
            self.xmpp.plugin['xep_0108'].stop(block=False)
        if config.get('enable_user_gaming', 'true') != 'false':
            self.xmpp.plugin['xep_0196'].stop(block=False)
        self.plugin_manager.disable_plugins()
        self.disconnect('')
        self.running = False
        try:
            self.reset_curses()
        except: # too bad
            pass
        sys.exit()

    def autoload_plugins(self):
        """
        Load the plugins on startup.
        """
        plugins = config.get('plugins_autoload', '')
        if ':' in plugins:
            for plugin in plugins.split(':'):
                self.plugin_manager.load(plugin)
        else:
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
        if firstrun:
            self.information(_(
                'It seems that it is the first time you start poezio.\n'
                'The online help is here http://poezio.eu/doc/en/\n'
                'No room is joined by default, but you can join poezio’s chatroom '
                '(with /join poezio@muc.poezio.eu), where you can ask for help or tell us how great it is.'
            ), 'Help')
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
                # Transform that stupid char into what we actually meant
                if char == '\x1f':
                    char = '^/'
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
            big_char_list = [replace_key_with_bound(key)\
                             for key in self.read_keyboard()]
            # whether to refresh after ALL keys have been handled
            for char_list in separate_chars_from_bindings(big_char_list):
                if self.paused:
                    self.current_tab().input.do_command(char_list[0])
                    self.current_tab().input.prompt()
                    self.event.set()
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
        if not roster.save_to_config_file() or \
                not config.silent_set('info_win_height', self.information_win_size, 'var'):
            self.information(_('Unable to write in the config file'), 'Error')

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
            if not self.get_conversation_by_jid(roster_row.jid, False):
                self.open_conversation_window(roster_row.jid)
            else:
                self.focus_tab_named(roster_row.jid)
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
        Execute an external command on the local or a remote machine,
        depending on the conf. For example, to open a link in a browser, do
        exec_command(["firefox", "http://poezio.eu"]), and this will call
        the command on the correct computer.

        The command argument is a list of strings, not quoted or escaped in
        any way. The escaping is done here if needed.

        The remote execution is done
        by writing the command on a fifo.  That fifo has to be on the
        machine where poezio is running, and accessible (through sshfs for
        example) from the local machine (where poezio is not running). A
        very simple daemon (daemon.py) reads on that fifo, and executes any
        command that is read in it. Since we can only write strings to that
        fifo, each argument has to be pipes.quote()d. That way the
        shlex.split on the reading-side of the daemon will be safe.

        You cannot use a real command line with pipes, redirections etc, but
        this function supports a simple case redirection to file: if the
        before-last argument of the command is ">" or ">>", then the last
        argument is considered to be a filename where the command stdout
        will be written. For example you can do exec_command(["echo",
        "coucou les amis coucou coucou", ">", "output.txt"]) and this will
        work. If you try to do anything else, your |, [, <<, etc will be
        interpreted as normal command arguments, not shell special tokens.
        """
        if config.get('exec_remote', 'false') == 'true':
            # We just write the command in the fifo
            if not self.remote_fifo:
                try:
                    self.remote_fifo = Fifo(os.path.join(config.get('remote_fifo_path', './'), 'poezio.fifo'), 'w')
                except (OSError, IOError) as e:
                    log.error('Could not open the fifo for writing (%s)',
                            os.path.join(config.get('remote_fifo_path', './'), 'poezio.fifo'),
                            exc_info=True)
                    self.information('Could not open fifo file for writing: %s' % (e,), 'Error')
                    return
            command_str = ' '.join([pipes.quote(arg.replace('\n', ' ')) for arg in command]) + '\n'
            try:
                self.remote_fifo.write(command_str)
            except (IOError) as e:
                log.error('Could not write in the fifo (%s): %s',
                            os.path.join(config.get('remote_fifo_path', './'), 'poezio.fifo'),
                            repr(command),
                            exc_info=True)
                self.information('Could not execute %s: %s' % (command, e,), 'Error')
                self.remote_fifo = None
        else:
            e = Executor(command)
            try:
                e.start()
            except ValueError as e:
                log.error('Could not execute command (%s)', repr(command), exc_info=True)
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
            log.error('Execute failed (%s)', line, exc_info=True)


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
        if config.get('save_status', 'true').lower() != 'false':
            if not config.silent_set('status', pres if pres else '') or \
                    not config.silent_set('status_message', msg.replace('\n', '|') if msg else ''):
                self.information(_('Unable to write in the config file'), 'Error')

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
            if isinstance(tab, tabs.MucTab):
                tab.command_part(msg)
        self.xmpp.disconnect()
        if reconnect:
            self.xmpp.start()

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

    def get_conversation_by_jid(self, jid, create=True, fallback_barejid=True):
        """
        From a JID, get the tab containing the conversation with it.
        If none already exist, and create is "True", we create it
        and return it. Otherwise, we return None.

        If fallback_barejid is True, then this method will seek other
        tabs with the same barejid, instead of searching only by fulljid.
        """
        jid = safeJID(jid)
        # We first check if we have a static conversation opened with this precise resource
        conversation = self.get_tab_by_name(jid.full, tabs.StaticConversationTab)
        if jid.bare == jid.full and not conversation:
            conversation = self.get_tab_by_name(jid.full, tabs.DynamicConversationTab)

        if not conversation and fallback_barejid:
            # If not, we search for a conversation with the bare jid
            conversation = self.get_tab_by_name(jid.bare, tabs.DynamicConversationTab)
            if not conversation:
                if create:
                    # We create a dynamic conversation with the bare Jid if
                    # nothing was found (and we lock it to the resource
                    # later)
                    conversation = self.open_conversation_window(jid.bare, False)
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
            elif new_pos < old_pos:
                self.tabs[old_pos] = tabs.GapTab()
                self.tabs.insert(new_pos, tab)
            else:
                return False
            i = self.tabs.index(tab)
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

    def focus_tab_named(self, tab_name, type_=None):
        """Returns True if it found a tab to focus on"""
        for tab in self.tabs:
            if tab.get_name() == tab_name:
                if (type_ and (isinstance(tab, type_))) or not type_:
                    self.command_win('%s' % (tab.nb,))
                return True
        return False

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
        Open a new conversation tab and focus it if needed. If a resource is
        provided, we open a StaticConversationTab, else a
        DynamicConversationTab
        """
        if safeJID(jid).resource:
            new_tab = tabs.StaticConversationTab(jid)
        else:
            new_tab = tabs.DynamicConversationTab(jid)
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
            tab.add_message(msg, typ=2)

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
                nb -= 1
                while not self.tabs[nb]: # remove the trailing gaps
                    self.tabs.pop()
                    nb -= 1
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
        self.current_tab().on_gain_focus()
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
            tab.add_message(msg, typ=2)
            if self.current_tab() is tab:
                self.refresh_window()


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
        colors = get_theme().INFO_COLORS
        color = colors.get(typ.lower(), colors.get('default', None))
        nb_lines = self.information_buffer.add_message(msg, nickname=typ, nick_color=color)
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
        stdscr.idlok(1)
        stdscr.keypad(1)
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
            return 0
        if self.information_win_size == 14:
            return 0
        self.information_win_size += nb
        if self.information_win_size > 14:
            nb = nb - (self.information_win_size - 14)
            self.information_win_size = 14
        self.resize_global_information_win()
        for tab in self.tabs:
            tab.on_info_win_size_changed()
        self.refresh_window()
        return nb

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
        result = self.grow_information_win(size)
        timed_event = timed_events.DelayedEvent(time, self.shrink_information_win, result)
        self.add_timed_event(timed_event)
        self.refresh_window()

    def toggle_left_pane(self):
        """
        Enable/disable the left panel.
        """
        enabled = config.get('enable_vertical_tab_list', 'false')
        if not config.silent_set('enable_vertical_tab_list', 'false' if enabled == 'true' else 'true'):
            self.information(_('Unable to write in the config file'), 'Error')
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
            with g_lock:
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
        get_user_input() has a timeout: it returns None when the timeout
        occurs. In that case we do not return (we loop until we get
        a non-None value), but we check for timed events instead.
        """
        res = keyboard.get_user_input(self.stdscr)
        while res is None:
            self.check_timed_events()
            res = keyboard.get_user_input(self.stdscr)
        return res

    def escape_next_key(self):
        """
        Tell the Keyboard object that the next key pressed by the user
        should be escaped. See Keyboard.get_user_input
        """
        keyboard.escape_next_key()

####################### Commands and completions ##############################

    def register_command(self, name, func, *, desc='', shortdesc='', completion=None, usage=''):
        if name in self.commands:
            return
        if not desc and shortdesc:
            desc = shortdesc
        self.commands[name] = Command(func, desc, completion, shortdesc, usage)

    def command_help(self, arg):
        """
        /help <command_name>
        """
        args = arg.split()
        if not args:
            color = dump_tuple(get_theme().COLOR_HELP_COMMANDS)
            acc = []
            buff = ['Global commands:']
            for command in self.commands:
                if isinstance(self.commands[command], Command):
                    acc.append('  \x19%s}%s\x19o - %s' % (color, command, self.commands[command].short))
                else:
                    acc.append('  \x19%s}%s\x19o' % (color, command))
            acc = sorted(acc)
            buff.extend(acc)
            acc = []
            buff.append('Tab-specific commands:')
            commands = self.current_tab().commands
            for command in commands:
                if isinstance(commands[command], Command):
                    acc.append('  \x19%s}%s\x19o - %s' % (color, command, commands[command].short))
                else:
                    acc.append('  \x19%s}%s\x19o' % (color, command))
            acc = sorted(acc)
            buff.extend(acc)

            msg = '\n'.join(buff)
            msg += _("\nType /help <command_name> to know what each command does")
        if args:
            command = args[0].lstrip('/').strip()

            if command in self.current_tab().commands:
                tup = self.current_tab().commands[command]
            elif command in self.commands:
                tup = self.commands[command]
            else:
                self.information(_('Unknown command: %s') % command, 'Error')
                return
            if isinstance(tup, Command):
                msg = _('Usage: /%s %s\n' % (command, tup.usage))
                msg += tup.desc
            else:
                msg = tup[1]
        self.information(msg, 'Help')

    def completion_help(self, the_input):
        """Completion for /help."""
        commands = sorted(self.commands.keys()) + sorted(self.current_tab().commands.keys())
        return the_input.new_completion(commands, 1, quotify=False)

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
        return the_input.new_completion(list_, 1, quotify=False)

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
        if the_input.get_argument_position() == 1:
            return the_input.new_completion([status for status in possible_show], 1, ' ', quotify=False)

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
        except:
            self.information(_('Could not send directed presence'), 'Error')
            log.debug('Could not send directed presence to %s', jid, exc_info=True)
            return
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
        arg = the_input.get_argument_position()
        if arg == 1:
            return the_input.auto_completion([jid for jid in roster.jids()], '', quotify=True)
        elif arg == 2:
            return the_input.auto_completion([status for status in possible_show], '', quotify=True)

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
            log.error('Completion for /theme failed', exc_info=True)
            return
        theme_files = [name[:-3] for name in names if name.endswith('.py')]
        if not 'default' in theme_files:
            theme_files.append('default')
        return the_input.new_completion(theme_files, 1, '', quotify=False)

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
        old_tab = self.current_tab()
        if isinstance(nb, int):
            if 0 <= nb < len(self.tabs):
                if not self.tabs[nb]:
                    return
                self.current_tab_nb = nb
        else:
            matchs = []
            for tab in self.tabs:
                for name in tab.matching_names():
                    if nb.lower() in name[1].lower():
                        matchs.append((name[0], tab))
                        self.current_tab_nb = tab.nb
            if not matchs:
                return
            tab = min(matchs, key=lambda m: m[0])[1]
            self.current_tab_nb = tab.nb
        old_tab.on_lose_focus()
        self.current_tab().on_gain_focus()
        self.refresh_window()

    def completion_win(self, the_input):
        """Completion for /win"""
        l = []
        for tab in self.tabs:
            l.extend(tab.matching_names())
        l = [i[1] for i in l]
        return the_input.new_completion(l, 1, '', quotify=False)

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
                    if not old_tab and value == tab.get_name():
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
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            nodes = [tab.get_name() for tab in self.tabs if tab]
            nodes.remove('Roster')
            return the_input.new_completion(nodes, 1, ' ', quotify=True)

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
            return the_input.new_completion(muc_serv_list, 1, quotify=False)

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
                                                             res.get('os') or _('an unknown platform'))
            self.information(version, 'Info')

        args = common.shell_split(arg)
        if len(args) < 1:
            return self.command_help('version')
        jid = safeJID(args[0])
        if jid.resource or jid not in roster:
            fixes.get_version(self.xmpp, jid, callback=callback)
        elif jid in roster:
            for resource in roster[jid].resources:
                fixes.get_version(self.xmpp, resource.jid, callback=callback)
            else:
                fixes.get_version(self.xmpp, jid, callback=callback)

    def completion_version(self, the_input):
        """Completion for /version"""
        n = the_input.get_argument_position(quoted=True)
        if n >= 2:
            return
        comp = reduce(lambda x, y: x + [i.jid for i in y], (roster[jid].resources for jid in roster.jids() if len(roster[jid])), [])
        return the_input.new_completion(sorted(comp), 1, '', quotify=True)

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
            if args[0].startswith('@'): # we try to join a server directly
                server_root = True
                info = safeJID(args[0][1:])
            else:
                info = safeJID(args[0])
                server_root = False
            if info == '' and len(args[0]) > 1 and args[0][0] == '/':
                nick = args[0][1:]
            elif info.resource == '':
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
                if room.find('@') == -1 and not server_root: # no server is provided, like "/join hello"
                    # use the server of the current room if available
                    # check if the current room's name has a server
                    if isinstance(self.current_tab(), tabs.MucTab) and\
                            self.current_tab().get_name().find('@') != -1:
                        room += '@%s' % safeJID(self.current_tab().get_name()).domain
                    else:
                        room = args[0]
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
        if password is None: # try to use a saved password
            password = config.get_by_tabname('password', None, room, fallback=False)
        if tab and not tab.joined:
            if tab.last_connection:
                delta = datetime.now() - tab.last_connection
                seconds = delta.seconds + delta.days * 24 * 3600 if tab.last_connection is not None else 0
                seconds = int(seconds)
            else:
                seconds = 0
            muc.join_groupchat(self, room, nick, password,
                               histo_length, current_status.message, current_status.show, seconds=seconds)
        if not tab:
            self.open_new_room(room, nick)
            muc.join_groupchat(self, room, nick, password,
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
        Completion for /join

        Try to complete the MUC JID:
            if only a resource is provided, complete with the default nick
            if only a server is provided, complete with the rooms from the
                disco#items of that server
            if only a nodepart is provided, complete with the servers of the
                current joined rooms
        """
        n = the_input.get_argument_position(quoted=True)
        args = common.shell_split(the_input.text)
        if n != 1:
            # we are not on the 1st argument of the command line
            return False
        if len(args) == 1:
            args.append('')
        jid = safeJID(args[1])
        if args[1].endswith('@') and not jid.user and not jid.server:
            jid.user = args[1][:-1]

        relevant_rooms = []
        relevant_rooms.extend(sorted(self.pending_invites.keys()))
        bookmarks = {str(elem.jid): False for elem in bookmark.bookmarks}
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab):
                name = tab.get_name()
                if name in bookmarks and not tab.joined:
                    bookmarks[name] = True
        relevant_rooms.extend(sorted(room[0] for room in bookmarks.items() if room[1]))

        if the_input.last_completion:
            return the_input.new_completion([], 1, quotify=True)

        if jid.server and not jid.user:
            # no room was given: complete the node
            try:
                response = self.xmpp.plugin['xep_0030'].get_items(jid=jid.server, block=True, timeout=1)
            except:
                log.error('/join completion: Unable to get the list of rooms for %s',
                        jid.server,
                        exc_info=True)
                response = None
            if response:
                items = response['disco_items'].get_items()
            else:
                return True
            items = sorted('%s/%s' % (tup[0], jid.resource) for tup in items)
            return the_input.new_completion(items, 1, quotify=True, override=True)
        elif jid.user:
            # we are writing the server: complete the server
            serv_list = []
            for tab in self.tabs:
                if isinstance(tab, tabs.MucTab) and tab.joined:
                    serv_list.append('%s@%s'% (jid.user, safeJID(tab.get_name()).host))
            serv_list.extend(relevant_rooms)
            return the_input.new_completion(serv_list, 1, quotify=True)
        elif args[1].startswith('/'):
            # we completing only a resource
            return the_input.new_completion(['/%s' % self.own_nick], 1, quotify=True)
        else:
            return the_input.new_completion(relevant_rooms, 1, quotify=True)
        return True

    def command_bookmark_local(self, arg=''):
        """
        /bookmark_local [room][/nick] [password]
        """
        args = common.shell_split(arg)
        nick = None
        password = None
        if len(args) == 0 and not isinstance(self.current_tab(), tabs.MucTab):
            return
        if len(args) == 0:
            tab = self.current_tab()
            roomname = tab.get_name()
            if tab.joined and tab.own_nick != self.own_nick:
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
            if len(args) > 1:
                password = args[1]

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
        bm.password = password
        bm.method = "local"
        bookmark.save_local()
        self.information(_('Your local bookmarks are now: %s') %
                [b for b in bookmark.bookmarks if b.method == 'local'], 'Info')

    def completion_bookmark_local(self, the_input):
        """Completion for /bookmark_local"""
        n = the_input.get_argument_position(quoted=True)
        args = common.shell_split(the_input.text)

        if n >= 2:
            return
        if len(args) == 1:
            args.append('')
        jid = safeJID(args[1])

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
            return the_input.new_completion(jids_list, 1, quotify=True)
        muc_list = [tab.get_name() for tab in self.tabs if isinstance(tab, tabs.MucTab)]
        muc_list.append('*')
        return the_input.new_completion(muc_list, 1, quotify=True)

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
                autojoin = False if args[1].lower() != 'true' else True
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
                autojoin = False if args[1].lower() != 'true' else True
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
        bm.autojoin = autojoin
        if bookmark.save_remote(self.xmpp):
            self.information('Bookmark added.', 'Info')
        self.information(_('Your remote bookmarks are now: %s') %
                [b for b in bookmark.bookmarks if b.method in ('pep', 'privatexml')], 'Info')

    def completion_bookmark(self, the_input):
        """Completion for /bookmark"""
        args = common.shell_split(the_input.text)
        n = the_input.get_argument_position(quoted=True)

        if n == 2:
            return the_input.new_completion(['true', 'false'], 2, quotify=True)
        if n >= 3:
            return

        if len(args) == 1:
            args.append('')
        jid = safeJID(args[1])

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
            return the_input.new_completion(jids_list, 1, quotify=True)
        muc_list = [tab.get_name() for tab in self.tabs if isinstance(tab, tabs.MucTab)]
        muc_list.sort()
        muc_list.append('*')
        return the_input.new_completion(muc_list, 1, quotify=True)

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
        return the_input.new_completion([bm.jid for bm in bookmark.bookmarks], 1, quotify=False)

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
            info = config.set_and_save(option, value)
            self.trigger_configuration_change(option, value)
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
                info = plugin.config.set_and_save(option, value, section)
            else:
                section = args[0]
                option = args[1]
                value = args[2]
                info = config.set_and_save(option, value, section)
                self.trigger_configuration_change(option, value)
        self.call_for_resize()
        self.information(*info)

    def completion_set(self, the_input):
        """Completion for /set"""
        args = common.shell_split(the_input.text)
        n = the_input.get_argument_position(quoted=True)
        if n >= len(args):
            args.append('')
        if n == 1:
            if '|' in args[1]:
                plugin_name, section = args[1].split('|')[:2]
                if not plugin_name in self.plugin_manager.plugins:
                        return the_input.new_completion([], n, quotify=True)
                plugin = self.plugin_manager.plugins[plugin_name]
                end_list = ['%s|%s' % (plugin_name, section) for section in plugin.config.sections()]
            else:
                end_list = config.options('Poezio')
        elif n == 2:
            if '|' in args[1]:
                plugin_name, section = args[1].split('|')[:2]
                if not plugin_name in self.plugin_manager.plugins:
                        return the_input.auto_completion([''], n, quotify=True)
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
        elif n == 3:
            if '|' in args[1]:
                plugin_name, section = args[1].split('|')[:2]
                if not plugin_name in self.plugin_manager.plugins:
                        return the_input.auto_completion([''], n, quotify=True)
                plugin = self.plugin_manager.plugins[plugin_name]
                end_list = [plugin.config.get(args[2], '', section or plugin_name), '']
            else:
                if not config.has_section(args[1]):
                    end_list = ['']
                else:
                    end_list = [config.get(args[2], '', args[1]), '']
        else:
            return
        return the_input.new_completion(end_list, n, quotify=True)

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
            if isinstance(tab, tabs.MucTab) and tab.get_name().endswith(domain):
                if tab.joined:
                    muc.leave_groupchat(tab.core.xmpp, tab.get_name(), tab.own_nick, message)
                tab.joined = False
                if tab.get_name() == domain:
                    self.command_join('"@%s/%s"' %(tab.get_name(), tab.own_nick))
                else:
                    self.command_join('"%s/%s"' %(tab.get_name(), tab.own_nick))

    def completion_server_cycle(self, the_input):
        """Completion for /server_cycle"""
        serv_list = set()
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab):
                serv = safeJID(tab.get_name()).server
                serv_list.add(serv)
        return the_input.new_completion(sorted(serv_list), 1, ' ')

    def command_last_activity(self, arg):
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
        if jid == '':
            return self.command_help('last_activity')
        self.xmpp.plugin['xep_0012'].get_last_activity(jid, block=False, callback=callback)

    def completion_last_activity(self, the_input):
            return the_input.new_completion([jid for jid in roster.jids()], 1, quotify=False)

    def command_mood(self, arg):
        """
        /mood [<mood> [text]]
        """
        args = common.shell_split(arg)
        if not args:
            return self.xmpp.plugin['xep_0107'].stop(block=False)
        mood = args[0]
        if mood not in pep.MOODS:
            return self.information('%s is not a correct value for a mood.' % mood, 'Error')
        if len(args) > 1:
            text = args[1]
        else:
            text = None
        self.xmpp.plugin['xep_0107'].publish_mood(mood, text, callback=dumb_callback, block=False)

    def completion_mood(self, the_input):
        """Completion for /mood"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            return the_input.new_completion(sorted(pep.MOODS.keys()), 1, quotify=True)

    def command_activity(self, arg):
        """
        /activity [<general> [specific] [text]]
        """
        args = common.shell_split(arg)
        length = len(args)
        if not length:
            return self.xmpp.plugin['xep_0108'].stop(block=False)
        general = args[0]
        if general not in pep.ACTIVITIES:
            return self.information('%s is not a correct value for an activity' % general, 'Error')
        specific = None
        text = None
        if length == 2:
            if args[1] in pep.ACTIVITIES[general]:
                specific = args[1]
            else:
                text = args[1]
        elif length == 3:
            specific = args[1]
            text = args[2]
        if specific and specific not in pep.ACTIVITIES[general]:
            return self.information('%s is not a correct value for an activity' % specific, 'Error')
        self.xmpp.plugin['xep_0108'].publish_activity(general, specific, text, callback=dumb_callback, block=False)

    def command_gaming(self, arg):
        """
        /gaming [<game name> [server address]]
        """
        args = common.shell_split(arg)
        if not args:
            return self.xmpp.plugin['xep_0196'].stop(block=False)
        name = args[0]
        if len(args) > 1:
            address = args[1]
        else:
            address = None
        return self.xmpp.plugin['xep_0196'].publish_gaming(name=name, server_address=address, callback=dumb_callback, block=False)

    def completion_activity(self, the_input):
        """Completion for /activity"""
        n = the_input.get_argument_position(quoted=True)
        args = common.shell_split(the_input.text)
        if n == 1:
            return the_input.new_completion(sorted(pep.ACTIVITIES.keys()), n, quotify=True)
        elif n == 2:
            if args[1] in pep.ACTIVITIES:
                l = list(pep.ACTIVITIES[args[1]])
                l.remove('category')
                l.sort()
                return the_input.new_completion(l, n, quotify=True)

    def command_invite(self, arg):
        """/invite <to> <room> [reason]"""
        args = common.shell_split(arg)
        if len(args) < 2:
            return
        reason = args[2] if len(args) > 2 else ''
        to = safeJID(args[0])
        room = safeJID(args[1])
        self.xmpp.plugin['xep_0045'].invite(room, str(to), reason)

    def completion_invite(self, the_input):
        """Completion for /invite"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            return the_input.new_completion(sorted(jid for jid in roster.jids()), n, quotify=True)
        elif n == 2:
            rooms = []
            for tab in self.tabs:
                if isinstance(tab, tabs.MucTab) and tab.joined:
                    rooms.append(tab.get_name())
            rooms.sort()
            return the_input.new_completion(rooms, n, '', quotify=True)

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
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            return the_input.auto_completion(sorted(self.pending_invites.keys()), 1, '', quotify=True)

    ### Commands without a completion in this class ###

    def command_invitations(self, arg=''):
        """/invitations"""
        build = ""
        for invite in self.pending_invites:
            build += "%s by %s" % (invite, safeJID(self.pending_invites[invite]).bare)
        if self.pending_invites:
            build = "You are invited to the following rooms:\n" + build
        else:
            build = "You do not have any pending invitations."
        self.information(build, 'Info')

    def command_quit(self, arg=''):
        """
        /quit
        """
        if len(arg.strip()) != 0:
            msg = arg
        else:
            msg = None
        if config.get('enable_user_mood', 'true') != 'false':
            self.xmpp.plugin['xep_0107'].stop(block=False)
        if config.get('enable_user_activity', 'true') != 'false':
            self.xmpp.plugin['xep_0108'].stop(block=False)
        if config.get('enable_user_gaming', 'true') != 'false':
            self.xmpp.plugin['xep_0196'].stop(block=False)
        self.save_config()
        self.plugin_manager.disable_plugins()
        self.disconnect(msg)
        self.running = False
        self.reset_curses()
        sys.exit()

    def completion_bind(self, the_input):
        n = the_input.get_argument_position()
        if n == 1:
            args = [key for key in self.key_func if not key.startswith('_')]
        elif n == 2:
            args = [key for key in self.key_func]
        else:
            return

        return the_input.new_completion(args, n, '', quotify=False)


        return the_input

    def command_bind(self, arg):
        """
        Bind a key.
        """
        args = common.shell_split(arg)
        if len(args) < 1:
            return self.command_help('bind')
        elif len(args) < 2:
            args.append("")
        if not config.silent_set(args[0], args[1], section='bindings'):
            self.information(_('Unable to write in the config file'), 'Error')
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
            stanza = StanzaBase(self.xmpp, xml=ET.fromstring(arg))
            if stanza.xml.tag == 'iq' and \
                    stanza.xml.attrib.get('type') in ('get', 'set') and \
                    stanza.xml.attrib.get('id'):
                iq_id = stanza.xml.attrib.get('id')

                def iqfunc(iq):
                    self.information('%s' % iq, 'Iq')
                    self.xmpp.remove_handler('Iq %s' % iq_id)

                self.xmpp.register_handler(
                        Callback('Iq %s' % iq_id,
                            StanzaPath('iq@id=%s' % iq_id),
                            iqfunc
                            )
                        )
                log.debug('handler')
            log.debug('%s %s', stanza.xml.tag, stanza.xml.attrib)

            stanza.send()
        except:
            self.information(_('Could not send custom stanza'), 'Error')
            log.debug('/rawxml: Could not send custom stanza (%s)',
                    repr(arg),
                    exc_info=True)


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
        tab = self.get_conversation_by_jid(jid.full, False, fallback_barejid=False)
        if not tab:
            tab = self.open_conversation_window(jid.full, focus=True)
        else:
            self.focus_tab_named(tab.get_name())
        if len(args) > 1:
            tab.command_say(args[1])

    def completion_message(self, the_input):
        """Completion for /message"""
        n = the_input.get_argument_position(quoted=True)
        if n >= 2:
            return
        comp = reduce(lambda x, y: x + [i.jid for i in y], (roster[jid].resources for jid in roster.jids() if len(roster[jid])), [])
        comp = sorted(comp)
        bares = sorted(roster[contact].bare_jid for contact in roster.jids() if len(roster[contact]))
        off = sorted(jid for jid in roster.jids() if jid not in bares)
        comp = bares + comp + off
        return the_input.new_completion(comp, 1, '', quotify=True)

    def command_xml_tab(self, arg=''):
        """/xml_tab"""
        self.xml_tab = True
        xml_tab = self.focus_tab_named('XMLTab', tabs.XMLTab)
        if not xml_tab:
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
        info = ('Your JID is %s\nYour current status is "%s" (%s)'
                '\nYour default nickname is %s\nYou are running poezio %s' % (
                jid,
                message if message else '',
                show if show else 'available',
                nick,
                config_opts.version))
        self.information(info, 'Info')

    def register_initial_commands(self):
        """
        Register the commands when poezio starts
        """
        self.register_command('help', self.command_help,
                usage=_('[command]'),
                shortdesc='\_o< KOIN KOIN KOIN',
                completion=self.completion_help)
        self.register_command('join', self.command_join,
                usage=_("[room_name][@server][/nick] [password]"),
                desc=_("Join the specified room. You can specify a nickname "
                    "after a slash (/). If no nickname is specified, you will"
                    " use the default_nick in the configuration file. You can"
                    " omit the room name: you will then join the room you\'re"
                    " looking at (useful if you were kicked). You can also "
                    "provide a room_name without specifying a server, the "
                    "server of the room you're currently in will be used. You"
                    " can also provide a password to join the room.\nExamples"
                    ":\n/join room@server.tld\n/join room@server.tld/John\n"
                    "/join room2\n/join /me_again\n/join\n/join room@server"
                    ".tld/my_nick password\n/join / password"),
                shortdesc=_('Join a room'),
                completion=self.completion_join)
        self.register_command('exit', self.command_quit,
                desc=_('Just disconnect from the server and exit poezio.'),
                shortdesc=_('Exit poezio.'))
        self.register_command('quit', self.command_quit,
                desc=_('Just disconnect from the server and exit poezio.'),
                shortdesc=_('Exit poezio.'))
        self.register_command('next', self.rotate_rooms_right,
                shortdesc=_('Go to the next room.'))
        self.register_command('prev', self.rotate_rooms_left,
                shortdesc=_('Go to the previous room.'))
        self.register_command('win', self.command_win,
                usage=_('<number or name>'),
                shortdesc=_('Go to the specified room'),
                completion=self.completion_win)
        self.commands['w'] = self.commands['win']
        self.register_command('move_tab', self.command_move_tab,
                usage=_('<source> <destination>'),
                desc=_("Insert the <source> tab at the position of "
                    "<destination>. This will make the following tabs shift in"
                    " some cases (refer to the documentation). A tab can be "
                    "designated by its number or by the beginning of its "
                    "address."),
                shortdesc=_('Move a tab.'),
                completion=self.completion_move_tab)
        self.register_command('show', self.command_status,
                usage=_('<availability> [status message]'),
                desc=_("Sets your availability and (optionally) your status "
                    "message. The <availability> argument is one of \"available"
                    ", chat, away, afk, dnd, busy, xa\" and the optional "
                    "[status message] argument will be your status message."),
                shortdesc=_('Change your availability.'),
                completion=self.completion_status)
        self.commands['status'] = self.commands['show']
        self.register_command('bookmark_local', self.command_bookmark_local,
                usage=_("[roomname][/nick] [password]"),
                desc=_("Bookmark Local: Bookmark locally the specified room "
                    "(you will then auto-join it on each poezio start). This"
                    " commands uses almost the same syntaxe as /join. Type "
                    "/help join for syntax examples. Note that when typing "
                    "\"/bookmark\" on its own, the room will be bookmarked "
                    "with the nickname you\'re currently using in this room "
                    "(instead of default_nick)"),
                shortdesc=_('Bookmark a room locally.'),
                completion=self.completion_bookmark_local)
        self.register_command('bookmark', self.command_bookmark,
                usage=_("[roomname][/nick] [autojoin] [password]"),
                desc=_("Bookmark: Bookmark online the specified room (you "
                    "will then auto-join it on each poezio start if autojoin"
                    " is specified and is 'true'). This commands uses almost"
                    " the same syntax as /join. Type /help join for syntax "
                    "examples. Note that when typing \"/bookmark\" alone, the"
                    " room will be bookmarked with the nickname you\'re "
                    "currently using in this room (instead of default_nick)."),
                shortdesc=_("Bookmark a room online."),
                completion=self.completion_bookmark)
        self.register_command('set', self.command_set,
                usage=_("[plugin|][section] <option> [value]"),
                desc=_("Set the value of an option in your configuration file."
                    " You can, for example, change your default nickname by "
                    "doing `/set default_nick toto` or your resource with `/set"
                    "resource blabla`. You can also set options in specific "
                    "sections with `/set bindings M-i ^i` or in specific plugin"
                    " with `/set mpd_client| host 127.0.0.1`. `toggle` can be "
                    "used as a special value to toggle a boolean option."),
                shortdesc=_("Set the value of an option"),
                completion=self.completion_set)
        self.register_command('theme', self.command_theme,
                usage=_('[theme name]'),
                desc=_("Reload the theme defined in the config file. If theme"
                    "_name is provided, set that theme before reloading it."),
                shortdesc=_('Load a theme'),
                completion=self.completion_theme)
        self.register_command('list', self.command_list,
                usage=_('[server]'),
                desc=_("Get the list of public chatrooms"
                    " on the specified server."),
                shortdesc=_('List the rooms.'),
                completion=self.completion_list)
        self.register_command('message', self.command_message,
                usage=_('<jid> [optional message]'),
                desc=_("Open a conversation with the specified JID (even if it"
                    " is not in our roster), and send a message to it, if the "
                    "message is specified."),
                shortdesc=_('Send a message'),
                completion=self.completion_message)
        self.register_command('version', self.command_version,
                usage='<jid>',
                desc=_("Get the software version of the given JID (usually its"
                    " XMPP client and Operating System)."),
                shortdesc=_('Get the software version of a JID.'),
                completion=self.completion_version)
        self.register_command('server_cycle', self.command_server_cycle,
                usage=_('[domain] [message]'),
                desc=_('Disconnect and reconnect in all the rooms in domain.'),
                shortdesc=_('Cycle a range of rooms'),
                completion=self.completion_server_cycle)
        self.register_command('bind', self.command_bind,
                usage=_(' <key> <equ>'),
                desc=_("Bind a key to another key or to a “command”. For "
                    "example \"/bind ^H KEY_UP\" makes Control + h do the"
                    " same same as the Up key."),
                completion=self.completion_bind,
                shortdesc=_('Bind a key to another key.'))
        self.register_command('load', self.command_load,
                usage=_('<plugin>'),
                shortdesc=_('Load the specified plugin'),
                completion=self.plugin_manager.completion_load)
        self.register_command('unload', self.command_unload,
                usage=_('<plugin>'),
                shortdesc=_('Unload the specified plugin'),
                completion=self.plugin_manager.completion_unload)
        self.register_command('plugins', self.command_plugins,
                shortdesc=_('Show the plugins in use.'))
        self.register_command('presence', self.command_presence,
                usage=_('<JID> [type] [status]'),
                desc=_("Send a directed presence to <JID> and using"
                    " [type] and [status] if provided."),
                shortdesc=_('Send a directed presence.'),
                completion=self.completion_presence)
        self.register_command('rawxml', self.command_rawxml,
                usage='<xml>',
                shortdesc=_('Send a custom xml stanza.'))
        self.register_command('invite', self.command_invite,
                usage=_('<jid> <room> [reason]'),
                desc=_('Invite jid in room with reason.'),
                shortdesc=_('Invite someone in a room.'),
                completion=self.completion_invite)
        self.register_command('invitations', self.command_invitations,
                shortdesc=_('Show the pending invitations.'))
        self.register_command('bookmarks', self.command_bookmarks,
                shortdesc=_('Show the current bookmarks.'))
        self.register_command('remove_bookmark', self.command_remove_bookmark,
                usage='[jid]',
                desc=_("Remove the specified bookmark, or the "
                    "bookmark on the current tab, if any."),
                shortdesc=_('Remove a bookmark'),
                completion=self.completion_remove_bookmark)
        self.register_command('xml_tab', self.command_xml_tab,
                shortdesc=_('Open an XML tab.'))
        self.register_command('runkey', self.command_runkey,
                usage=_('<key>'),
                shortdesc=_('Execute the action defined for <key>.'),
                completion=self.completion_runkey)
        self.register_command('self', self.command_self,
                shortdesc=_('Remind you of who you are.'))
        self.register_command('last_activity', self.command_last_activity,
                usage='<jid>',
                desc=_('Informs you of the last activity of a JID.'),
                shortdesc=_('Get the activity of someone.'),
                completion=self.completion_last_activity)

        if config.get('enable_user_mood', 'true') != 'false':
            self.register_command('activity', self.command_activity,
                    usage='[<general> [specific] [text]]',
                    desc=_('Send your current activity to your contacts (use the completion).'
                           ' Nothing means "stop broadcasting an activity".'),
                    shortdesc=_('Send your activity.'),
                    completion=self.completion_activity)
        if config.get('enable_user_activity', 'true') != 'false':
            self.register_command('mood', self.command_mood,
                    usage='[<mood> [text]]',
                    desc=_('Send your current mood to your contacts (use the completion).'
                           ' Nothing means "stop broadcasting a mood".'),
                    shortdesc=_('Send your mood.'),
                    completion=self.completion_mood)
        if config.get('enable_user_gaming', 'true') != 'false':
            self.register_command('gaming', self.command_gaming,
                    usage='[<game name> [server address]]',
                    desc=_('Send your current gaming activity to your contacts.'
                           ' Nothing means "stop broadcasting a gaming activity".'),
                    shortdesc=_('Send your gaming activity.'),
                    completion=None)

####################### XMPP Event Handlers  ##################################

    def on_session_start_features(self, _):
        """
        Enable carbons & blocking on session start if wanted and possible
        """
        def callback(iq):
            if not iq:
                return
            features = iq['disco_info']['features']
            rostertab = self.get_tab_by_name('Roster')
            rostertab.check_blocking(features)
            if (config.get('enable_carbons', 'true').lower() != 'false' and
                    'urn:xmpp:carbons:2' in features):
                self.xmpp.plugin['xep_0280'].enable()
                self.xmpp.add_event_handler('carbon_received', self.on_carbon_received)
                self.xmpp.add_event_handler('carbon_sent', self.on_carbon_sent)
        features = self.xmpp.plugin['xep_0030'].get_info(jid=self.xmpp.boundjid.domain, callback=callback, block=False)

    def on_carbon_received(self, message):
        recv = message['carbon_received']
        if recv['from'].bare not in roster or roster[recv['from'].bare].subscription == 'none':
            try:
                if self.xmpp.plugin['xep_0030'].has_identity(jid=recv['from'].server, category="conference"):
                    return
            except:
                pass
            else:
                return
        recv['to'] = self.xmpp.boundjid.full
        self.on_normal_message(recv)

    def on_carbon_sent(self, message):
        sent = message['carbon_sent']
        if sent['to'].bare not in roster or roster[sent['to'].bare].subscription == 'none':
            try:
                if self.xmpp.plugin['xep_0030'].has_identity(jid=sent['to'].server, category="conference"):
                    return
            except:
                pass
            else:
                return
        sent['from'] = self.xmpp.boundjid.full
        self.on_normal_message(sent)

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
        logger.log_roster_change(inviter.full, 'invited you to %s' % jid.full)
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
        if message['type'] == 'error':
            return self.information(self.get_error_message(message, deprecated=True), 'Error')
        elif message['type'] == 'headline' and message['body']:
            return self.information('%s says: %s' % (message['from'], message['body']), 'Headline')

        use_xhtml = config.get('enable_xhtml_im', 'true') == 'true'
        body = xhtml.get_body_from_message_stanza(message, use_xhtml=use_xhtml)
        if not body:
            return

        remote_nick = ''
        # normal message, we are the recipient
        if message['to'].bare == self.xmpp.boundjid.bare:
            conv_jid = message['from']
            jid = conv_jid
            color = get_theme().COLOR_REMOTE_USER
            # check for a name
            if conv_jid.bare in roster:
                remote_nick = roster[conv_jid.bare].name
            # check for a received nick
            if not remote_nick and config.get('enable_user_nick', 'true') != 'false':
                if message.xml.find('{http://jabber.org/protocol/nick}nick') is not None:
                    remote_nick = message['nick']['nick']
            own = False
        # we wrote the message (happens with carbons)
        elif message['from'].bare == self.xmpp.boundjid.bare:
            conv_jid = message['to']
            jid = self.xmpp.boundjid
            color = get_theme().COLOR_OWN_NICK
            remote_nick = self.own_nick
            own = True
        # we are not part of that message, drop it
        else:
            return

        conversation = self.get_conversation_by_jid(conv_jid, create=True)
        if isinstance(conversation, tabs.DynamicConversationTab):
            conversation.lock(conv_jid.resource)

        if not remote_nick and conversation.nick:
            remote_nick = conversation.nick
        elif not remote_nick or own:
            remote_nick = conv_jid.user
        conversation.nick = remote_nick

        self.events.trigger('conversation_msg', message, conversation)
        if not message['body']:
            return
        body = xhtml.get_body_from_message_stanza(message, use_xhtml=use_xhtml)
        delayed, date = common.find_delayed_tag(message)

        def try_modify():
            replaced_id = message['replace']['id']
            if replaced_id and (config.get_by_tabname('group_corrections',
                'true', conv_jid.bare).lower() != 'false'):
                try:
                    conversation.modify_message(body, replaced_id, message['id'], jid=jid,
                            nickname=remote_nick)
                    return True
                except CorrectionError:
                    log.error('Unable to correct a message', exc_info=True)
            return False

        if not try_modify():
            conversation.add_message(body, date,
                    nickname=remote_nick,
                    nick_color=color,
                    history=delayed,
                    identifier=message['id'],
                    jid=jid,
                    typ=1)

        if conversation.remote_wants_chatstates is None and not delayed:
            if message['chat_state']:
                conversation.remote_wants_chatstates = True
            else:
                conversation.remote_wants_chatstates = False
        if 'private' in config.get('beep_on', 'highlight private').split():
            if config.get_by_tabname('disable_beep', 'false', conv_jid.bare, False).lower() != 'true':
                curses.beep()
        if self.current_tab() is not conversation:
            conversation.state = 'private'
            self.refresh_tab_win()
        else:
            self.refresh_window()

    def on_nick_received(self, message):
        """
        Called when a pep notification for an user nickname
        is received
        """
        contact = roster[message['from'].bare]
        if not contact:
            return
        item = message['pubsub_event']['items']['item']
        if item.xml.find('{http://jabber.org/protocol/nick}nick'):
            contact.name = item['nick']['nick']
        else:
            contact.name= ''

    def on_gaming_event(self, message):
        """
        Called when a pep notification for user gaming
        is received
        """
        contact = roster[message['from'].bare]
        if not contact:
            return
        item = message['pubsub_event']['items']['item']
        old_gaming = contact.gaming
        if item.xml.find('{urn:xmpp:gaming:0}gaming'):
            item = item['gaming']
            # only name and server_address are used for now
            contact.gaming = {
                    'character_name': item['character_name'],
                    'character_profile': item['character_profile'],
                    'name': item['name'],
                    'level': item['level'],
                    'uri': item['uri'],
                    'server_name': item['server_name'],
                    'server_address': item['server_address'],
                }
        else:
            contact.gaming = {}

        if contact.gaming:
            logger.log_roster_change(contact.bare_jid, 'is playing %s' % (common.format_gaming_string(contact.gaming)))

        if old_gaming != contact.gaming and config.get_by_tabname('display_gaming_notifications', 'false', contact.bare_jid) == 'true':
            if contact.gaming:
                self.information('%s is playing %s' % (contact.bare_jid, common.format_gaming_string(contact.gaming)), 'Gaming')
            else:
                self.information(contact.bare_jid + ' stopped playing.', 'Gaming')

    def on_mood_event(self, message):
        """
        Called when a pep notification for an user mood
        is received.
        """
        contact = roster[message['from'].bare]
        if not contact:
            return
        roster.modified()
        item = message['pubsub_event']['items']['item']
        old_mood = contact.mood
        if item.xml.find('{http://jabber.org/protocol/mood}mood'):
            mood = item['mood']['value']
            if mood:
                mood = pep.MOODS.get(mood, mood)
                text = item['mood']['text']
                if text:
                    mood = '%s (%s)' % (mood, text)
                contact.mood = mood
            else:
                contact.mood = ''
        else:
            contact.mood = ''

        if contact.mood:
            logger.log_roster_change(contact.bare_jid, 'has now the mood: %s' % contact.mood)

        if old_mood != contact.mood and config.get_by_tabname('display_mood_notifications', 'false', contact.bare_jid) == 'true':
            if contact.mood:
                self.information('Mood from '+ contact.bare_jid + ': ' + contact.mood, 'Mood')
            else:
                self.information(contact.bare_jid + ' stopped having his/her mood.', 'Mood')

    def on_activity_event(self, message):
        """
        Called when a pep notification for an user activity
        is received.
        """
        contact = roster[message['from'].bare]
        if not contact:
            return
        roster.modified()
        item = message['pubsub_event']['items']['item']
        old_activity = contact.activity
        if item.xml.find('{http://jabber.org/protocol/activity}activity'):
            try:
                activity = item['activity']['value']
            except ValueError:
                return
            if activity[0]:
                general = pep.ACTIVITIES.get(activity[0])
                s = general['category']
                if activity[1]:
                    s = s + '/' + general.get(activity[1], 'other')
                text = item['activity']['text']
                if text:
                    s = '%s (%s)' % (s, text)
                contact.activity = s
            else:
                contact.activity = ''
        else:
            contact.activity = ''

        if contact.activity:
            logger.log_roster_change(contact.bare_jid, 'has now the activity %s' % contact.activity)

        if old_activity != contact.activity and config.get_by_tabname('display_activity_notifications', 'false', contact.bare_jid) == 'true':
            if contact.activity:
                self.information('Activity from '+ contact.bare_jid + ': ' + contact.activity, 'Activity')
            else:
                self.information(contact.bare_jid + ' stopped doing his/her activity.', 'Activity')

    def on_tune_event(self, message):
        """
        Called when a pep notification for an user tune
        is received
        """
        contact = roster[message['from'].bare]
        if not contact:
            return
        roster.modified()
        item = message['pubsub_event']['items']['item']
        old_tune = contact.tune
        if item.xml.find('{http://jabber.org/protocol/tune}tune'):
            item = item['tune']
            contact.tune =  {
                    'artist': item['artist'],
                    'length': item['length'],
                    'rating': item['rating'],
                    'source': item['source'],
                    'title': item['title'],
                    'track': item['track'],
                    'uri': item['uri']
                }
        else:
            contact.tune = {}

        if contact.tune:
            logger.log_roster_change(message['from'].bare, 'is now listening to %s' % common.format_tune_string(contact.tune))

        if old_tune != contact.tune and config.get_by_tabname('display_tune_notifications', 'false', contact.bare_jid) == 'true':
            if contact.tune:
                self.information(
                        'Tune from '+ message['from'].bare + ': ' + common.format_tune_string(contact.tune),
                        'Tune')
            else:
                self.information(contact.bare_jid + ' stopped listening to music.', 'Tune')

    def on_groupchat_message(self, message):
        """
        Triggered whenever a message is received from a multi-user chat room.
        """
        if message['subject']:
            return
        room_from = message['from'].bare

        if message['type'] == 'error': # Check if it's an error
            return self.room_error(message, room_from)

        tab = self.get_tab_by_name(room_from, tabs.MucTab)
        if not tab:
            self.information(_("message received for a non-existing room: %s") % (room_from))
            return

        nick_from = message['mucnick']
        user = tab.get_user_by_name(nick_from)
        if user and user in tab.ignores:
            return

        self.events.trigger('muc_msg', message, tab)
        use_xhtml = config.get('enable_xhtml_im', 'true') == 'true'
        body = xhtml.get_body_from_message_stanza(message, use_xhtml=use_xhtml)
        if not body:
            return

        old_state = tab.state
        delayed, date = common.find_delayed_tag(message)
        replaced_id = message['replace']['id']
        replaced = False
        if replaced_id is not '' and (config.get_by_tabname(
            'group_corrections', 'true', message['from'].bare).lower() != 'false'):
            try:
                if tab.modify_message(body, replaced_id, message['id'], time=date,
                        nickname=nick_from, user=user):
                    self.events.trigger('highlight', message, tab)
                replaced = True
            except CorrectionError:
                log.error('Unable to correct a message', exc_info=True)
        if not replaced and tab.add_message(body, date, nick_from, history=delayed, identifier=message['id'], jid=message['from'], typ=1):
            self.events.trigger('highlight', message, tab)

        if message['from'].resource == tab.own_nick:
            tab.last_sent_message = message

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
        if not nick_from:
            return self.on_groupchat_message(message)

        room_from = jid.bare
        use_xhtml = config.get('enable_xhtml_im', 'true') == 'true'
        body = xhtml.get_body_from_message_stanza(message, use_xhtml=use_xhtml)
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
        body = xhtml.get_body_from_message_stanza(message, use_xhtml=use_xhtml)
        if not body or not tab:
            return
        replaced_id = message['replace']['id']
        replaced = False
        user = tab.parent_muc.get_user_by_name(nick_from)
        if replaced_id is not '' and (config.get_by_tabname(
            'group_corrections', 'true', room_from).lower() != 'false'):
            try:
                tab.modify_message(body, replaced_id, message['id'], user=user, jid=message['from'],
                        nickname=nick_from)
                replaced = True
            except CorrectionError:
                log.error('Unable to correct a message', exc_info=True)
        if not replaced:
            tab.add_message(body, time=None, nickname=nick_from,
                            forced_user=user,
                            identifier=message['id'],
                            jid=message['from'],
                            typ=1)

        if tab.remote_wants_chatstates is None:
            if message['chat_state']:
                tab.remote_wants_chatstates = True
            else:
                tab.remote_wants_chatstates = False
        if 'private' in config.get('beep_on', 'highlight private').split():
            if config.get_by_tabname('disable_beep', 'false', jid.full, False).lower() != 'true':
                curses.beep()
        if tab is self.current_tab():
            self.refresh_window()
        else:
            tab.state = 'private'
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
        tab.remote_wants_chatstates = True
        self.events.trigger('normal_chatstate', message, tab)
        tab.chatstate = state
        if state == 'gone' and isinstance(tab, tabs.DynamicConversationTab):
            tab.unlock()
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
        tab.remote_wants_chatstates = True
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
        if contact and contact.subscription in ('from', 'both'):
            return
        elif contact and contact.subscription == 'to':
            self.xmpp.sendPresence(pto=jid, ptype='subscribed')
            self.xmpp.sendPresence(pto=jid)
        else:
            if not contact:
                contact = roster.get_and_set(jid)
            roster.update_contact_groups(contact)
            contact.pending_in = True
            self.information('%s wants to subscribe to your presence' % jid, 'Roster')
            self.get_tab_by_number(0).state = 'highlight'
            roster.modified()
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

        roster.modified()

        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()

    def on_subscription_remove(self, presence):
        """unsubscribe received"""
        jid = presence['from'].bare
        contact = roster[jid]
        if not contact:
            return
        roster.modified()
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
        roster.modified()
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
        tab = self.get_conversation_by_jid(jid, create=False)
        if isinstance(tab, tabs.DynamicConversationTab) and tab.get_dest_jid() != jid.full:
            tab.unlock()
        if contact is None:
            return
        roster.modified()
        contact.error = None
        self.events.trigger('normal_presence', presence, contact[jid.full])
        tab = self.get_conversation_by_jid(jid, create=False)
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()
        elif self.current_tab() == tab:
            tab.refresh()
            self.doupdate()

    def on_presence_error(self, presence):
        jid = presence['from']
        contact = roster[jid.bare]
        if not contact:
            return
        roster.modified()
        contact.error = presence['error']['type'] + ': ' + presence['error']['condition']

    def on_got_offline(self, presence):
        """
        A JID got offline
        """
        if presence.match('presence/muc') or presence.xml.find('{http://jabber.org/protocol/muc#user}x'):
            return
        jid = presence['from']
        if not logger.log_roster_change(jid.bare, 'got offline'):
            self.information(_('Unable to write in the log file'), 'Error')
        # If a resource got offline, display the message in the conversation with this
        # precise resource.
        if jid.resource:
            self.add_information_message_to_conversation_tab(jid.full, '\x195}%s is \x191}offline' % (jid.full))
        self.add_information_message_to_conversation_tab(jid.bare, '\x195}%s is \x191}offline' % (jid.bare))
        self.information('\x193}%s \x195}is \x191}offline' % (jid.bare), 'Roster')
        roster.modified()
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
        roster.modified()
        if not logger.log_roster_change(jid.bare, 'got online'):
            self.information(_('Unable to write in the log file'), 'Error')
        resource = Resource(jid.full, {
            'priority': presence.get_priority() or 0,
            'status': presence['status'],
            'show': presence['show'],
            })
        self.events.trigger('normal_presence', presence, resource)
        self.add_information_message_to_conversation_tab(jid.full, '\x195}%s is \x194}online' % (jid.full))
        if time.time() - self.connection_time > 10:
            # We do not display messages if we recently logged in
            if presence['status']:
                self.information("\x193}%s \x195}is \x194}online\x195} (\x19o%s\x195})" % (safeJID(resource.jid).bare, presence['status']), "Roster")
            else:
                self.information("\x193}%s \x195}is \x194}online\x195}" % safeJID(resource.jid).bare, "Roster")
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
        roster.modified()
        for tab in self.tabs:
            if isinstance(tab, tabs.MucTab):
                tab.disconnect()
        self.information(_("Disconnected from server."))

    def on_failed_auth(self, event):
        """
        Authentication failed
        """
        self.information(_("Authentication failed (bad credentials?)."))

    def on_no_auth(self, event):
        """
        Authentication failed (no mech)
        """
        self.information(_("Authentication failed, no login method available."))

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
            if config.get('send_initial_presence', 'true').lower() != 'false':
                pres = self.xmpp.make_presence()
                pres['show'] = self.status.show
                pres['status'] = self.status.message
                self.events.trigger('send_normal_presence', pres)
                pres.send()
        bookmark.get_local()
        if not self.xmpp.anon and not config.get('use_remote_bookmarks', 'true').lower() == 'false':
            bookmark.get_remote(self.xmpp)
        for bm in bookmark.bookmarks:
            tab = self.get_tab_by_name(bm.jid, tabs.MucTab)
            nick = bm.nick if bm.nick else self.own_nick
            if not tab:
                self.open_new_room(bm.jid, nick, False)
            self.initial_joins.append(bm.jid)
            histo_length = config.get('muc_history_length', 20)
            if histo_length == -1:
                histo_length= None
            if histo_length is not None:
                histo_length= str(histo_length)
            # do not join rooms that do not have autojoin
            # but display them anyway
            if bm.autojoin:
                muc.join_groupchat(self, bm.jid, nick,
                        passwd=bm.password,
                        maxhistory=histo_length,
                        status=self.status.message,
                        show=self.status.show)

        if config.get('enable_user_nick', 'true') != 'false':
            self.xmpp.plugin['xep_0172'].publish_nick(nick=self.own_nick, callback=dumb_callback, block=False)
        self.xmpp.plugin['xep_0115'].update_caps()

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
                tab.add_message('\x19%(info_col)s}Info: A configuration change not privacy-related occured.' %
                        {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
                        typ=2)
                modif = True
            if show_unavailable:
                tab.add_message('\x19%(info_col)s}Info: The unavailable members are now shown.' %
                        {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
                        typ=2)
            elif hide_unavailable:
                tab.add_message('\x19%(info_col)s}Info: The unavailable members are now hidden.' %
                        {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
                        typ=2)
            if non_anon:
                tab.add_message('\x191}Warning:\x19%(info_col)s} The room is now not anonymous. (public JID)' %
                        {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
                        typ=2)
            elif semi_anon:
                tab.add_message('\x19%(info_col)s}Info: The room is now semi-anonymous. (moderators-only JID)' %
                        {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
                        typ=2)
            elif full_anon:
                tab.add_message('\x19%(info_col)s}Info: The room is now fully anonymous.' %
                        {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
                        typ=2)
            if logging_on:
                tab.add_message('\x191}Warning: \x19%(info_col)s}This room is publicly logged' %
                        {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
                        typ=2)
            elif logging_off:
                tab.add_message('\x19%(info_col)s}Info: This room is not logged anymore.' %
                        {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
                        typ=2)
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
            tab.add_message(_("\x19%(info_col)s}%(nick)s set the subject to: %(subject)s") %
                    {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT), 'nick':nick_from, 'subject':subject},
                    time=None,
                    typ=2)
        else:
            tab.add_message(_("\x19%(info_col)s}The subject is: %(subject)s") %
                    {'subject':subject, 'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
                    time=None,
                    typ=2)
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
        tab.add_message(error_message, highlight=True, nickname='Error', nick_color=get_theme().COLOR_ERROR_MSG, typ=2)
        code = error['error']['code']
        if code == '401':
            msg = _('To provide a password in order to join the room, type "/join / password" (replace "password" by the real password)')
            tab.add_message(msg, typ=2)
        if code == '409':
            if config.get('alternative_nickname', '') != '':
                self.command_join('%s/%s'% (tab.name, tab.own_nick+config.get('alternative_nickname', '')))
            else:
                if not tab.joined:
                    tab.add_message(_('You can join the room with an other nick, by typing "/join /other_nick"'), typ=2)
        self.refresh_window()

    def outgoing_stanza(self, stanza):
        """
        We are sending a new stanza, write it in the xml buffer if needed.
        """
        if self.xml_tab:
            self.add_message_to_text_buffer(self.xml_buffer, '\x191}<--\x19o %s' % stanza)
            if isinstance(self.current_tab(), tabs.XMLTab):
                self.current_tab().refresh()
                self.doupdate()

    def incoming_stanza(self, stanza):
        """
        We are receiving a new stanza, write it in the xml buffer if needed.
        """
        if self.xml_tab:
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
        # update the cert representation when it uses the old one
        if cert and not ':' in cert:
            cert = ':'.join(i + j for i, j in zip(cert[::2], cert[1::2])).upper()
            config.set_and_save('certificate', cert)

        der = ssl.PEM_cert_to_DER_cert(pem)
        digest = sha1(der).hexdigest().upper()
        found_cert = ':'.join(i + j for i, j in zip(digest[::2], digest[1::2]))
        if cert:
            if found_cert == cert:
                log.debug('Cert %s OK', found_cert)
                return
            else:
                saved_input = self.current_tab().input
                log.debug('\nWARNING: CERTIFICATE CHANGED old: %s, new: %s\n', cert, found_cert)
                input = windows.YesNoInput(text="WARNING! Server certificate has changed, accept? (y/n) (%s)" % found_cert)
                self.current_tab().input = input
                input.resize(1, self.current_tab().width, self.current_tab().height-1, 0)
                input.refresh()
                self.doupdate()
                self.paused = True
                while input.value is None:
                    self.event.wait()
                self.current_tab().input = saved_input
                self.paused = False
                if input.value:
                    self.information('Setting new certificate: old: %s, new: %s' % (cert, found_cert), 'Info')
                    log.debug('Setting certificate to %s', found_cert)
                    if not config.silent_set('certificate', found_cert):
                        self.information(_('Unable to write in the config file'), 'Error')
                else:
                    self.information('You refused to validate the certificate. You are now disconnected', 'Info')
                    self.xmpp.disconnect()
        else:
            log.debug('First time. Setting certificate to %s', found_cert)
            if not config.silent_set('certificate', found_cert):
                self.information(_('Unable to write in the config file'), 'Error')




class KeyDict(dict):
    """
    A dict, with a wrapper for get() that will return a custom value
    if the key starts with _exc_
    """
    def get(self, k, d=None):
        if isinstance(k, str) and k.startswith('_exc_') and len(k) > 5:
            return lambda: dict.get(self, '_exc_')(k[5:])
        return dict.get(self, k, d)

def replace_key_with_bound(key):
    bind = config.get(key, key, 'bindings')
    if not bind:
        bind = key
    return bind

def dumb_callback(*args, **kwargs):
    pass

