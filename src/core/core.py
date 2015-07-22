"""
Module defining the Core class, which is the central orchestrator
of poezio and contains the main loop, the list of tabs, sets the state
of everything; it also contains global commands, completions and event
handlers but those are defined in submodules in order to avoir cluttering
this file.
"""
import logging

log = logging.getLogger(__name__)

import asyncio
import shutil
import curses
import os
import pipes
import sys
import time

from slixmpp.xmlstream.handler import Callback

import connection
import decorators
import events
import singleton
import tabs
import theming
import timed_events
import windows

from bookmarks import BookmarkList
from common import safeJID
from config import config, firstrun
from contact import Contact, Resource
from daemon import Executor
from fifo import Fifo
from logger import logger
from plugin_manager import PluginManager
from roster import roster
from size_manager import SizeManager
from text_buffer import TextBuffer
from theming import get_theme
import keyboard

from . import completions
from . import commands
from . import handlers
from . structs import possible_show, DEPRECATED_ERRORS, \
        ERROR_AND_STATUS_CODES, Command, Status


class Core(object):
    """
    “Main” class of poezion
    """

    def __init__(self):
        # All uncaught exception are given to this callback, instead
        # of being displayed on the screen and exiting the program.
        sys.excepthook = self.on_exception
        self.connection_time = time.time()
        self.stdscr = None
        status = config.get('status')
        status = possible_show.get(status, None)
        self.status = Status(show=status,
                message=config.get('status_message'))
        self.running = True
        self.xmpp = singleton.Singleton(connection.Connection)
        self.xmpp.core = self
        self.keyboard = keyboard.Keyboard()
        roster.set_node(self.xmpp.client_roster)
        decorators.refresh_wrapper.core = self
        self.bookmarks = BookmarkList()
        self.debug = False
        self.remote_fifo = None
        # a unique buffer used to store global informations
        # that are displayed in almost all tabs, in an
        # information window.
        self.information_buffer = TextBuffer()
        self.information_win_size = config.get('info_win_height', section='var')
        self.information_win = windows.TextWin(300)
        self.information_buffer.add_window(self.information_win)
        self.left_tab_win = None

        self.tab_win = windows.GlobalInfoBar()
        # Whether the XML tab is opened
        self.xml_tab = None
        self.xml_buffer = TextBuffer()

        self.tabs = []
        self._current_tab_nb = 0
        self.previous_tab_nb = 0

        own_nick = config.get('default_nick')
        own_nick = own_nick or self.xmpp.boundjid.user
        own_nick = own_nick or os.environ.get('USER')
        own_nick = own_nick or 'poezio'
        self.own_nick = own_nick

        self.plugins_autoloaded = False
        self.plugin_manager = PluginManager(self)
        self.events = events.EventHandler()

        self.size = SizeManager(self, windows.Win)

        # Set to True whenever we consider that we have been disconnected
        # from the server because of a legitimate reason (bad credentials,
        # or explicit disconnect from the user for example), in that case we
        # should not try to auto-reconnect, even if auto_reconnect is true
        # in the user config.
        self.legitimate_disconnect = False

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
        if not config.get('send_initial_presence'):
            del self.commands['status']
            del self.commands['show']

        # A list of integers. For example if the user presses Alt+j, 2, 1,
        # we will insert 2, then 1 in that list, and we will finally build
        # the number 21 and use it with command_win, before clearing the
        # list.
        self.room_number_jump = []
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
            '_exc_': self.try_execute,
        }
        self.key_func.update(key_func)

        # Add handlers
        self.xmpp.add_event_handler('connecting', self.on_connecting)
        self.xmpp.add_event_handler('connected', self.on_connected)
        self.xmpp.add_event_handler('connection_failed', self.on_failed_connection)
        self.xmpp.add_event_handler('disconnected', self.on_disconnected)
        self.xmpp.add_event_handler('stream_error', self.on_stream_error)
        self.xmpp.add_event_handler('failed_all_auth', self.on_failed_all_auth)
        self.xmpp.add_event_handler('no_auth', self.on_no_auth)
        self.xmpp.add_event_handler("session_start", self.on_session_start)
        self.xmpp.add_event_handler("session_start",
                                    self.on_session_start_features)
        self.xmpp.add_event_handler("groupchat_presence",
                                    self.on_groupchat_presence)
        self.xmpp.add_event_handler("groupchat_message",
                                    self.on_groupchat_message)
        self.xmpp.add_event_handler("groupchat_invite",
                                    self.on_groupchat_invitation)
        self.xmpp.add_event_handler("groupchat_direct_invite",
                                    self.on_groupchat_direct_invitation)
        self.xmpp.add_event_handler("groupchat_decline",
                                    self.on_groupchat_decline)
        self.xmpp.add_event_handler("groupchat_config_status",
                                    self.on_status_codes)
        self.xmpp.add_event_handler("groupchat_subject",
                                    self.on_groupchat_subject)
        self.xmpp.add_event_handler("message", self.on_message)
        self.xmpp.add_event_handler("message_error", self.on_error_message)
        self.xmpp.add_event_handler("receipt_received", self.on_receipt)
        self.xmpp.add_event_handler("got_online", self.on_got_online)
        self.xmpp.add_event_handler("got_offline", self.on_got_offline)
        self.xmpp.add_event_handler("roster_update", self.on_roster_update)
        self.xmpp.add_event_handler("changed_status", self.on_presence)
        self.xmpp.add_event_handler("presence_error", self.on_presence_error)
        self.xmpp.add_event_handler("roster_subscription_request",
                                    self.on_subscription_request)
        self.xmpp.add_event_handler("roster_subscription_authorized",
                                    self.on_subscription_authorized)
        self.xmpp.add_event_handler("roster_subscription_remove",
                                    self.on_subscription_remove)
        self.xmpp.add_event_handler("roster_subscription_removed",
                                    self.on_subscription_removed)
        self.xmpp.add_event_handler("message_xform", self.on_data_form)
        self.xmpp.add_event_handler("chatstate_active",
                                    self.on_chatstate_active)
        self.xmpp.add_event_handler("chatstate_composing",
                                    self.on_chatstate_composing)
        self.xmpp.add_event_handler("chatstate_paused",
                                    self.on_chatstate_paused)
        self.xmpp.add_event_handler("chatstate_gone",
                                    self.on_chatstate_gone)
        self.xmpp.add_event_handler("chatstate_inactive",
                                    self.on_chatstate_inactive)
        self.xmpp.add_event_handler("attention", self.on_attention)
        self.xmpp.add_event_handler("ssl_cert", self.validate_ssl)
        self.xmpp.add_event_handler("ssl_invalid_chain", self.ssl_invalid_chain)
        self.xmpp.add_event_handler('carbon_received', self.on_carbon_received)
        self.xmpp.add_event_handler('carbon_sent', self.on_carbon_sent)

        self.all_stanzas = Callback('custom matcher',
                                    connection.MatchAll(None),
                                    self.incoming_stanza)
        self.xmpp.register_handler(self.all_stanzas)
        if config.get('enable_user_tune'):
            self.xmpp.add_event_handler("user_tune_publish",
                                        self.on_tune_event)
        if config.get('enable_user_nick'):
            self.xmpp.add_event_handler("user_nick_publish",
                                        self.on_nick_received)
        if config.get('enable_user_mood'):
            self.xmpp.add_event_handler("user_mood_publish",
                                        self.on_mood_event)
        if config.get('enable_user_activity'):
            self.xmpp.add_event_handler("user_activity_publish",
                                        self.on_activity_event)
        if config.get('enable_user_gaming'):
            self.xmpp.add_event_handler("user_gaming_publish",
                                        self.on_gaming_event)

        self.initial_joins = []

        self.connected_events = {}

        self.pending_invites = {}

        # a dict of the form {'config_option': [list, of, callbacks]}
        # Whenever a configuration option is changed (using /set or by
        # reloading a new config using a signal), all the associated
        # callbacks are triggered.
        # Use Core.add_configuration_handler("option", callback) to add a
        # handler
        # Note that the callback will be called when it’s changed in the
        # global section, OR in a special section.
        # As a special case, handlers can be associated with the empty
        # string option (""), they will be called for every option change
        # The callback takes two argument: the config option, and the new
        # value
        self.configuration_change_handlers = {"": []}
        self.add_configuration_handler("create_gaps",
                                       self.on_gaps_config_change)
        self.add_configuration_handler("request_message_receipts",
                                       self.on_request_receipts_config_change)
        self.add_configuration_handler("ack_message_receipts",
                                       self.on_ack_receipts_config_change)
        self.add_configuration_handler("plugins_dir",
                                       self.on_plugins_dir_config_change)
        self.add_configuration_handler("plugins_conf_dir",
                                       self.on_plugins_conf_dir_config_change)
        self.add_configuration_handler("connection_timeout_delay",
                                       self.xmpp.set_keepalive_values)
        self.add_configuration_handler("connection_check_interval",
                                       self.xmpp.set_keepalive_values)
        self.add_configuration_handler("themes_dir",
                                       theming.update_themes_dir)
        self.add_configuration_handler("theme",
                                       self.on_theme_config_change)
        self.add_configuration_handler("use_bookmarks_method",
                                       self.on_bookmarks_method_config_change)
        self.add_configuration_handler("password",
                                       self.on_password_change)
        self.add_configuration_handler("enable_vertical_tab_list",
                                       self.on_vertical_tab_list_config_change)
        self.add_configuration_handler("vertical_tab_list_size",
                                       self.on_vertical_tab_list_config_change)
        self.add_configuration_handler("deterministic_nick_colors",
                                       self.on_nick_determinism_changed)
        self.add_configuration_handler("enable_carbons",
                                       self.on_carbons_switch)
        self.add_configuration_handler("hide_user_list",
                                       self.on_hide_user_list_change)

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

    def on_hide_user_list_change(self, option, value):
        """
        Called when the hide_user_list option changes
        """
        self.call_for_resize()

    def on_bookmarks_method_config_change(self, option, value):
        """
        Called when the use_bookmarks_method option changes
        """
        if value not in ('pep', 'privatexml'):
            return
        self.bookmarks.preferred = value
        self.bookmarks.save(self.xmpp, core=self)

    def on_gaps_config_change(self, option, value):
        """
        Called when the option create_gaps is changed.
        Remove all gaptabs if switching from gaps to nogaps.
        """
        if value.lower() == "false":
            self.tabs = list(tab for tab in self.tabs if tab)

    def on_request_receipts_config_change(self, option, value):
        """
        Called when the request_message_receipts option changes
        """
        self.xmpp.plugin['xep_0184'].auto_request = config.get(option,
                                                               default=True)

    def on_ack_receipts_config_change(self, option, value):
        """
        Called when the ack_message_receipts option changes
        """
        self.xmpp.plugin['xep_0184'].auto_ack = config.get(option, default=True)

    def on_plugins_dir_config_change(self, option, value):
        """
        Called when the plugins_dir option is changed
        """
        path = os.path.expanduser(value)
        self.plugin_manager.on_plugins_dir_change(path)

    def on_vertical_tab_list_config_change(self, option, value):
        """
        Called when the enable_vertical_tab_list option is changed
        """
        self.call_for_resize()

    def on_plugins_conf_dir_config_change(self, option, value):
        """
        Called when the plugins_conf_dir option is changed
        """
        path = os.path.expanduser(value)
        self.plugin_manager.on_plugins_conf_dir_change(path)

    def on_theme_config_change(self, option, value):
        """
        Called when the theme option is changed
        """
        error_msg = theming.reload_theme()
        if error_msg:
            self.information(error_msg, 'Warning')
        self.refresh_window()

    def on_password_change(self, option, value):
        """
        Set the new password in the slixmpp.ClientXMPP object
        """
        self.xmpp.password = value


    def on_nick_determinism_changed(self, option, value):
        """If we change the value to true, we call /recolor on all the MucTabs, to
        make the current nick colors reflect their deterministic value.
        """
        if value.lower() == "true":
            for tab in self.get_tabs(tabs.MucTab):
                tab.command_recolor('')

    def on_carbons_switch(self, option, value):
        """Whenever the user enables or disables carbons using /set, we should
        inform the server immediately, this way we do not require a restart
        for the change to take effect
        """
        if value:
            self.xmpp.plugin['xep_0280'].enable()
        else:
            self.xmpp.plugin['xep_0280'].disable()

    def reload_config(self):
        # reload all log files
        log.debug("Reloading the log files…")
        logger.reload_all()
        log.debug("Log files reloaded.")
        # reload the theme
        log.debug("Reloading the theme…")
        theming.reload_theme()
        log.debug("Theme reloaded.")
        # reload the config from the disk
        log.debug("Reloading the config…")
        # Copy the old config in a dict
        old_config = config.to_dict()
        config.read_file()
        # Compare old and current config, to trigger the callbacks of all
        # modified options
        for section in config.sections():
            old_section = old_config.get(section, {})
            for option in config.options(section):
                old_value = old_section.get(option)
                new_value = config.get(option, default="", section=section)
                if new_value != old_value:
                    self.trigger_configuration_change(option, new_value)
        log.debug("Config reloaded.")
        # in case some roster options have changed
        roster.modified()

    def sigusr_handler(self, num, stack):
        """
        Handle SIGUSR1 (10)
        When caught, reload all the possible files.
        """
        log.debug("SIGUSR1 caught, reloading the files…")
        self.reload_config()

    def exit_from_signal(self, *args, **kwargs):
        """
        Quit when receiving SIGHUP or SIGTERM or SIGPIPE

        do not save the config because it is not a normal exit
        (and only roster UI things are not yet saved)
        """
        sig = args[0]
        signals = {
                1: 'SIGHUP',
                13: 'SIGPIPE',
                15: 'SIGTERM',
                }

        log.error("%s received. Exiting…", signals[sig])
        if config.get('enable_user_mood'):
            self.xmpp.plugin['xep_0107'].stop()
        if config.get('enable_user_activity'):
            self.xmpp.plugin['xep_0108'].stop()
        if config.get('enable_user_gaming'):
            self.xmpp.plugin['xep_0196'].stop()
        self.plugin_manager.disable_plugins()
        self.disconnect('%s received' % signals.get(sig))
        self.xmpp.add_event_handler("disconnected", self.exit, disposable=True)

    def autoload_plugins(self):
        """
        Load the plugins on startup.
        """
        plugins = config.get('plugins_autoload')
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
        self.information('Welcome to poezio!', 'Info')
        if firstrun:
            self.information(
                'It seems that it is the first time you start poezio.\n'
                'The online help is here http://doc.poez.io/\n'
                'No room is joined by default, but you can join poezio’s'
                ' chatroom (with /join poezio@muc.poez.io), where you can'
                ' ask for help or tell us how great it is.',
                'Help')
        self.refresh_window()
        self.xmpp.plugin['xep_0012'].begin_idle(jid=self.xmpp.boundjid)

    def exit(self, event=None):
        log.debug("exit(%s)" % (event,))
        asyncio.get_event_loop().stop()

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

    def sigwinch_handler(self):
        """A work-around for ncurses resize stuff, which sucks. Normally, ncurses
        catches SIGWINCH itself. In its signal handler, it updates the
        windows structures (for example the size, etc) and it
        ungetch(KEY_RESIZE). That way, the next time we call getch() we know
        that a resize occured and we can act on it. BUT poezio doesn’t call
        getch() until it knows it will return something. The problem is we
        can’t know that, because stdin is not affected by this KEY_RESIZE
        value (it is only inserted in a ncurses internal fifo that we can’t
        access).

        The (ugly) solution is to handle SIGWINCH ourself, trigger the
        change of the internal windows sizes stored in ncurses module, using
        sizes that we get using shutil, ungetch the KEY_RESIZE value and
        then call getch to handle the resize on poezio’s side properly.
        """
        size = shutil.get_terminal_size()
        curses.resizeterm(size.lines, size.columns)
        curses.ungetch(curses.KEY_RESIZE)
        self.on_input_readable()

    def on_input_readable(self):
        """
        main loop waiting for the user to press a key
        """
        def replace_line_breaks(key):
            "replace ^J with \n"
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
                assert char
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

        log.debug("Input is readable.")
        big_char_list = [replace_key_with_bound(key)\
                         for key in self.read_keyboard()]
        log.debug("Got from keyboard: %s", (big_char_list,))

        # whether to refresh after ALL keys have been handled
        for char_list in separate_chars_from_bindings(big_char_list):
            # Special case for M-x where x is a number
            if len(char_list) == 1:
                char = char_list[0]
                if char.startswith('M-') and len(char) == 3:
                    try:
                        nb = int(char[2])
                    except ValueError:
                        pass
                    else:
                        if self.current_tab().nb == nb and config.get('go_to_previous_tab_on_alt_number'):
                            self.go_to_previous_tab()
                        else:
                            self.command_win('%d' % nb)
                # search for keyboard shortcut
                func = self.key_func.get(char, None)
                if func:
                    func()
                else:
                    self.do_command(replace_line_breaks(char), False)
            else:
                self.do_command(''.join(char_list), True)
        if self.status.show not in ('xa', 'away'):
            self.xmpp.plugin['xep_0012'].begin_idle(jid=self.xmpp.boundjid)
        self.doupdate()

    def save_config(self):
        """
        Save config in the file just before exit
        """
        ok = roster.save_to_config_file()
        ok = ok and config.silent_set('info_win_height',
                                      self.information_win_size,
                                      'var')
        if not ok:
            self.information('Unable to save runtime preferences'
                             ' in the config file',
                             'Error')

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
            if not self.get_conversation_by_jid(roster_row.jid,
                                                False,
                                                fallback_barejid=False):
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
                self.information("Unknown command (%s)" % (command),
                                 'Error')

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
        if config.get('exec_remote'):
            # We just write the command in the fifo
            fifo_path = config.get('remote_fifo_path')
            if not self.remote_fifo:
                try:
                    self.remote_fifo = Fifo(os.path.join(fifo_path,
                                                         'poezio.fifo'),
                                            'w')
                except (OSError, IOError) as exc:
                    log.error('Could not open the fifo for writing (%s)',
                               os.path.join(fifo_path, './', 'poezio.fifo'),
                               exc_info=True)
                    self.information('Could not open the fifo '
                                     'file for writing: %s' % exc,
                                     'Error')
                    return

            args = (pipes.quote(arg.replace('\n', ' ')) for arg in command)
            command_str = ' '.join(args) + '\n'
            try:
                self.remote_fifo.write(command_str)
            except (IOError) as exc:
                log.error('Could not write in the fifo (%s): %s',
                            os.path.join(fifo_path, './', 'poezio.fifo'),
                            repr(command),
                            exc_info=True)
                self.information('Could not execute %s: %s' % (command, exc),
                                 'Error')
                self.remote_fifo = None
        else:
            executor = Executor(command)
            try:
                executor.start()
            except ValueError as exc:
                log.error('Could not execute command (%s)',
                          repr(command),
                          exc_info=True)
                self.information('%s' % exc, 'Error')


    def do_command(self, key, raw):
        """
        Execute the action associated with a key

        Or if keyboard.continuation_keys_callback is set, call it instead. See
        the comment of this variable.
        """
        if not key:
            return
        if keyboard.continuation_keys_callback is not None:
            # Reset the callback to None BEFORE calling it, because this
            # callback MAY set a new callback itself, and we don’t want to
            # erase it in that case
            cb = keyboard.continuation_keys_callback
            keyboard.continuation_keys_callback = None
            cb(key)
        else:
            self.current_tab().on_input(key, raw)


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
        event.handler.cancel()

    def add_timed_event(self, event):
        """Add a new timed event"""
        event.handler = asyncio.get_event_loop().call_later(event.delay,
                                                            event.callback,
                                                            *event.args)

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
        if config.get('save_status'):
            ok = config.silent_set('status', pres if pres else '')
            msg = msg.replace('\n', '|') if msg else ''
            ok = ok and config.silent_set('status_message', msg)
            if not ok:
                self.information('Unable to save the status in '
                                 'the config file', 'Error')

    def get_bookmark_nickname(self, room_name):
        """
        Returns the nickname associated with a bookmark
        or the default nickname
        """
        bm = self.bookmarks[room_name]
        if bm:
            return bm.nick
        return self.own_nick

    def disconnect(self, msg='', reconnect=False):
        """
        Disconnect from remote server and correctly set the states of all
        parts of the client (for example, set the MucTabs as not joined, etc)
        """
        self.legitimate_disconnect = True
        msg = msg or ''
        for tab in self.get_tabs(tabs.MucTab):
            tab.command_part(msg)
        self.xmpp.disconnect()
        if reconnect:
            # Add a one-time event to reconnect as soon as we are
            # effectively disconnected
            self.xmpp.add_event_handler('disconnected', lambda event: self.xmpp.connect(), disposable=True)

    def send_message(self, msg):
        """
        Function to use in plugins to send a message in the current
        conversation.
        Returns False if the current tab is not a conversation tab
        """
        if not isinstance(self.current_tab(), tabs.ChatTab):
            return False
        self.current_tab().command_say(msg)
        return True

    def invite(self, jid, room, reason=None):
        """
        Checks if the sender supports XEP-0249, then send an invitation,
        or a mediated one if it does not.
        TODO: allow passwords
        """
        def callback(iq):
            if not iq:
                return
            if 'jabber:x:conference' in iq['disco_info'].get_features():
                self.xmpp.plugin['xep_0249'].send_invitation(
                        jid,
                        room,
                        reason=reason)
            else: # fallback
                self.xmpp.plugin['xep_0045'].invite(room, jid,
                        reason=reason or '')

        self.xmpp.plugin['xep_0030'].get_info(jid=jid, timeout=5,
                                              callback=callback)

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
                    body = condition or 'Unknown error'
            else:
                if code in ERROR_AND_STATUS_CODES:
                    body = ERROR_AND_STATUS_CODES[code]
                else:
                    body = condition or 'Unknown error'
        if code:
            message = '%(from)s: %(code)s - %(msg)s: %(body)s' % {
                      'from': sender, 'msg': msg, 'body': body, 'code': code}
        else:
            message = '%(from)s: %(msg)s: %(body)s' % {
                      'from': sender, 'msg': msg, 'body': body}
        return message


####################### Tab logic-related things ##############################

    ### Tab getters ###

    def get_tabs(self, cls=tabs.Tab):
        "Get all the tabs of a type"
        return filter(lambda tab: isinstance(tab, cls), self.tabs)

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
        # We first check if we have a static conversation opened
        # with this precise resource
        conversation = self.get_tab_by_name(jid.full,
                                            tabs.StaticConversationTab)
        if jid.bare == jid.full and not conversation:
            conversation = self.get_tab_by_name(jid.full,
                                                tabs.DynamicConversationTab)

        if not conversation and fallback_barejid:
            # If not, we search for a conversation with the bare jid
            conversation = self.get_tab_by_name(jid.bare,
                                                tabs.DynamicConversationTab)
            if not conversation:
                if create:
                    # We create a dynamic conversation with the bare Jid if
                    # nothing was found (and we lock it to the resource
                    # later)
                    conversation = self.open_conversation_window(jid.bare,
                                                                 False)
                else:
                    conversation = None
        return conversation

    def get_tab_by_name(self, name, typ=None):
        """
        Get the tab with the given name.
        If typ is provided, return a tab of this type only
        """
        for tab in self.tabs:
            if tab.name == name:
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
                old_tab = self.tabs[old_pos]
                self.tabs[new_pos], self.tabs[old_pos] = old_tab, tabs.GapTab()
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
        elif new_pos == old_pos:
            return False
        elif not self.tabs[old_pos]:
            return False
        if config.get('create_gaps'):
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
        def read_next_digit(digit):
            try:
                nb = int(digit)
            except ValueError:
                # If it is not a number, we do nothing. If it was the first
                # one, we do not wait for a second one by re-setting the
                # callback
                self.room_number_jump.clear()
            else:
                self.room_number_jump.append(digit)
                if len(self.room_number_jump) == 2:
                    arg = "".join(self.room_number_jump)
                    self.room_number_jump.clear()
                    self.command_win(arg)
                else:
                    # We need to read more digits
                    keyboard.continuation_keys_callback = read_next_digit
        keyboard.continuation_keys_callback = read_next_digit

    def go_to_roster(self):
        "Select the roster as the current tab"
        self.command_win('0')

    def go_to_previous_tab(self):
        "Go to the previous tab"
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
        states = sorted(tab_refs.keys(),
                        key=(lambda x: priority.get(x, 0)),
                        reverse=True)
        states = [state for state in states if priority.get(state, -1) >= 0]

        for state in states:
            for tab in tab_refs[state]:
                if (tab.nb < self.current_tab_nb and
                    tab_refs[state][-1].nb > self.current_tab_nb):
                    continue
                self.command_win('%s' % tab.nb)
                return
        return

    def focus_tab_named(self, tab_name, type_=None):
        """Returns True if it found a tab to focus on"""
        for tab in self.tabs:
            if tab.name == tab_name:
                if (type_ and (isinstance(tab, type_))) or not type_:
                    self.command_win('%s' % (tab.nb,))
                return True
        return False

    @property
    def current_tab_nb(self):
        """Wrapper for the current tab number"""
        return self._current_tab_nb

    @current_tab_nb.setter
    def current_tab_nb(self, value):
        """
        Prevents the tab number from going over the total number of opened
        tabs, or under 0
        """
        old = self._current_tab_nb
        if value >= len(self.tabs):
            self._current_tab_nb = 0
        elif value < 0:
            self._current_tab_nb = len(self.tabs) - 1
        else:
            self._current_tab_nb = value
        if old != self._current_tab_nb and self.tabs[self._current_tab_nb]:
            self.events.trigger('tab_change', old, self._current_tab_nb)

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
        # if the room exists, focus it and return
        for tab in self.get_tabs(tabs.PrivateTab):
            if tab.name == complete_jid:
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

    def open_new_room(self, room, nick, *, password=None, focus=True):
        """
        Open a new tab.MucTab containing a muc Room, using the specified nick
        """
        new_tab = tabs.MucTab(room, nick, password=password)
        self.add_tab(new_tab, focus)
        self.refresh_window()

    def open_new_form(self, form, on_cancel, on_send, **kwargs):
        """
        Open a new tab containing the form
        The callback are called with the completed form as parameter in
        addition with kwargs
        """
        form_tab = tabs.DataFormsTab(form, on_cancel, on_send, kwargs)
        self.add_tab(form_tab, True)

    ### Modifying actions ###

    def rename_private_tabs(self, room_name, old_nick, new_nick):
        """
        Call this method when someone changes his/her nick in a MUC,
        this updates the name of all the opened private conversations
        with him/her
        """
        tab = self.get_tab_by_name('%s/%s' % (room_name, old_nick),
                                   tabs.PrivateTab)
        if tab:
            tab.rename_user(old_nick, new_nick)

    def on_user_left_private_conversation(self, room_name, nick, status_message):
        """
        The user left the MUC: add a message in the associated
        private conversation
        """
        tab = self.get_tab_by_name('%s/%s' % (room_name, nick), tabs.PrivateTab)
        if tab:
            tab.user_left(status_message, nick)

    def on_user_rejoined_private_conversation(self, room_name, nick):
        """
        The user joined a MUC: add a message in the associated
        private conversation
        """
        tab = self.get_tab_by_name('%s/%s' % (room_name, nick), tabs.PrivateTab)
        if tab:
            tab.user_rejoined(nick)

    def disable_private_tabs(self, room_name, reason=None):
        """
        Disable private tabs when leaving a room
        """
        if reason is None:
            reason = '\x195}You left the chatroom\x193}'
        for tab in self.get_tabs(tabs.PrivateTab):
            if tab.name.startswith(room_name):
                tab.deactivate(reason=reason)

    def enable_private_tabs(self, room_name, reason=None):
        """
        Enable private tabs when joining a room
        """
        if reason is None:
            reason = '\x195}You joined the chatroom\x193}'
        for tab in self.get_tabs(tabs.PrivateTab):
            if tab.name.startswith(room_name):
                tab.activate(reason=reason)

    def on_user_changed_status_in_private(self, jid, msg):
        tab = self.get_tab_by_name(jid, tabs.ChatTab)
        if tab: # display the message in private
            tab.add_message(msg, typ=2)

    def close_tab(self, tab=None):
        """
        Close the given tab. If None, close the current one
        """
        was_current = tab is None
        tab = tab or self.current_tab()
        if isinstance(tab, tabs.RosterInfoTab):
            return              # The tab 0 should NEVER be closed
        del tab.key_func      # Remove self references
        del tab.commands      # and make the object collectable
        tab.on_close()
        nb = tab.nb
        if was_current:
            if self.previous_tab_nb != nb:
                self.current_tab_nb = self.previous_tab_nb
                self.previous_tab_nb = 0
        if config.get('create_gaps'):
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
        if tab and tab.name in logger.fds:
            logger.fds[tab.name].close()
            log.debug("Log file for %s closed.", tab.name)
            del logger.fds[tab.name]
        if self.current_tab_nb >= len(self.tabs):
            self.current_tab_nb = len(self.tabs) - 1
        while not self.tabs[self.current_tab_nb]:
            self.current_tab_nb -= 1
        if was_current:
            self.current_tab().on_gain_focus()
        self.refresh_window()
        import gc
        gc.collect()
        log.debug('___ Referrers of closing tab:\n%s\n______',
                  gc.get_referrers(tab))
        del tab

    def add_information_message_to_conversation_tab(self, jid, msg):
        """
        Search for a ConversationTab with the given jid (full or bare),
        if yes, add the given message to it
        """
        tab = self.get_tab_by_name(jid, tabs.ConversationTab)
        if tab:
            tab.add_message(msg, typ=2)
            if self.current_tab() is tab:
                self.refresh_window()


####################### Curses and ui-related stuff ###########################

    def doupdate(self):
        "Do a curses update"
        if not self.running:
            return
        curses.doupdate()

    def information(self, msg, typ=''):
        """
        Displays an informational message in the "Info" buffer
        """
        filter_messages = config.get('filter_info_messages').split(':')
        for words in filter_messages:
            if words and words in msg:
                log.debug('Did not show the message:\n\t%s> %s', typ, msg)
                return False
        colors = get_theme().INFO_COLORS
        color = colors.get(typ.lower(), colors.get('default', None))
        nb_lines = self.information_buffer.add_message(msg,
                                                       nickname=typ,
                                                       nick_color=color)
        popup_on = config.get('information_buffer_popup_on').split()
        if isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.refresh_window()
        elif typ != '' and typ.lower() in popup_on:
            popup_time = config.get('popup_time') + (nb_lines - 1) * 2
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
        nocursor = curses.curs_set(0)
        self.current_tab().state = 'current'
        self.current_tab().refresh()
        self.doupdate()
        curses.curs_set(nocursor)

    def refresh_tab_win(self):
        """
        Refresh the window containing the tab list
        """
        self.current_tab().refresh_tab_win()
        self.refresh_input()
        self.doupdate()

    def refresh_input(self):
        """
        Refresh the input if it exists
        """
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
        """
        Expand the information win a number of lines
        """
        if self.information_win_size >= self.current_tab().height -5 or \
                self.information_win_size+nb >= self.current_tab().height-4 or\
                self.size.core_degrade_y:
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
        """
        Reduce the size of the information win
        """
        if self.information_win_size == 0 or self.size.core_degrade_y:
            return
        self.information_win_size -= nb
        if self.information_win_size < 0:
            self.information_win_size = 0
        self.resize_global_information_win()
        for tab in self.tabs:
            tab.on_info_win_size_changed()
        self.refresh_window()

    def scroll_info_up(self):
        """
        Scroll the information buffer up
        """
        self.information_win.scroll_up(self.information_win.height)
        if not isinstance(self.current_tab(), tabs.RosterInfoTab):
            self.information_win.refresh()
        else:
            info = self.current_tab().information_win
            info.scroll_up(info.height)
            self.refresh_window()

    def scroll_info_down(self):
        """
        Scroll the information buffer down
        """
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
        timed_event = timed_events.DelayedEvent(time,
                        self.shrink_information_win,
                        result)
        self.add_timed_event(timed_event)
        self.refresh_window()

    def toggle_left_pane(self):
        """
        Enable/disable the left panel.
        """
        enabled = config.get('enable_vertical_tab_list')
        if not config.silent_set('enable_vertical_tab_list', str(not enabled)):
            self.information('Unable to write in the config file', 'Error')
        self.call_for_resize()

    def resize_global_information_win(self):
        """
        Resize the global_information_win only once at each resize.
        """
        if self.information_win_size > tabs.Tab.height - 6:
            self.information_win_size = tabs.Tab.height - 6
        if tabs.Tab.height < 6:
            self.information_win_size = 0
        height = (tabs.Tab.height - 1 - self.information_win_size
                        - tabs.Tab.tab_win_height())
        self.information_win.resize(self.information_win_size,
                                    tabs.Tab.width,
                                    height,
                                    0)

    def resize_global_info_bar(self):
        """
        Resize the GlobalInfoBar only once at each resize
        """
        height, width = self.stdscr.getmaxyx()
        if config.get('enable_vertical_tab_list'):

            if self.size.core_degrade_x:
                return
            try:
                height, _ = self.stdscr.getmaxyx()
                truncated_win = self.stdscr.subwin(height,
                        config.get('vertical_tab_list_size'),
                        0, 0)
            except:
                log.error('Curses error on infobar resize', exc_info=True)
                return
            self.left_tab_win = windows.VerticalGlobalInfoBar(truncated_win)
        elif not self.size.core_degrade_y:
                self.tab_win.resize(1, tabs.Tab.width,
                                    tabs.Tab.height - 2, 0)
                self.left_tab_win = None

    def add_message_to_text_buffer(self, buff, txt,
                                   time=None, nickname=None, history=None):
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
        # window to each Tab class, so they draw themself in the portion of
        # the screen that they can occupy, and we draw the tab list on the
        # remaining space, on the left
        height, width = self.stdscr.getmaxyx()
        if (config.get('enable_vertical_tab_list') and
                not self.size.core_degrade_x):
            try:
                scr = self.stdscr.subwin(0,
                        config.get('vertical_tab_list_size'))
            except:
                log.error('Curses error on resize', exc_info=True)
                return
        else:
            scr = self.stdscr
        tabs.Tab.resize(scr)
        self.resize_global_info_bar()
        self.resize_global_information_win()
        for tab in self.tabs:
            if config.get('lazy_resize'):
                tab.need_resize = True
            else:
                tab.resize()
        if self.tabs:
            self.full_screen_redraw()

    def read_keyboard(self):
        """
        Get the next keyboard key pressed and returns it.  It blocks until
        something can be read on stdin, this function must be called only if
        there is something to read. No timeout ever occurs.
        """
        return self.keyboard.get_user_input(self.stdscr)

    def escape_next_key(self):
        """
        Tell the Keyboard object that the next key pressed by the user
        should be escaped. See Keyboard.get_user_input
        """
        self.keyboard.escape_next_key()

####################### Commands and completions ##############################

    def register_command(self, name, func, **kwargs):
        """
        Add a command
        """
        desc = kwargs.get('desc', '')
        shortdesc = kwargs.get('shortdesc', '')
        completion = kwargs.get('completion')
        usage = kwargs.get('usage', '')
        if name in self.commands:
            return
        if not desc and shortdesc:
            desc = shortdesc
        self.commands[name] = Command(func, desc, completion, shortdesc, usage)

    def register_initial_commands(self):
        """
        Register the commands when poezio starts
        """
        self.register_command('help', self.command_help,
                usage='[command]',
                shortdesc='\\_o< KOIN KOIN KOIN',
                completion=self.completion_help)
        self.register_command('join', self.command_join,
                usage="[room_name][@server][/nick] [password]",
                desc="Join the specified room. You can specify a nickname "
                     "after a slash (/). If no nickname is specified, you will"
                     " use the default_nick in the configuration file. You can"
                     " omit the room name: you will then join the room you\'re"
                     " looking at (useful if you were kicked). You can also "
                     "provide a room_name without specifying a server, the "
                     "server of the room you're currently in will be used. You"
                     " can also provide a password to join the room.\nExamples"
                     ":\n/join room@server.tld\n/join room@server.tld/John\n"
                     "/join room2\n/join /me_again\n/join\n/join room@server"
                     ".tld/my_nick password\n/join / password",
                shortdesc='Join a room',
                completion=self.completion_join)
        self.register_command('exit', self.command_quit,
                desc='Just disconnect from the server and exit poezio.',
                shortdesc='Exit poezio.')
        self.register_command('quit', self.command_quit,
                desc='Just disconnect from the server and exit poezio.',
                shortdesc='Exit poezio.')
        self.register_command('next', self.rotate_rooms_right,
                shortdesc='Go to the next room.')
        self.register_command('prev', self.rotate_rooms_left,
                shortdesc='Go to the previous room.')
        self.register_command('win', self.command_win,
                usage='<number or name>',
                shortdesc='Go to the specified room',
                completion=self.completion_win)
        self.commands['w'] = self.commands['win']
        self.register_command('move_tab', self.command_move_tab,
                usage='<source> <destination>',
                desc="Insert the <source> tab at the position of "
                     "<destination>. This will make the following tabs shift in"
                     " some cases (refer to the documentation). A tab can be "
                     "designated by its number or by the beginning of its "
                     "address. You can use \".\" as a shortcut for the current "
                     "tab.",
                shortdesc='Move a tab.',
                completion=self.completion_move_tab)
        self.register_command('destroy_room', self.command_destroy_room,
                usage='[room JID]',
                desc='Try to destroy the room [room JID], or the current'
                     ' tab if it is a multi-user chat and [room JID] is '
                     'not given.',
                shortdesc='Destroy a room.',
                completion=None)
        self.register_command('show', self.command_status,
                usage='<availability> [status message]',
                desc="Sets your availability and (optionally) your status "
                     "message. The <availability> argument is one of \"available"
                     ", chat, away, afk, dnd, busy, xa\" and the optional "
                     "[status message] argument will be your status message.",
                shortdesc='Change your availability.',
                completion=self.completion_status)
        self.commands['status'] = self.commands['show']
        self.register_command('bookmark_local', self.command_bookmark_local,
                usage="[roomname][/nick] [password]",
                desc="Bookmark Local: Bookmark locally the specified room "
                     "(you will then auto-join it on each poezio start). This"
                     " commands uses almost the same syntaxe as /join. Type "
                     "/help join for syntax examples. Note that when typing "
                     "\"/bookmark\" on its own, the room will be bookmarked "
                     "with the nickname you\'re currently using in this room "
                     "(instead of default_nick)",
                shortdesc='Bookmark a room locally.',
                completion=self.completion_bookmark_local)
        self.register_command('bookmark', self.command_bookmark,
                usage="[roomname][/nick] [autojoin] [password]",
                desc="Bookmark: Bookmark online the specified room (you "
                     "will then auto-join it on each poezio start if autojoin"
                     " is specified and is 'true'). This commands uses almost"
                     " the same syntax as /join. Type /help join for syntax "
                     "examples. Note that when typing \"/bookmark\" alone, the"
                     " room will be bookmarked with the nickname you\'re "
                     "currently using in this room (instead of default_nick).",
                shortdesc="Bookmark a room online.",
                completion=self.completion_bookmark)
        self.register_command('set', self.command_set,
                usage="[plugin|][section] <option> [value]",
                desc="Set the value of an option in your configuration file."
                     " You can, for example, change your default nickname by "
                     "doing `/set default_nick toto` or your resource with `/set"
                     " resource blabla`. You can also set options in specific "
                     "sections with `/set bindings M-i ^i` or in specific plugin"
                     " with `/set mpd_client| host 127.0.0.1`. `toggle` can be "
                     "used as a special value to toggle a boolean option.",
                shortdesc="Set the value of an option",
                completion=self.completion_set)
        self.register_command('set_default', self.command_set_default,
                usage="[section] <option>",
                desc="Set the default value of an option. For example, "
                     "`/set_default resource` will reset the resource "
                     "option. You can also reset options in specific "
                     "sections by doing `/set_default section option`.",
                shortdesc="Set the default value of an option",
                completion=self.completion_set_default)
        self.register_command('toggle', self.command_toggle,
                usage='<option>',
                desc='Shortcut for /set <option> toggle',
                shortdesc='Toggle an option',
                completion=self.completion_toggle)
        self.register_command('theme', self.command_theme,
                usage='[theme name]',
                desc="Reload the theme defined in the config file. If theme"
                     "_name is provided, set that theme before reloading it.",
                shortdesc='Load a theme',
                completion=self.completion_theme)
        self.register_command('list', self.command_list,
                usage='[server]',
                desc="Get the list of public chatrooms"
                     " on the specified server.",
                shortdesc='List the rooms.',
                completion=self.completion_list)
        self.register_command('message', self.command_message,
                usage='<jid> [optional message]',
                desc="Open a conversation with the specified JID (even if it"
                     " is not in our roster), and send a message to it, if the "
                     "message is specified.",
                shortdesc='Send a message',
                completion=self.completion_message)
        self.register_command('version', self.command_version,
                usage='<jid>',
                desc="Get the software version of the given JID (usually its"
                     " XMPP client and Operating System).",
                shortdesc='Get the software version of a JID.',
                completion=self.completion_version)
        self.register_command('server_cycle', self.command_server_cycle,
                usage='[domain] [message]',
                desc='Disconnect and reconnect in all the rooms in domain.',
                shortdesc='Cycle a range of rooms',
                completion=self.completion_server_cycle)
        self.register_command('bind', self.command_bind,
                usage='<key> <equ>',
                desc="Bind a key to another key or to a “command”. For "
                     "example \"/bind ^H KEY_UP\" makes Control + h do the"
                     " same same as the Up key.",
                completion=self.completion_bind,
                shortdesc='Bind a key to another key.')
        self.register_command('load', self.command_load,
                usage='<plugin> [<otherplugin> …]',
                shortdesc='Load the specified plugin(s)',
                completion=self.plugin_manager.completion_load)
        self.register_command('unload', self.command_unload,
                usage='<plugin> [<otherplugin> …]',
                shortdesc='Unload the specified plugin(s)',
                completion=self.plugin_manager.completion_unload)
        self.register_command('plugins', self.command_plugins,
                shortdesc='Show the plugins in use.')
        self.register_command('presence', self.command_presence,
                usage='<JID> [type] [status]',
                desc="Send a directed presence to <JID> and using"
                     " [type] and [status] if provided.",
                shortdesc='Send a directed presence.',
                completion=self.completion_presence)
        self.register_command('rawxml', self.command_rawxml,
                usage='<xml>',
                shortdesc='Send a custom xml stanza.')
        self.register_command('invite', self.command_invite,
                usage='<jid> <room> [reason]',
                desc='Invite jid in room with reason.',
                shortdesc='Invite someone in a room.',
                completion=self.completion_invite)
        self.register_command('invitations', self.command_invitations,
                shortdesc='Show the pending invitations.')
        self.register_command('bookmarks', self.command_bookmarks,
                shortdesc='Show the current bookmarks.')
        self.register_command('remove_bookmark', self.command_remove_bookmark,
                usage='[jid]',
                desc="Remove the specified bookmark, or the "
                     "bookmark on the current tab, if any.",
                shortdesc='Remove a bookmark',
                completion=self.completion_remove_bookmark)
        self.register_command('xml_tab', self.command_xml_tab,
                shortdesc='Open an XML tab.')
        self.register_command('runkey', self.command_runkey,
                usage='<key>',
                shortdesc='Execute the action defined for <key>.',
                completion=self.completion_runkey)
        self.register_command('self', self.command_self,
                shortdesc='Remind you of who you are.')
        self.register_command('last_activity', self.command_last_activity,
                usage='<jid>',
                desc='Informs you of the last activity of a JID.',
                shortdesc='Get the activity of someone.',
                completion=self.completion_last_activity)
        self.register_command('ad-hoc', self.command_adhoc,
                usage='<jid>',
                shortdesc='List available ad-hoc commands on the given jid')
        self.register_command('reload', self.command_reload,
                shortdesc='Reload the config. You can achieve the same by '
                          'sending SIGUSR1 to poezio.')

        if config.get('enable_user_activity'):
            self.register_command('activity', self.command_activity,
                    usage='[<general> [specific] [text]]',
                    desc='Send your current activity to your contacts '
                         '(use the completion). Nothing means '
                         '"stop broadcasting an activity".',
                    shortdesc='Send your activity.',
                    completion=self.completion_activity)
        if config.get('enable_user_mood'):
            self.register_command('mood', self.command_mood,
                    usage='[<mood> [text]]',
                    desc='Send your current mood to your contacts '
                         '(use the completion). Nothing means '
                         '"stop broadcasting a mood".',
                    shortdesc='Send your mood.',
                    completion=self.completion_mood)
        if config.get('enable_user_gaming'):
            self.register_command('gaming', self.command_gaming,
                    usage='[<game name> [server address]]',
                    desc='Send your current gaming activity to '
                         'your contacts. Nothing means "stop '
                         'broadcasting a gaming activity".',
                    shortdesc='Send your gaming activity.',
                    completion=None)

####################### XMPP Event Handlers  ##################################
    on_session_start_features = handlers.on_session_start_features
    on_carbon_received = handlers.on_carbon_received
    on_carbon_sent = handlers.on_carbon_sent
    on_groupchat_invitation = handlers.on_groupchat_invitation
    on_groupchat_direct_invitation = handlers.on_groupchat_direct_invitation
    on_groupchat_decline = handlers.on_groupchat_decline
    on_message = handlers.on_message
    on_error_message = handlers.on_error_message
    on_normal_message = handlers.on_normal_message
    on_nick_received = handlers.on_nick_received
    on_gaming_event = handlers.on_gaming_event
    on_mood_event = handlers.on_mood_event
    on_activity_event = handlers.on_activity_event
    on_tune_event = handlers.on_tune_event
    on_groupchat_message = handlers.on_groupchat_message
    on_muc_own_nickchange = handlers.on_muc_own_nickchange
    on_groupchat_private_message = handlers.on_groupchat_private_message
    on_chatstate_active = handlers.on_chatstate_active
    on_chatstate_inactive = handlers.on_chatstate_inactive
    on_chatstate_composing = handlers.on_chatstate_composing
    on_chatstate_paused = handlers.on_chatstate_paused
    on_chatstate_gone = handlers.on_chatstate_gone
    on_chatstate = handlers.on_chatstate
    on_chatstate_normal_conversation = handlers.on_chatstate_normal_conversation
    on_chatstate_private_conversation = \
            handlers.on_chatstate_private_conversation
    on_chatstate_groupchat_conversation = \
            handlers.on_chatstate_groupchat_conversation
    on_roster_update = handlers.on_roster_update
    on_subscription_request = handlers.on_subscription_request
    on_subscription_authorized = handlers.on_subscription_authorized
    on_subscription_remove = handlers.on_subscription_remove
    on_subscription_removed = handlers.on_subscription_removed
    on_presence = handlers.on_presence
    on_presence_error = handlers.on_presence_error
    on_got_offline = handlers.on_got_offline
    on_got_online = handlers.on_got_online
    on_groupchat_presence = handlers.on_groupchat_presence
    on_failed_connection = handlers.on_failed_connection
    on_disconnected = handlers.on_disconnected
    on_stream_error = handlers.on_stream_error
    on_failed_all_auth = handlers.on_failed_all_auth
    on_no_auth = handlers.on_no_auth
    on_connected = handlers.on_connected
    on_connecting = handlers.on_connecting
    on_session_start = handlers.on_session_start
    on_status_codes = handlers.on_status_codes
    on_groupchat_subject = handlers.on_groupchat_subject
    on_data_form = handlers.on_data_form
    on_receipt = handlers.on_receipt
    on_attention = handlers.on_attention
    room_error = handlers.room_error
    check_bookmark_storage = handlers.check_bookmark_storage
    outgoing_stanza = handlers.outgoing_stanza
    incoming_stanza = handlers.incoming_stanza
    validate_ssl = handlers.validate_ssl
    ssl_invalid_chain = handlers.ssl_invalid_chain
    on_next_adhoc_step = handlers.on_next_adhoc_step
    on_adhoc_error = handlers.on_adhoc_error
    cancel_adhoc_command = handlers.cancel_adhoc_command
    validate_adhoc_step = handlers.validate_adhoc_step
    terminate_adhoc_command = handlers.terminate_adhoc_command
    command_help = commands.command_help
    command_runkey = commands.command_runkey
    command_status = commands.command_status
    command_presence = commands.command_presence
    command_theme = commands.command_theme
    command_win = commands.command_win
    command_move_tab = commands.command_move_tab
    command_list = commands.command_list
    command_version = commands.command_version
    command_join = commands.command_join
    command_bookmark_local = commands.command_bookmark_local
    command_bookmark = commands.command_bookmark
    command_bookmarks = commands.command_bookmarks
    command_destroy_room = commands.command_destroy_room
    command_remove_bookmark = commands.command_remove_bookmark
    command_set = commands.command_set
    command_set_default = commands.command_set_default
    command_toggle = commands.command_toggle
    command_server_cycle = commands.command_server_cycle
    command_last_activity = commands.command_last_activity
    command_mood = commands.command_mood
    command_activity = commands.command_activity
    command_gaming = commands.command_gaming
    command_invite = commands.command_invite
    command_decline = commands.command_decline
    command_invitations = commands.command_invitations
    command_quit = commands.command_quit
    command_bind = commands.command_bind
    command_rawxml = commands.command_rawxml
    command_load = commands.command_load
    command_unload = commands.command_unload
    command_plugins = commands.command_plugins
    command_message = commands.command_message
    command_xml_tab = commands.command_xml_tab
    command_adhoc = commands.command_adhoc
    command_self = commands.command_self
    command_reload = commands.command_reload
    completion_help = completions.completion_help
    completion_status = completions.completion_status
    completion_presence = completions.completion_presence
    completion_theme = completions.completion_theme
    completion_win = completions.completion_win
    completion_join = completions.completion_join
    completion_version = completions.completion_version
    completion_list = completions.completion_list
    completion_move_tab = completions.completion_move_tab
    completion_runkey = completions.completion_runkey
    completion_bookmark = completions.completion_bookmark
    completion_remove_bookmark = completions.completion_remove_bookmark
    completion_decline = completions.completion_decline
    completion_bind = completions.completion_bind
    completion_message = completions.completion_message
    completion_invite = completions.completion_invite
    completion_activity = completions.completion_activity
    completion_mood = completions.completion_mood
    completion_last_activity = completions.completion_last_activity
    completion_server_cycle = completions.completion_server_cycle
    completion_set = completions.completion_set
    completion_set_default = completions.completion_set_default
    completion_toggle = completions.completion_toggle
    completion_bookmark_local = completions.completion_bookmark_local



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
    """
    Replace an inputted key with the one defined as its replacement
    in the config
    """
    bind = config.get(key, default=key, section='bindings')
    if not bind:
        bind = key
    return bind


