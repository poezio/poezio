# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
a Tab object is a way to organize various Windows (see windows.py)
around the screen at once.
A tab is then composed of multiple Buffers.
Each Tab object has different refresh() and resize() methods, defining how its
Windows are displayed, resized, etc.
"""

MIN_WIDTH = 42
MIN_HEIGHT = 6

import logging
log = logging.getLogger(__name__)

from gettext import gettext as _

import windows
import curses
import difflib
import string
import common
import core
import singleton
import random
import xhtml
import weakref
import timed_events
import os
import time

import multiuserchat as muc

from theming import get_theme

from common import safeJID
from decorators import refresh_wrapper
from sleekxmpp import JID, InvalidJID
from sleekxmpp.xmlstream import matcher
from sleekxmpp.xmlstream.handler import Callback
from config import config
from roster import RosterGroup, roster
from contact import Contact, Resource
from text_buffer import TextBuffer
from user import User
from os import getenv, path
from logger import logger

from datetime import datetime, timedelta
from xml.etree import cElementTree as ET

SHOW_NAME = {
    'dnd': _('busy'),
    'away': _('away'),
    'xa': _('not available'),
    'chat': _('chatty'),
    '': _('available')
    }

NS_MUC_USER = 'http://jabber.org/protocol/muc#user'

STATE_COLORS = {
        'disconnected': lambda: get_theme().COLOR_TAB_DISCONNECTED,
        'joined': lambda: get_theme().COLOR_TAB_JOINED,
        'message': lambda: get_theme().COLOR_TAB_NEW_MESSAGE,
        'highlight': lambda: get_theme().COLOR_TAB_HIGHLIGHT,
        'private': lambda: get_theme().COLOR_TAB_PRIVATE,
        'normal': lambda: get_theme().COLOR_TAB_NORMAL,
        'current': lambda: get_theme().COLOR_TAB_CURRENT,
        'attention': lambda: get_theme().COLOR_TAB_ATTENTION,
    }

VERTICAL_STATE_COLORS = {
        'disconnected': lambda: get_theme().COLOR_VERTICAL_TAB_DISCONNECTED,
        'joined': lambda: get_theme().COLOR_VERTICAL_TAB_JOINED,
        'message': lambda: get_theme().COLOR_VERTICAL_TAB_NEW_MESSAGE,
        'highlight': lambda: get_theme().COLOR_VERTICAL_TAB_HIGHLIGHT,
        'private': lambda: get_theme().COLOR_VERTICAL_TAB_PRIVATE,
        'normal': lambda: get_theme().COLOR_VERTICAL_TAB_NORMAL,
        'current': lambda: get_theme().COLOR_VERTICAL_TAB_CURRENT,
        'attention': lambda: get_theme().COLOR_VERTICAL_TAB_ATTENTION,
    }


STATE_PRIORITY = {
        'normal': -1,
        'current': -1,
        'disconnected': 0,
        'message': 1,
        'joined': 1,
        'highlight': 2,
        'private': 2,
        'attention': 3
    }

class Tab(object):
    tab_core = None
    def __init__(self):
        self.input = None
        if isinstance(self, MucTab) and not self.joined:
            self._state = 'disconnected'
        else:
            self._state = 'normal'

        self.need_resize = False
        self.need_resize = False
        self.key_func = {}      # each tab should add their keys in there
                                # and use them in on_input
        self.commands = {}      # and their own commands


    @property
    def core(self):
        if not Tab.tab_core:
            Tab.tab_core = singleton.Singleton(core.Core)
        return Tab.tab_core

    @property
    def nb(self):
        for index, tab in enumerate(self.core.tabs):
            log.debug("%s", tab.__class__)
            if tab == self:
                return index
        return len(self.core.tabs)

    @property
    def tab_win(self):
        if not Tab.tab_core:
            Tab.tab_core = singleton.Singleton(core.Core)
        return Tab.tab_core.tab_win

    @property
    def left_tab_win(self):
        if not Tab.tab_core:
            Tab.tab_core = singleton.Singleton(core.Core)
        return Tab.tab_core.left_tab_win

    @staticmethod
    def tab_win_height():
        """
        Returns 1 or 0, depending on if we are using the vertical tab list
        or not.
        """
        if config.get('enable_vertical_tab_list', 'false') == 'true':
            return 0
        return 1

    @property
    def info_win(self):
        return self.core.information_win

    @property
    def color(self):
        return STATE_COLORS[self._state]()

    @property
    def vertical_color(self):
        return VERTICAL_STATE_COLORS[self._state]()

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        if not value in STATE_COLORS:
            log.debug("Invalid value for tab state: %s", value)
        elif STATE_PRIORITY[value] < STATE_PRIORITY[self._state] and \
                value not in ('current', 'disconnected'):
            log.debug("Did not set state because of lower priority, asked: %s, kept: %s", value, self._state)
        elif self._state == 'disconnected' and value not in ('joined', 'current'):
            log.debug('Did not set state because disconnected tabs remain visible')
        else:
            self._state = value

    @staticmethod
    def resize(scr):
        Tab.size = (Tab.height, Tab.width) = scr.getmaxyx()
        if Tab.height < MIN_HEIGHT or Tab.width < MIN_WIDTH:
            Tab.visible = False
        else:
            Tab.visible = True
        windows.Win._tab_win = scr

    def complete_commands(self, the_input):
        """
        Does command completion on the specified input for both global and tab-specific
        commands.
        This should be called from the completion method (on tab, for example), passing
        the input where completion is to be made.
        It can completion the command name itself or an argument of the command.
        Returns True if a completion was made, False else.
        """
        txt = the_input.get_text()
        # check if this is a command
        if txt.startswith('/') and not txt.startswith('//'):
            # check if we are in the middle of the command name
            if len(txt.split()) > 1 or\
                    (txt.endswith(' ') and not the_input.last_completion):
                command_name = txt.split()[0][1:]
                if command_name in self.commands:
                    command = self.commands[command_name]
                elif command_name in self.core.commands:
                    command = self.core.commands[command_name]
                else:           # Unknown command, cannot complete
                    return False
                if command[2] is None:
                    return False # There's no completion function
                else:
                    return command[2](the_input)
            else:
                # complete the command's name
                words = ['/%s'% (name) for name in self.core.commands] +\
                    ['/%s' % (name) for name in self.commands]
                the_input.auto_completion(words, '', quotify=False)
                # Do not try to cycle command completion if there was only
                # one possibily. The next tab will complete the argument.
                # Otherwise we would need to add a useless space before being
                # able to complete the arguments.
                hit_copy = set(the_input.hit_list)
                while not hit_copy:
                    the_input.key_backspace()
                    the_input.auto_completion(words, '', quotify=False)
                    hit_copy = set(the_input.hit_list)
                if len(hit_copy) == 1:
                    the_input.do_command(' ')
                return True
        return False

    def execute_command(self, provided_text):
        """
        Execute the command in the input and return False if
        the input didn't contain a command
        """
        txt = provided_text or self.input.key_enter()
        if txt.startswith('/') and not txt.startswith('//') and\
                not txt.startswith('/me '):
            command = txt.strip().split()[0][1:]
            arg = txt[2+len(command):] # jump the '/' and the ' '
            func = None
            if command in self.commands: # check tab-specific commands
                func = self.commands[command][0]
            elif command in self.core.commands: # check global commands
                func = self.core.commands[command][0]
            else:
                low = command.lower()
                if low in self.commands:
                    func = self.commands[low][0]
                elif low in self.core.commands:
                    func = self.core.commands[low][0]
                else:
                    self.core.information(_("Unknown command (%s)") % (command), _('Error'))
            if command in ('correct', 'say'): # hack
                arg = xhtml.convert_simple_to_full_colors(arg)
            else:
                arg = xhtml.clean_text_simple(arg)
            if func:
                func(arg)
            return True
        else:
            return False

    def refresh_tab_win(self):
        if self.left_tab_win:
            self.left_tab_win.refresh()
        else:
            self.tab_win.refresh()

    def refresh(self):
        """
        Called on each screen refresh (when something has changed)
        """
        pass

    def get_name(self):
        """
        get the name of the tab
        """
        return self.__class__.__name__

    def get_nick(self):
        """
        Get the nick of the tab (defaults to its name)
        """
        return self.get_name()

    def get_text_window(self):
        """
        Returns the principal TextWin window, if there's one
        """
        return None

    def on_input(self, key, raw):
        """
        raw indicates if the key should activate the associated command or not.
        """
        pass

    def update_commands(self):
        for c in self.plugin_commands:
            if not c in self.commands:
                self.commands[c] = self.plugin_commands[c]

    def update_keys(self):
        for k in self.plugin_keys:
            if not k in self.key_func:
                self.key_func[k] = self.plugin_keys[k]

    def on_lose_focus(self):
        """
        called when this tab loses the focus.
        """
        self.state = 'normal'

    def on_gain_focus(self):
        """
        called when this tab gains the focus.
        """
        self.state = 'current'

    def on_scroll_down(self):
        """
        Defines what happens when we scroll down
        """
        pass

    def on_scroll_up(self):
        """
        Defines what happens when we scroll up
        """
        pass

    def on_line_up(self):
        """
        Defines what happens when we scroll one line up
        """
        pass

    def on_line_down(self):
        """
        Defines what happens when we scroll one line up
        """
        pass

    def on_half_scroll_down(self):
        """
        Defines what happens when we scroll half a screen down
        """
        pass

    def on_half_scroll_up(self):
        """
        Defines what happens when we scroll half a screen up
        """
        pass

    def on_info_win_size_changed(self):
        """
        Called when the window with the informations is resized
        """
        pass

    def on_close(self):
        """
        Called when the tab is to be closed
        """
        if self.input:
            self.input.on_delete()

    def matching_names(self):
        """
        Returns a list of strings that are used to name a tab with the /win
        command.  For example you could switch to a tab that returns
        ['hello', 'coucou'] using /win hel, or /win coucou
        If not implemented in the tab, it just doesn’t match with anything.
        """
        return []

    def __del__(self):
        log.debug('------ Closing tab %s', self.__class__.__name__)

class GapTab(Tab):

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def get_name(self):
        return ''

    def refresh(self):
        log.debug('WARNING: refresh() called on a gap tab, this should not happen')

class ChatTab(Tab):
    """
    A tab containing a chat of any type.
    Just use this class instead of Tab if the tab needs a recent-words completion
    Also, ^M is already bound to on_enter
    And also, add the /say command
    """
    plugin_commands = {}
    plugin_keys = {}
    def __init__(self, jid=''):
        Tab.__init__(self)
        self.name = jid
        self._text_buffer = TextBuffer()
        self.remote_wants_chatstates = None # change this to True or False when
        # we know that the remote user wants chatstates, or not.
        # None means we don’t know yet, and we send only "active" chatstates
        self.chatstate = None   # can be "active", "composing", "paused", "gone", "inactive"
        # We keep a weakref of the event that will set our chatstate to "paused", so that
        # we can delete it or change it if we need to
        self.timed_event_paused = None
        # if that’s None, then no paused chatstate was sent recently
        # if that’s a weakref returning None, then a paused chatstate was sent
        # since the last input
        self.remote_supports_attention = False
        # Keeps the last sent message to complete it easily in completion_correct, and to replace it.
        self.last_sent_message = None
        self.key_func['M-v'] = self.move_separator
        self.key_func['M-h'] = self.scroll_separator
        self.key_func['M-/'] = self.last_words_completion
        self.key_func['^M'] = self.on_enter
        self.commands['say'] =  (self.command_say,
                                 _("""Usage: /say <message>\nSay: Just send the message.
                                        Useful if you want your message to begin with a '/'."""), None)
        self.commands['xhtml'] =  (self.command_xhtml, _("Usage: /xhtml <custom xhtml>\nXHTML: Send custom XHTML."), None)
        self.commands['clear'] =  (self.command_clear,
                                 _('Usage: /clear\nClear: Clear the current buffer.'), None)
        self.commands['correct'] = (self.command_correct, _('Usage: /correct\nCorrect: Fix the last message with whatever you want.'), self.completion_correct)

        self.chat_state = None
        self.update_commands()
        self.update_keys()

        # Get the logs
        log_nb = config.get('load_log', 10)

        if isinstance(self, PrivateTab):
            logs = logger.get_logs(safeJID(self.get_name()).full.replace('/', '\\'), log_nb)
        else:
            logs = logger.get_logs(safeJID(self.get_name()).bare, log_nb)
        if logs:
            for log_line in logs:
                log_line = '\x19%s}%s' % (get_theme().COLOR_INFORMATION_TEXT[0], log_line)
                self._text_buffer.add_message(
                        txt=log_line.strip(),
                        time='',
                        nickname='',
                        user='',
                        str_time=''
                        )
    def log_message(self, txt, time, nickname):
        """
        Log the messages in the archives, if it needs
        to be
        """
        if time is None and self.joined:        # don't log the history messages
            logger.log_message(self.name, nickname, txt)

    def last_words_completion(self):
        """
        Complete the input with words recently said
        """
        # build the list of the recent words
        char_we_dont_want = string.punctuation+' ’„“”…«»'
        words = list()
        for msg in self._text_buffer.messages[:-40:-1]:
            if not msg:
                continue
            txt = xhtml.clean_text(msg.txt)
            for char in char_we_dont_want:
                txt = txt.replace(char, ' ')
            for word in txt.split():
                if len(word) >= 4 and word not in words:
                    words.append(word)
        words.extend([word for word in config.get('words', '').split(':') if word])
        self.input.auto_completion(words, ' ', quotify=False)

    def on_enter(self):
        txt = self.input.key_enter()
        if txt:
            if not self.execute_command(txt):
                if txt.startswith('//'):
                    txt = txt[1:]
                self.command_say(xhtml.convert_simple_to_full_colors(txt))
        self.cancel_paused_delay()

    def command_xhtml(self, arg):
        """"
        /xhtml <custom xhtml>
        """
        if not arg:
            return
        try:
            body = xhtml.clean_text(xhtml.xhtml_to_poezio_colors(arg))
            # The <body /> element is the only allowable child of the <xhtm-im>
            arg = "<body xmlns='http://www.w3.org/1999/xhtml'>%s</body>" % (arg,)
            ET.fromstring(arg)
        except:
            self.core.information('Could not send custom xhtml', 'Error')
            return

        msg = self.core.xmpp.make_message(self.get_name())
        msg['body'] = body
        msg['xhtml_im'] = arg
        if isinstance(self, MucTab):
            msg['type'] = 'groupchat'
        if isinstance(self, ConversationTab):
            self.core.add_message_to_text_buffer(self._text_buffer, body, None, self.core.own_nick)
            self.refresh()
        msg.send()

    @refresh_wrapper.always
    def command_clear(self, args):
        """
        /clear
        """
        self._text_buffer.messages = []
        self.text_win.rebuild_everything(self._text_buffer)

    def send_chat_state(self, state, always_send=False):
        """
        Send an empty chatstate message
        """
        if not isinstance(self, MucTab) or self.joined:
            if state in ('active', 'inactive', 'gone') and self.inactive and not always_send:
                return
            msg = self.core.xmpp.make_message(self.get_name())
            msg['type'] = self.message_type
            msg['chat_state'] = state
            self.chat_state = state
            msg.send()

    def send_composing_chat_state(self, empty_after):
        """
        Send the "active" or "composing" chatstate, depending
        on the the current status of the input
        """
        name = self.general_jid
        if config.get_by_tabname('send_chat_states', 'true', name, True) == 'true' and self.remote_wants_chatstates:
            needed = 'inactive' if self.inactive else 'active'
            self.cancel_paused_delay()
            if not empty_after:
                if self.chat_state != "composing":
                    self.send_chat_state("composing")
                self.set_paused_delay(True)
            elif empty_after and self.chat_state != needed:
                self.send_chat_state(needed, True)

    def set_paused_delay(self, composing):
        """
        we create a timed event that will put us to paused
        in a few seconds
        """
        if config.get_by_tabname('send_chat_states', 'true', self.general_jid, True) != 'true':
            return
        if self.timed_event_paused:
            # check the weakref
            event = self.timed_event_paused()
            if event:
                # the event already exists: we just update
                # its date
                event.change_date(datetime.now() + timedelta(seconds=4))
                return
        new_event = timed_events.DelayedEvent(4, self.send_chat_state, 'paused')
        self.core.add_timed_event(new_event)
        self.timed_event_paused = weakref.ref(new_event)

    def cancel_paused_delay(self):
        """
        Remove that event from the list and set it to None.
        Called for example when the input is emptied, or when the message
        is sent
        """
        if self.timed_event_paused:
            event = self.timed_event_paused()
            if event:
                self.core.remove_timed_event(event)
                del event
        self.timed_event_paused = None

    def command_correct(self, line):
        """
        /correct <fixed message>
        """
        if not line:
            self.core.command_help('correct')
            return
        if not self.last_sent_message:
            self.core.information(_('There is no message to correct.'))
            return
        self.command_say(line, correct=True)

    def completion_correct(self, the_input):
        return the_input.auto_completion([self.last_sent_message['body']], '', quotify=False)

    @property
    def inactive(self):
        """Whether we should send inactive or active as a chatstate"""
        return self.core.status.show in ('xa', 'away') or\
                (hasattr(self, 'directed_presence') and not self.directed_presence)

    def move_separator(self):
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        self.text_win.refresh()
        self.input.refresh()

    def get_conversation_messages(self):
        return self._text_buffer.messages

    def command_say(self, line, correct=False):
        pass

    def on_line_up(self):
        return self.text_win.scroll_up(1)

    def on_line_down(self):
        return self.text_win.scroll_down(1)

    def on_scroll_up(self):
        return self.text_win.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        return self.text_win.scroll_down(self.text_win.height-1)

    def on_half_scroll_up(self):
        return self.text_win.scroll_up((self.text_win.height-1) // 2)

    def on_half_scroll_down(self):
        return self.text_win.scroll_down((self.text_win.height-1) // 2)

    @refresh_wrapper.always
    def scroll_separator(self):
        self.text_win.scroll_to_separator()

class MucTab(ChatTab):
    """
    The tab containing a multi-user-chat room.
    It contains an userlist, an input, a topic, an information and a chat zone
    """
    message_type = 'groupchat'
    plugin_commands = {}
    plugin_keys = {}
    def __init__(self, jid, nick):
        self.joined = False
        ChatTab.__init__(self, jid)
        self.own_nick = nick
        self.name = jid
        self.users = []
        self.privates = [] # private conversations
        self.topic = ''
        self.remote_wants_chatstates = True
        # We send active, composing and paused states to the MUC because
        # the chatstate may or may not be filtered by the MUC,
        # that’s not our problem.
        self.topic_win = windows.Topic()
        self.text_win = windows.TextWin()
        self._text_buffer.add_window(self.text_win)
        self.v_separator = windows.VerticalSeparator()
        self.user_win = windows.UserList()
        self.info_header = windows.MucInfoWin()
        self.input = windows.MessageInput()
        self.ignores = []       # set of Users
        # keys
        self.key_func['^I'] = self.completion
        self.key_func['M-u'] = self.scroll_user_list_down
        self.key_func['M-y'] = self.scroll_user_list_up
        self.key_func['M-n'] = self.go_to_next_hl
        self.key_func['M-p'] = self.go_to_prev_hl
        # commands
        self.commands['ignore'] = (self.command_ignore, _("Usage: /ignore <nickname> \nIgnore: Ignore a specified nickname."), self.completion_ignore)
        self.commands['unignore'] = (self.command_unignore, _("Usage: /unignore <nickname>\nUnignore: Remove the specified nickname from the ignore list."), self.completion_unignore)
        self.commands['kick'] =  (self.command_kick, _("Usage: /kick <nick> [reason]\nKick: Kick the user with the specified nickname. You also can give an optional reason."), self.completion_quoted)
        self.commands['ban'] =  (self.command_ban, _("Usage: /ban <nick> [reason]\nBan: ban the user with the specified nickname. You also can give an optional reason."), self.completion_quoted)
        self.commands['role'] =  (self.command_role, _("Usage: /role <nick> <role> [reason]\nRole: Set the role of an user. Roles can be: none, visitor, participant, moderator. You also can give an optional reason."), self.completion_role)
        self.commands['affiliation'] =  (self.command_affiliation, _("Usage: /affiliation <nick or jid> <affiliation>\nAffiliation: Set the affiliation of an user. Affiliations can be: outcast, none, member, admin, owner."), self.completion_affiliation)
        self.commands['topic'] = (self.command_topic, _("Usage: /topic <subject>\nTopic: Change the subject of the room."), self.completion_topic)
        self.commands['query'] = (self.command_query, _('Usage: /query <nick> [message]\nQuery: Open a private conversation with <nick>. This nick has to be present in the room you\'re currently in. If you specified a message after the nickname, it will immediately be sent to this user.'), self.completion_quoted)
        self.commands['part'] = (self.command_part, _("Usage: /part [message]\nPart: Disconnect from a room. You can specify an optional message."), None)
        self.commands['close'] = (self.command_close, _("Usage: /close [message]\nClose: Disconnect from a room and close the tab. You can specify an optional message if you are still connected."), None)
        self.commands['nick'] = (self.command_nick, _("Usage: /nick <nickname>\nNick: Change your nickname in the current room."), self.completion_nick)
        self.commands['recolor'] = (self.command_recolor, _('Usage: /recolor\nRecolor: Re-assign a color to all participants of the current room, based on the last time they talked. Use this if the participants currently talking have too many identical colors.'), self.completion_recolor)
        self.commands['cycle'] = (self.command_cycle, _('Usage: /cycle [message]\nCycle: Leave the current room and rejoin it immediately.'), None)
        self.commands['info'] = (self.command_info, _('Usage: /info <nickname>\nInfo: Display some information about the user in the MUC: its/his/her role, affiliation, status and status message.'), self.completion_info)
        self.commands['configure'] = (self.command_configure, _('Usage: /configure\nConfigure: Configure the current room, through a form.'), None)
        self.commands['version'] = (self.command_version, _('Usage: /version <jid or nick>\nVersion: Get the software version of the given JID or nick in room (usually its XMPP client and Operating System).'), self.completion_version)
        self.commands['names'] = (self.command_names, _('Usage: /names\nNames: Get the list of the users in the room, and the list of the people assuming the different roles.'), None)

        if self.core.xmpp.boundjid.server == "gmail.com": #gmail sucks
            del self.commands["nick"]

        self.resize()
        self.update_commands()
        self.update_keys()

    @property
    def general_jid(self):
        return self.get_name()

    @property
    def last_connection(self):
        last_message = self._text_buffer.last_message
        if last_message:
            return last_message.time
        return None

    @refresh_wrapper.always
    def go_to_next_hl(self):
        """
        Go to the next HL in the room, or the last
        """
        self.text_win.next_highlight()

    @refresh_wrapper.always
    def go_to_prev_hl(self):
        """
        Go to the previous HL in the room, or the first
        """
        self.text_win.previous_highlight()

    def completion_version(self, the_input):
        """Completion for /version"""
        compare_users = lambda x: x.last_talked
        userlist = [user.nick for user in sorted(self.users, key=compare_users, reverse=True)\
                         if user.nick != self.own_nick]
        contact_list = [jid for jid in roster.jids()]
        userlist.extend(contact_list)
        return the_input.auto_completion(userlist, '', quotify=False)

    def completion_info(self, the_input):
        """Completion for /info"""
        compare_users = lambda x: x.last_talked
        userlist = [user.nick for user in sorted(self.users, key=compare_users, reverse=True)]
        return the_input.auto_completion(userlist, '', quotify=False)

    def completion_nick(self, the_input):
        """Completion for /nick"""
        nicks = [os.environ.get('USER'), config.get('default_nick', ''), self.core.get_bookmark_nickname(self.get_name())]
        while nicks.count(''):
            nicks.remove('')
        return the_input.auto_completion(nicks, '', quotify=False)

    def completion_recolor(self, the_input):
        return the_input.auto_completion(['random'], '', quotify=False)

    def completion_ignore(self, the_input):
        """Completion for /ignore"""
        userlist = [user.nick for user in self.users]
        userlist.remove(self.own_nick)
        return the_input.auto_completion(userlist, '', quotify=False)

    def completion_role(self, the_input):
        """Completion for /role"""
        text = the_input.get_text()
        args = common.shell_split(text)
        n = len(args)
        if text.endswith(' '):
            n += 1
        if n == 2:
            userlist = [user.nick for user in self.users]
            userlist.remove(self.own_nick)
            return the_input.auto_completion(userlist, '')
        elif n == 3:
            possible_roles = ['none', 'visitor', 'participant', 'moderator']
            return the_input.auto_completion(possible_roles, '')

    def completion_affiliation(self, the_input):
        """Completion for /affiliation"""
        text = the_input.get_text()
        args = common.shell_split(text)
        n = len(args)
        if text.endswith(' '):
            n += 1
        if n == 2:
            userlist = [user.nick for user in self.users]
            if self.own_nick in userlist:
                userlist.remove(self.own_nick)
            jidlist = [user.jid.bare for user in self.users]
            if self.core.xmpp.boundjid.bare in jidlist:
                jidlist.remove(self.core.xmpp.boundjid.bare)
            userlist.extend(jidlist)
            return the_input.auto_completion(userlist, '')
        elif n == 3:
            possible_affiliations = ['none', 'member', 'admin', 'owner']
            return the_input.auto_completion(possible_affiliations, '')

    def scroll_user_list_up(self):
        self.user_win.scroll_up()
        self.user_win.refresh(self.users)
        self.input.refresh()

    def scroll_user_list_down(self):
        self.user_win.scroll_down()
        self.user_win.refresh(self.users)
        self.input.refresh()

    def command_info(self, arg):
        """
        /info <nick>
        """
        if not arg:
            return self.core.command_help('info')
        user = self.get_user_by_name(arg)
        if not user:
            return self.core.information("Unknown user: %s" % arg)
        info = '%s%s: show: %s, affiliation: %s, role: %s%s' % (arg,
                        ' (%s)' % user.jid if user.jid else '',
                        user.show or 'Available',
                        user.affiliation or 'None',
                        user.role or 'None',
                        '\n%s' % user.status if user.status else '')
        self.core.information(info, 'Info')

    def command_configure(self, arg):
        form = self.core.xmpp.plugin['xep_0045'].getRoomForm(self.get_name())
        if not form:
            self.core.information('Could not retrieve the configuration form', 'Error')
            return
        self.core.open_new_form(form, self.cancel_config, self.send_config)

    def cancel_config(self, form):
        """
        The user do not want to send his/her config, send an iq cancel
        """
        self.core.xmpp.plugin['xep_0045'].cancelConfig(self.get_name())
        self.core.close_tab()

    def send_config(self, form):
        """
        The user sends his/her config to the server
        """
        self.core.xmpp.plugin['xep_0045'].configureRoom(self.get_name(), form)
        self.core.close_tab()

    def command_cycle(self, arg):
        """/cycle [reason]"""
        if self.joined:
            muc.leave_groupchat(self.core.xmpp, self.get_name(), self.own_nick, arg)
        self.disconnect()
        self.core.disable_private_tabs(self.name)
        self.core.command_join('"/%s"' % self.own_nick)
        self.user_win.pos = 0

    def command_recolor(self, arg):
        """
        /recolor [random]
        Re-assign color to the participants of the room
        """
        arg = arg.strip()
        compare_users = lambda x: x.last_talked
        users = list(self.users)
        sorted_users = sorted(users, key=compare_users, reverse=True)
        # search our own user, to remove it from the list
        for user in sorted_users:
            if user.nick == self.own_nick:
                sorted_users.remove(user)
                user.color = get_theme().COLOR_OWN_NICK
        colors = list(get_theme().LIST_COLOR_NICKNAMES)
        if arg and arg == 'random':
            random.shuffle(colors)
        for i, user in enumerate(sorted_users):
            user.color = colors[i % len(colors)]
        self.text_win.rebuild_everything(self._text_buffer)
        self.user_win.refresh(self.users)
        self.text_win.refresh()
        self.input.refresh()

    def command_version(self, arg):
        """
        /version <jid or nick>
        """
        def callback(res):
            if not res:
                return self.core.information('Could not get the software version from %s' % (jid,), 'Warning')
            version = '%s is running %s version %s on %s' % (jid,
                         res.get('name') or _('an unknown software'),
                         res.get('version') or _('unknown'),
                         res.get('os') or _('on an unknown platform'))
            self.core.information(version, 'Info')

        if not arg:
            return self.core.command_help('version')
        if arg in [user.nick for user in self.users]:
            jid = safeJID(self.name).bare
            jid = safeJID(jid + '/' + arg)
        else:
            jid = safeJID(arg)
        self.core.xmpp.plugin['xep_0092'].get_version(jid, callback=callback)

    def command_nick(self, arg):
        """
        /nick <nickname>
        """
        if not arg:
            return self.core.command_help('nick')
        nick = arg
        if not self.joined:
            return self.core.information('/nick only works in joined rooms', 'Info')
        current_status = self.core.get_status()
        if not safeJID(self.get_name() + '/' + nick):
            return self.core.information('Invalid nick', 'Info')
        muc.change_nick(self.core.xmpp, self.name, nick, current_status.message, current_status.show)

    def command_part(self, arg):
        """
        /part [msg]
        """
        arg = arg.strip()
        msg = None
        if self.joined:
            self.disconnect()
            muc.leave_groupchat(self.core.xmpp, self.name, self.own_nick, arg)
            if arg:
                msg = _("\x195}You left the chatroom (\x19o%s\x195})\x193}" % arg)
            else:
                msg =_("\x195}You left the chatroom\x193}")
            self.add_message(msg)
            if self == self.core.current_tab():
                self.refresh()
            self.core.doupdate()
        else:
            msg =_("\x195}You left the chatroom\x193}")
        self.core.disable_private_tabs(self.name, reason=msg)

    def command_close(self, arg):
        """
        /close [msg]
        """
        self.command_part(arg)
        self.core.close_tab()

    def command_query(self, arg):
        """
        /query <nick> [message]
        """
        args = common.shell_split(arg)
        if len(args) < 1:
            return
        nick = args[0]
        r = None
        for user in self.users:
            if user.nick == nick:
                r = self.core.open_private_window(self.name, user.nick)
        if r and len(args) > 1:
            msg = args[1]
            self.core.current_tab().command_say(xhtml.convert_simple_to_full_colors(msg))
        if not r:
            self.core.information(_("Cannot find user: %s" % nick), 'Error')

    def command_topic(self, arg):
        """
        /topic [new topic]
        """
        if not arg.strip():
            self._text_buffer.add_message(_("\x19%s}The subject of the room is: %s") %
                    (get_theme().COLOR_INFORMATION_TEXT[0], self.topic))
            self.text_win.refresh()
            self.input.refresh()
            return
        subject = arg
        muc.change_subject(self.core.xmpp, self.name, subject)

    def command_names(self, arg=None):
        """
        /names
        """
        if not self.joined:
            return
        color_visitor = get_theme().COLOR_USER_VISITOR[0]
        color_other = get_theme().COLOR_USER_NONE[0]
        color_moderator = get_theme().COLOR_USER_MODERATOR[0]
        color_participant = get_theme().COLOR_USER_PARTICIPANT[0]
        visitors, moderators, participants, others = [], [], [], []
        aff = {
                'owner': get_theme().CHAR_AFFILIATION_OWNER,
                'admin': get_theme().CHAR_AFFILIATION_ADMIN,
                'member': get_theme().CHAR_AFFILIATION_MEMBER,
                'none': get_theme().CHAR_AFFILIATION_NONE,
                }

        for user in self.users:
            if user.role == 'visitor':
                visitors.append((user, aff[user.affiliation]))
            elif user.role == 'participant':
                participants.append((user, aff[user.affiliation]))
            elif user.role == 'moderator':
                moderators.append((user, aff[user.affiliation]))
            else:
                others.append((user, aff[user.affiliation]))

        buff = ['Users: %s \n' % len(self.users)]
        for moderator in moderators:
            buff.append('\x19%s}%s\x19o\x19%s}%s\x19o' % (color_moderator,
                    moderator[1],  moderator[0].color[0], moderator[0].nick))
        for participant in participants:
            buff.append('\x19%s}%s\x19o\x19%s}%s\x19o' % (color_participant,
                    participant[1],  participant[0].color[0], participant[0].nick))
        for visitor in visitors:
            buff.append('\x19%s}%s\x19o\x19%s}%s\x19o' % (color_visitor,
                    visitor[1],  visitor[0].color[0], visitor[0].nick))
        for other in others:
            buff.append('\x19%s}%s\x19o\x19%s}%s\x19o' % (color_other,
                    other[1],  other[0].color[0], other[0].nick))
        buff.append('\n')
        message = ' '.join(buff)

        self._text_buffer.add_message(message)
        self.text_win.refresh()
        self.input.refresh()

    def completion_topic(self, the_input):
        current_topic = self.topic
        return the_input.auto_completion([current_topic], '', quotify=False)

    def completion_quoted(self, the_input):
        """Nick completion, but with quotes"""
        compare_users = lambda x: x.last_talked
        word_list = [user.nick for user in sorted(self.users, key=compare_users, reverse=True)\
                         if user.nick != self.own_nick]
        return the_input.auto_completion(word_list, '', quotify=True)

    def command_kick(self, arg):
        """
        /kick <nick> [reason]
        """
        args = common.shell_split(arg)
        if not args:
            self.core.command_help('kick')
        else:
            if len(args) > 1:
                msg = ' "%s"' % args[1]
            else:
                msg = ''
            self.command_role('"'+args[0]+ '" none'+msg)

    def command_ban(self, arg):
        """
        /ban <nick> [reason]
        """
        args = common.shell_split(arg)
        if not args:
            self.core.command_help('ban')
        else:
            if len(args) > 1:
                msg = ' "%s"' %args[1]
            else:
                msg = ''
            self.command_affiliation('"'+args[0]+ '" outcast'+msg)

    def command_role(self, arg):
        """
        /role <nick> <role> [reason]
        Changes the role of an user
        roles can be: none, visitor, participant, moderator
        """
        args = common.shell_split(arg)
        if len(args) < 2:
            self.core.command_help('role')
            return
        nick, role = args[0],args[1]
        if len(args) > 2:
            reason = ' '.join(args[2:])
        else:
            reason = ''
        if not self.joined or \
                not role in ('none', 'visitor', 'participant', 'moderator'):
            return
        if not safeJID(self.get_name() + '/' + nick):
            return self.core('Invalid nick', 'Info')
        res = muc.set_user_role(self.core.xmpp, self.get_name(), nick, reason, role)
        if res['type'] == 'error':
            self.core.room_error(res, self.get_name())

    def command_affiliation(self, arg):
        """
        /affiliation <nick> <role>
        Changes the affiliation of an user
        affiliations can be: outcast, none, member, admin, owner
        """
        args = common.shell_split(arg)
        if len(args) < 2:
            self.core.command_help('affiliation')
            return
        nick, affiliation = args[0], args[1].lower()
        if not self.joined:
            return
        if affiliation not in ('outcast', 'none', 'member', 'admin', 'owner'):
            self.core.command_help('affiliation')
            return
        if nick in [user.nick for user in self.users]:
            res = muc.set_user_affiliation(self.core.xmpp, self.get_name(), affiliation, nick=nick)
        else:
            res = muc.set_user_affiliation(self.core.xmpp, self.get_name(), affiliation, jid=safeJID(nick))
        if not res:
            self.core.information('Could not set affiliation', 'Error')

    def command_say(self, line, correct=False):
        """
        /say <message>
        Or normal input + enter
        """
        needed = 'inactive' if self.inactive else 'active'
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = 'groupchat'
        msg['body'] = line
        # trigger the event BEFORE looking for colors.
        # This lets a plugin insert \x19xxx} colors, that will
        # be converted in xhtml.
        self.core.events.trigger('muc_say', msg, self)
        if msg['body'].find('\x19') != -1:
            msg['xhtml_im'] = xhtml.poezio_colors_to_html(msg['body'])
            msg['body'] = xhtml.clean_text(msg['body'])
        if config.get_by_tabname('send_chat_states', 'true', self.general_jid, True) == 'true' and self.remote_wants_chatstates is not False:
            msg['chat_state'] = needed
        if correct:
            msg['replace']['id'] = self.last_sent_message['id']
        self.cancel_paused_delay()
        self.core.events.trigger('muc_say_after', msg, self)
        self.last_sent_message = msg
        msg.send()
        self.chat_state = needed

    def command_ignore(self, arg):
        """
        /ignore <nick>
        """
        if not arg:
            self.core.command_help('ignore')
            return
        nick = arg
        user = self.get_user_by_name(nick)
        if not user:
            self.core.information(_('%s is not in the room') % nick)
        elif user in self.ignores:
            self.core.information(_('%s is already ignored') % nick)
        else:
            self.ignores.append(user)
            self.core.information(_("%s is now ignored") % nick, 'info')

    def command_unignore(self, arg):
        """
        /unignore <nick>
        """
        if not arg:
            self.core.command_help('unignore')
            return
        nick = arg
        user = self.get_user_by_name(nick)
        if not user:
            self.core.information(_('%s is not in the room') % nick)
        elif user not in self.ignores:
            self.core.information(_('%s is not ignored') % nick)
        else:
            self.ignores.remove(user)
            self.core.information(_('%s is now unignored') % nick)

    def completion_unignore(self, the_input):
        return the_input.auto_completion([user.nick for user in self.ignores], ' ', quotify=False)

    def resize(self):
        """
        Resize the whole window. i.e. all its sub-windows
        """
        if not self.visible:
            return
        self.need_resize = False
        if config.get("hide_user_list", "false") == "true":
            text_width = self.width
        else:
            text_width = (self.width//10)*9
        self.user_win.resize(self.height-3-self.core.information_win_size - Tab.tab_win_height(), self.width-(self.width//10)*9-1, 1, (self.width//10)*9+1)
        self.topic_win.resize(1, self.width, 0, 0)
        self.v_separator.resize(self.height-2 - Tab.tab_win_height(), 1, 1, 9*(self.width//10))
        self.text_win.resize(self.height-3-self.core.information_win_size - Tab.tab_win_height(), text_width, 1, 0)
        self.text_win.rebuild_everything(self._text_buffer)
        self.info_header.resize(1, self.width, self.height-2-self.core.information_win_size - Tab.tab_win_height(), 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s',self.__class__.__name__)
        self.topic_win.refresh(self.get_single_line_topic())
        self.text_win.refresh()
        if config.get("hide_user_list", "false") == "false":
            self.v_separator.refresh()
            self.user_win.refresh(self.users)
        self.info_header.refresh(self, self.text_win)
        self.refresh_tab_win()
        self.info_win.refresh()
        self.input.refresh()

    def on_input(self, key, raw):
        if not raw and key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key, raw=raw)
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)
        return False

    def completion(self):
        """
        Called when Tab is pressed, complete the nickname in the input
        """
        if self.complete_commands(self.input):
            return

        # If we are not completing a command or a command's argument, complete a nick
        compare_users = lambda x: x.last_talked
        word_list = [user.nick for user in sorted(self.users, key=compare_users, reverse=True)\
                         if user.nick != self.own_nick]
        after = config.get('after_completion', ',')+" "
        input_pos = self.input.pos + self.input.line_pos
        if ' ' not in self.input.get_text()[:input_pos] or (self.input.last_completion and\
                     self.input.get_text()[:input_pos] == self.input.last_completion + after):
            add_after = after
        else:
            add_after = '' if config.get('add_space_after_completion', 'true') == 'false' else ' '
        self.input.auto_completion(word_list, add_after, quotify=False)
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)

    def get_color_state(self):
        return self.color_state

    def set_color_state(self, color):
        self.set_color_state(color)

    def get_name(self):
        return self.name

    def get_nick(self):
        if config.getl('show_muc_jid', 'true') == 'false':
            return safeJID(self.name).user
        return self.name

    def get_text_window(self):
        return self.text_win

    def on_lose_focus(self):
        if self.joined:
            self.state = 'normal'
        else:
            self.state = 'disconnected'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        if config.get_by_tabname('send_chat_states', 'true', self.general_jid, True) == 'true' and not self.input.get_text():
            self.send_chat_state('inactive')

    def on_gain_focus(self):
        self.state = 'current'
        if self.text_win.built_lines and self.text_win.built_lines[-1] is None and config.getl('show_useless_separator', 'false') != 'true':
            self.text_win.remove_line_separator()
        curses.curs_set(1)
        if self.joined and config.get_by_tabname('send_chat_states', 'true', self.general_jid, True) == 'true' and not self.input.get_text():
            self.send_chat_state('active')

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        if config.get("hide_user_list", "false") == "true":
            text_width = self.width
        else:
            text_width = (self.width//10)*9
        self.user_win.resize(self.height-3-self.core.information_win_size - Tab.tab_win_height(), self.width-(self.width//10)*9-1, 1, (self.width//10)*9+1)
        self.text_win.resize(self.height-3-self.core.information_win_size - Tab.tab_win_height(), text_width, 1, 0)
        self.info_header.resize(1, self.width, self.height-2-self.core.information_win_size - Tab.tab_win_height(), 0)

    def handle_presence(self, presence):
        from_nick = presence['from'].resource
        from_room = presence['from'].bare
        status_codes = set([s.attrib['code'] for s in presence.findall('{%s}x/{%s}status' % (NS_MUC_USER, NS_MUC_USER))])
        # Check if it's not an error presence.
        if presence['type'] == 'error':
            return self.core.room_error(presence, from_room)
        affiliation = presence['muc']['affiliation']
        show = presence['show']
        status = presence['status']
        role = presence['muc']['role']
        jid = presence['muc']['jid']
        typ = presence['type']
        if not self.joined:     # user in the room BEFORE us.
            # ignore redondant presence message, see bug #1509
            if from_nick not in [user.nick for user in self.users] and typ != "unavailable":
                new_user = User(from_nick, affiliation, show, status, role, jid)
                self.users.append(new_user)
                self.core.events.trigger('muc_join', presence, self)
                if from_nick == self.own_nick:
                    self.joined = True
                    if self.get_name() in self.core.initial_joins:
                        self.core.initial_joins.remove(self.get_name())
                        self._state = 'normal'
                    elif self != self.core.current_tab():
                        self._state = 'joined'
                    if self.core.current_tab() == self and self.core.status.show not in ('xa', 'away'):
                        self.send_chat_state('active')
                    new_user.color = get_theme().COLOR_OWN_NICK
                    self.add_message(_("\x19%(info_col)s}Your nickname is \x193}%(nick)s") % {'nick': from_nick, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
                    if '201' in status_codes:
                        self.add_message('\x19%(info_col)s}Info: The room has been created' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
                    if '170' in status_codes:
                        self.add_message('\x191}Warning: \x19%(info_col)s}this room is publicly logged' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
                    if '100' in status_codes:
                        self.add_message('\x191}Warning: \x19%(info_col)s}This room is not anonymous.' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
                    if self.core.current_tab() is not self:
                        self.refresh_tab_win()
                        self.core.current_tab().input.refresh()
                        self.core.doupdate()
                    self.core.enable_private_tabs(self.get_name())
        else:
            change_nick = '303' in status_codes
            kick = '307' in status_codes and typ == 'unavailable'
            ban = '301' in status_codes and typ == 'unavailable'
            shutdown = '332' in status_codes and typ == 'unavailable'
            non_member = '322' in status_codes and typ == 'unavailable'
            user = self.get_user_by_name(from_nick)
            # New user
            if not user:
                self.core.events.trigger('muc_join', presence, self)
                self.on_user_join(from_nick, affiliation, show, status, role, jid)
            # nick change
            elif change_nick:
                self.core.events.trigger('muc_nickchange', presence, self)
                self.on_user_nick_change(presence, user, from_nick, from_room)
            elif ban:
                self.core.events.trigger('muc_ban', presence, self)
                self.core.on_user_left_private_conversation(from_room, from_nick, status)
                self.on_user_banned(presence, user, from_nick)
            # kick
            elif kick:
                self.core.events.trigger('muc_kick', presence, self)
                self.core.on_user_left_private_conversation(from_room, from_nick, status)
                self.on_user_kicked(presence, user, from_nick)
            elif shutdown:
                self.core.events.trigger('muc_shutdown', presence, self)
                self.on_muc_shutdown()
            elif non_member:
                self.core.events.trigger('muc_shutdown', presence, self)
                self.on_non_member_kick()
            # user quit
            elif typ == 'unavailable':
                self.on_user_leave_groupchat(user, jid, status, from_nick, from_room)
            # status change
            else:
                self.on_user_change_status(user, from_nick, from_room, affiliation, role, show, status)
        if self.core.current_tab() is self:
            self.text_win.refresh()
            self.user_win.refresh(self.users)
            self.info_header.refresh(self, self.text_win)
            self.input.refresh()
            self.core.doupdate()

    def on_non_member_kicked(self):
        """We have been kicked because the MUC is members-only"""
        self.add_message('\x19%(info_col)s}%You have been kicked because you are not a member and the room is now members-only.' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
        self.disconnect()

    def on_muc_shutdown(self):
        """We have been kicked because the MUC service is shutting down"""
        self.add_message('\x19%(info_col)s}%You have been kicked because the MUC service is shutting down.' % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
        self.disconnect()

    def on_user_join(self, from_nick, affiliation, show, status, role, jid):
        """
        When a new user joins the groupchat
        """
        user = User(from_nick, affiliation,
                    show, status, role, jid)
        self.users.append(user)
        hide_exit_join = config.get_by_tabname('hide_exit_join', -1, self.general_jid, True)
        if hide_exit_join != 0:
            color = user.color[0] if config.get_by_tabname('display_user_color_in_join_part', '', self.general_jid, True) == 'true' else 3
            if not jid.full:
                msg = '\x194}%(spec)s \x19%(color)d}%(nick)s\x19%(info_col)s} joined the room' % {'nick':from_nick, 'color':color, 'spec':get_theme().CHAR_JOIN, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            else:
                msg = '\x194}%(spec)s \x19%(color)d}%(nick)s \x19%(info_col)s}(\x194}%(jid)s\x19%(info_col)s}) joined the room' % {'spec':get_theme().CHAR_JOIN, 'nick':from_nick, 'color':color, 'jid':jid.full, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            self.add_message(msg)
        self.core.on_user_rejoined_private_conversation(self.name, from_nick)

    def on_user_nick_change(self, presence, user, from_nick, from_room):
        new_nick = presence.find('{%s}x/{%s}item' % (NS_MUC_USER, NS_MUC_USER)).attrib['nick']
        if user.nick == self.own_nick:
            self.own_nick = new_nick
            # also change our nick in all private discussion of this room
            for _tab in self.core.tabs:
                if isinstance(_tab, PrivateTab) and safeJID(_tab.get_name()).bare == self.name:
                    _tab.own_nick = new_nick
        user.change_nick(new_nick)
        color = user.color[0] if config.get_by_tabname('display_user_color_in_join_part', '', self.general_jid, True) == 'true' else 3
        self.add_message('\x19%(color)d}%(old)s\x19%(info_col)s} is now known as \x19%(color)d}%(new)s' % {'old':from_nick, 'new':new_nick, 'color':color, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
        # rename the private tabs if needed
        self.core.rename_private_tabs(self.name, from_nick, new_nick)

    def on_user_banned(self, presence, user, from_nick):
        """
        When someone is banned from a muc
        """
        self.users.remove(user)
        by = presence.find('{%s}x/{%s}item/{%s}actor' % (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        reason = presence.find('{%s}x/{%s}item/{%s}reason' % (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        by = by.attrib['jid'] if by is not None else None
        if from_nick == self.own_nick: # we are banned
            if by:
                kick_msg = _('\x191}%(spec)s \x193}You\x19%(info_col)s} have been banned by \x194}%(by)s') % {'spec': get_theme().CHAR_KICK, 'by':by, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            else:
                kick_msg = _('\x191}%(spec)s \x193}You\x19%(info_col)s} have been banned.') % {'spec':get_theme().CHAR_KICK, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            self.core.disable_private_tabs(self.name, reason=kick_msg)
            self.disconnect()
            self.refresh_tab_win()
            self.core.current_tab().input.refresh()
            self.core.doupdate()
            if config.get_by_tabname('autorejoin', 'false', self.general_jid, True) == 'true':
                delay = config.get_by_tabname('autorejoin_delay', "5", self.general_jid, True)
                delay = common.parse_str_to_secs(delay)
                if delay <= 0:
                    muc.join_groupchat(self.core.xmpp, self.name, self.own_nick)
                else:
                    self.core.add_timed_event(timed_events.DelayedEvent(
                        delay,
                        muc.join_groupchat,
                        self.core.xmpp,
                        self.name,
                        self.own_nick))

        else:
            color = user.color[0] if config.get_by_tabname('display_user_color_in_join_part', '', self.general_jid, True) == 'true' else 3
            if by:
                kick_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x19%(info_col)s} has been banned by \x194}%(by)s') % {'spec':get_theme().CHAR_KICK, 'nick':from_nick, 'color':color, 'by':by, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            else:
                kick_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x19%(info_col)s} has been banned') % {'spec':get_theme().CHAR_KICK, 'nick':from_nick, 'color':color, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
        if reason is not None and reason.text:
            kick_msg += _('\x19%(info_col)s} Reason: \x196}%(reason)s\x19%(info_col)s}') % {'reason': reason.text, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
        self._text_buffer.add_message(kick_msg)

    def on_user_kicked(self, presence, user, from_nick):
        """
        When someone is kicked from a muc
        """
        self.users.remove(user)
        by = presence.find('{%s}x/{%s}item/{%s}actor' % (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        reason = presence.find('{%s}x/{%s}item/{%s}reason' % (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        by = by.attrib['jid'] if by is not None else None
        if from_nick == self.own_nick: # we are kicked
            if by:
                kick_msg = _('\x191}%(spec)s \x193}You\x19%(info_col)s} have been kicked by \x193}%(by)s') % {'spec': get_theme().CHAR_KICK, 'by':by, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            else:
                kick_msg = _('\x191}%(spec)s \x193}You\x19%(info_col)s} have been kicked.') % {'spec':get_theme().CHAR_KICK, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            self.core.disable_private_tabs(self.name, reason=kick_msg)
            self.disconnect()
            self.refresh_tab_win()
            self.core.current_tab().input.refresh()
            self.core.doupdate()
            # try to auto-rejoin
            if config.get_by_tabname('autorejoin', 'false', self.general_jid, True) == 'true':
                delay = config.get_by_tabname('autorejoin_delay', "5", self.general_jid, True)
                delay = common.parse_str_to_secs(delay)
                if delay <= 0:
                    muc.join_groupchat(self.core.xmpp, self.name, self.own_nick)
                else:
                    self.core.add_timed_event(timed_events.DelayedEvent(
                        delay,
                        muc.join_groupchat,
                        self.core.xmpp,
                        self.name,
                        self.own_nick))
        else:
            color = user.color[0] if config.get_by_tabname('display_user_color_in_join_part', '', self.general_jid, True) == 'true' else 3
            if by:
                kick_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x19%(info_col)s} has been kicked by \x193}%(by)s') % {'spec':get_theme().CHAR_KICK, 'nick':from_nick, 'color':color, 'by':by, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            else:
                kick_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x19%(info_col)s} has been kicked') % {'spec':get_theme().CHAR_KICK, 'nick':from_nick, 'color':color, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
        if reason is not None and reason.text:
            kick_msg += _('\x19%(info_col)s} Reason: \x196}%(reason)s') % {'reason': reason.text, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
        self.add_message(kick_msg)

    def on_user_leave_groupchat(self, user, jid, status, from_nick, from_room):
        """
        When an user leaves a groupchat
        """
        self.users.remove(user)
        if self.own_nick == user.nick:
            # We are now out of the room. Happens with some buggy (? not sure) servers
            self.disconnect()
            self.core.disable_private_tabs(from_room)
            self.refresh_tab_win()
            self.core.current_tab().input.refresh()
            self.core.doupdate()
        hide_exit_join = config.get_by_tabname('hide_exit_join', -1, self.general_jid, True) if config.get_by_tabname('hide_exit_join', -1, self.general_jid, True) >= -1 else -1
        if hide_exit_join == -1 or user.has_talked_since(hide_exit_join):
            color = user.color[0] if config.get_by_tabname('display_user_color_in_join_part', '', self.general_jid, True) == 'true' else 3
            if not jid.full:
                leave_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x19%(info_col)s} has left the room') % {'nick':from_nick, 'color':color, 'spec':get_theme().CHAR_QUIT, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            else:
                leave_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x19%(info_col)s} (\x194}%(jid)s\x19%(info_col)s}) has left the room') % {'spec':get_theme().CHAR_QUIT, 'nick':from_nick, 'color':color, 'jid':jid.full, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
            if status:
                leave_msg += ' (%s)' % status
            self.add_message(leave_msg)
        self.core.on_user_left_private_conversation(from_room, from_nick, status)

    def on_user_change_status(self, user, from_nick, from_room, affiliation, role, show, status):
        """
        When an user changes her status
        """
        # build the message
        display_message = False # flag to know if something significant enough
        # to be displayed has changed
        color = user.color[0] if config.get_by_tabname('display_user_color_in_join_part', '', self.general_jid, True) == 'true' else 3
        if from_nick == self.own_nick:
            msg = _('\x193}You\x19%(info_col)s} changed: ') % {'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
        else:
            msg = _('\x19%(color)d}%(nick)s\x19%(info_col)s} changed: ') % {'nick': from_nick, 'color': color, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
        if show not in SHOW_NAME:
            self.core.information("%s from room %s sent an invalid show: %s" %\
                                      (from_nick, from_room, show), "warning")
        if affiliation != user.affiliation:
            msg += _('affiliation: %s, ') % affiliation
            display_message = True
        if role != user.role:
            msg += _('role: %s, ') % role
            display_message = True
        if show != user.show and show in SHOW_NAME:
            msg += _('show: %s, ') % SHOW_NAME[show]
            display_message = True
        if status != user.status:
            # if the user sets his status to nothing
            if status:
                msg += _('status: %s, ') % status
                display_message = True
            elif show in SHOW_NAME and show == user.show:
                msg += _('show: %s, ') % SHOW_NAME[show]
                display_message = True
        if not display_message:
            return
        msg = msg[:-2] # remove the last ", "
        hide_status_change = config.get_by_tabname('hide_status_change', -1, self.general_jid, True)
        if hide_status_change < -1:
            hide_status_change = -1
        if ((hide_status_change == -1 or \
                user.has_talked_since(hide_status_change) or\
                user.nick == self.own_nick)\
                and\
                (affiliation != user.affiliation or\
                    role != user.role or\
                    show != user.show or\
                    status != user.status))\
                      or\
                        (affiliation != user.affiliation or\
                          role != user.role):
            # display the message in the room
            self._text_buffer.add_message(msg)
        self.core.on_user_changed_status_in_private('%s/%s' % (from_room, from_nick), msg)
        # finally, effectively change the user status
        user.update(affiliation, show, status, role)

    def disconnect(self):
        """
        Set the state of the room as not joined, so
        we can know if we can join it, send messages to it, etc
        """
        self.users = []
        if self is not self.core.current_tab():
            self.state = 'disconnected'
        self.joined = False

    def get_single_line_topic(self):
        """
        Return the topic as a single-line string (for the window header)
        """
        return self.topic.replace('\n', '|')

    def log_message(self, txt, time, nickname):
        """
        Log the messages in the archives, if it needs
        to be
        """
        if time is None and self.joined:        # don't log the history messages
            logger.log_message(self.name, nickname, txt)

    def do_highlight(self, txt, time, nickname):
        """
        Set the tab color and returns the nick color
        """
        highlighted = False
        if not time and nickname and nickname != self.own_nick and self.joined:
            if self.own_nick.lower() in txt.lower():
                if self.state != 'current':
                    self.state = 'highlight'
                highlighted = True
            else:
                highlight_words = config.get_by_tabname('highlight_on', '', self.general_jid, True).split(':')
                for word in highlight_words:
                    if word and word.lower() in txt.lower():
                        if self.state != 'current':
                            self.state = 'highlight'
                        highlighted = True
                        break
        if highlighted:
            beep_on = config.get('beep_on', 'highlight private').split()
            if 'highlight' in beep_on and 'message' not in beep_on:
                if config.get_by_tabname('disable_beep', 'false', self.name, False).lower() != 'true':
                    curses.beep()
        return highlighted

    def get_user_by_name(self, nick):
        """
        Gets the user associated with the given nick, or None if not found
        """
        for user in self.users:
            if user.nick == nick:
                return user
        return None

    def add_message(self, txt, time=None, nickname=None, forced_user=None, nick_color=None, history=None, identifier=None):
        """
        Note that user can be None even if nickname is not None. It happens
        when we receive an history message said by someone who is not
        in the room anymore
        Return True if the message highlighted us. False otherwise.
        """
        self.log_message(txt, time, nickname)
        user = self.get_user_by_name(nickname) if nickname is not None else None
        if user:
            user.set_last_talked(datetime.now())
        if not user and forced_user:
            user = forced_user
        if not time and nickname and\
                nickname != self.own_nick and\
                    self.state != 'current':
            if self.state != 'highlight':
                self.state = 'message'
        nick_color = nick_color or None
        highlight = False
        if (not nickname or time) and not txt.startswith('/me '):
            txt = '\x19%(info_col)s}%(txt)s' % {'txt':txt, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}
        else:                   # TODO
            highlight = self.do_highlight(txt, time, nickname)
        time = time or datetime.now()
        self._text_buffer.add_message(txt, time, nickname, nick_color, history, user, highlight=highlight, identifier=identifier)
        return highlight

    def modify_message(self, txt, old_id, new_id, time=None, nickname=None):
        self.log_message(txt, time, nickname)
        highlight = self.do_highlight(txt, time, nickname)
        message = self._text_buffer.modify_message(txt, old_id, new_id, highlight=highlight, time=time)
        if message:
            self.text_win.modify_message(old_id, message)
            self.core.refresh_window()
            return highlight

    def matching_names(self):
        return [safeJID(self.get_name()).user]

class PrivateTab(ChatTab):
    """
    The tab containg a private conversation (someone from a MUC)
    """
    message_type = 'chat'
    plugin_commands = {}
    plugin_keys = {}
    def __init__(self, name, nick):
        ChatTab.__init__(self, name)
        self.own_nick = nick
        self.name = name
        self.text_win = windows.TextWin()
        self._text_buffer.add_window(self.text_win)
        self.info_header = windows.PrivateInfoWin()
        self.input = windows.MessageInput()
        self.check_attention()
        # keys
        self.key_func['^I'] = self.completion
        # commands
        self.commands['info'] = (self.command_info, _('Usage: /info\nInfo: Display some information about the user in the MUC: its/his/her role, affiliation, status and status message.'), None)
        self.commands['unquery'] = (self.command_unquery, _("Usage: /unquery\nUnquery: Close the tab."), None)
        self.commands['close'] = (self.command_unquery, _("Usage: /close\nClose: Close the tab."), None)
        self.commands['version'] = (self.command_version, _('Usage: /version\nVersion: Get the software version of the current interlocutor (usually its XMPP client and Operating System).'), None)
        self.resize()
        self.parent_muc = self.core.get_tab_by_name(safeJID(name).bare, MucTab)
        self.on = True
        self.update_commands()
        self.update_keys()

    @property
    def general_jid(self):
        return self.get_name()

    def on_close(self):
        self.parent_muc.privates.remove(self)

    def completion(self):
        """
        Called when Tab is pressed, complete the nickname in the input
        """
        if self.complete_commands(self.input):
            return

        # If we are not completing a command or a command's argument, complete a nick
        compare_users = lambda x: x.last_talked
        word_list = [user.nick for user in sorted(self.parent_muc.users, key=compare_users, reverse=True)\
                         if user.nick != self.own_nick]
        after = config.get('after_completion', ',')+" "
        input_pos = self.input.pos + self.input.line_pos
        if ' ' not in self.input.get_text()[:input_pos] or (self.input.last_completion and\
                     self.input.get_text()[:input_pos] == self.input.last_completion + after):
            add_after = after
        else:
            add_after = ''
        self.input.auto_completion(word_list, add_after, quotify=False)
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)

    def command_say(self, line, attention=False, correct=False):
        if not self.on:
            return
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = 'chat'
        msg['body'] = line
        logger.log_message(self.get_name().replace('/', '\\'), self.own_nick, line)
        # trigger the event BEFORE looking for colors.
        # This lets a plugin insert \x19xxx} colors, that will
        # be converted in xhtml.
        self.core.events.trigger('private_say', msg, self)
        if correct:
            msg['replace']['id'] = self.last_sent_message['id']
            self.modify_message(line, self.last_sent_message['id'], msg['id'])
        else:
            self.add_message(msg['body'],
                    nickname=self.core.own_nick or self.own_nick,
                    nick_color=get_theme().COLOR_OWN_NICK,
                    identifier=msg['id'])
        if msg['body'].find('\x19') != -1:
            msg['xhtml_im'] = xhtml.poezio_colors_to_html(msg['body'])
            msg['body'] = xhtml.clean_text(msg['body'])
        if config.get_by_tabname('send_chat_states', 'true', self.general_jid, True) == 'true' and self.remote_wants_chatstates is not False:
            needed = 'inactive' if self.inactive else 'active'
            msg['chat_state'] = needed
        if attention and self.remote_supports_attention:
            msg['attention'] = True
        self.core.events.trigger('private_say_after', msg, self)
        self.last_sent_message = msg
        msg.send()
        self.cancel_paused_delay()
        self.text_win.refresh()
        self.input.refresh()

    def command_attention(self, message=''):
        if message is not '':
            self.command_say(message, attention=True)
        else:
            msg = self.core.xmpp.make_message(self.get_name())
            msg['type'] = 'chat'
            msg['attention'] = True
            msg.send()

    def check_attention(self):
        self.core.xmpp.plugin['xep_0030'].get_info(jid=self.get_name(), block=False, timeout=5, callback=self.on_attention_checked)

    def on_attention_checked(self, iq):
        if 'urn:xmpp:attention:0' in iq['disco_info'].get_features():
            self.core.information('Attention is supported', 'Info')
            self.remote_supports_attention = True
            self.commands['attention'] =  (self.command_attention, _('Usage: /attention [message]\nAttention: Require the attention of the contact. Can also send a message along with the attention.'), None)
        else:
            self.remote_supports_attention = False

    def command_unquery(self, arg):
        """
        /unquery
        """
        self.core.close_tab()

    def command_version(self, arg):
        """
        /version
        """
        def callback(res):
            if not res:
                return self.core.information('Could not get the software version from %s' % (jid,), 'Warning')
            version = '%s is running %s version %s on %s' % (jid,
                                                             res.get('name') or _('an unknown software'),
                                                             res.get('version') or _('unknown'),
                                                             res.get('os') or _('on an unknown platform'))
            self.core.information(version, 'Info')
        if arg:
            return self.core.command_version(arg)
        jid = safeJID(self.name)
        self.core.xmpp.plugin['xep_0092'].get_version(jid, callback=callback)

    def command_info(self, arg):
        """
        /info
        """
        if arg:
            self.parent_muc.command_info(arg)
        else:
            user = safeJID(self.name).resource
            self.parent_muc.command_info(user)

    def resize(self):
        if self.core.information_win_size >= self.height-3 or not self.visible:
            return
        self.need_resize = False
        self.text_win.resize(self.height-2-self.core.information_win_size - Tab.tab_win_height(), self.width, 0, 0)
        self.text_win.rebuild_everything(self._text_buffer)
        self.info_header.resize(1, self.width, self.height-2-self.core.information_win_size - Tab.tab_win_height(), 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s',self.__class__.__name__)
        self.text_win.refresh()
        self.info_header.refresh(self.name, self.text_win, self.chatstate)
        self.info_win.refresh()
        self.refresh_tab_win()
        self.input.refresh()

    def refresh_info_header(self):
        self.info_header.refresh(self.name, self.text_win, self.chatstate)
        self.input.refresh()

    def get_name(self):
        return self.name

    def get_nick(self):
        return safeJID(self.name).resource

    def on_input(self, key, raw):
        if not raw and key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key, raw=raw)
        if not self.on:
            return False
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        tab = self.core.get_tab_by_name(safeJID(self.name).bare, MucTab)
        if tab and tab.joined:
            self.send_composing_chat_state(empty_after)
        return False

    def on_lose_focus(self):
        self.state = 'normal'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        tab = self.core.get_tab_by_name(safeJID(self.name).bare, MucTab)
        if tab and tab.joined and config.get_by_tabname(
                'send_chat_states', 'true', self.general_jid, True) == 'true'\
                    and not self.input.get_text() and self.on:
            self.send_chat_state('inactive')

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(1)
        tab = self.core.get_tab_by_name(safeJID(self.name).bare, MucTab)
        if tab and tab.joined and config.get_by_tabname(
                'send_chat_states', 'true', self.general_jid, True) == 'true'\
                    and not self.input.get_text() and self.on:
            self.send_chat_state('active')

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        self.text_win.resize(self.height-2-self.core.information_win_size - Tab.tab_win_height(), self.width, 0, 0)
        self.info_header.resize(1, self.width, self.height-2-self.core.information_win_size - Tab.tab_win_height(), 0)

    def get_text_window(self):
        return self.text_win

    def rename_user(self, old_nick, new_nick):
        """
        The user changed her nick in the corresponding muc: update the tab’s name and
        display a message.
        """
        self.add_message('\x193}%(old)s\x19%(info_col)s} is now known as \x193}%(new)s' % {'old':old_nick, 'new':new_nick, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
        new_jid = safeJID(self.name).bare+'/'+new_nick
        self.name = new_jid

    @refresh_wrapper.conditional
    def user_left(self, status_message, from_nick):
        """
        The user left the associated MUC
        """
        self.deactivate()
        if not status_message:
            self.add_message(_('\x191}%(spec)s \x193}%(nick)s\x19%(info_col)s} has left the room') % {'nick':from_nick, 'spec':get_theme().CHAR_QUIT, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
        else:
            self.add_message(_('\x191}%(spec)s \x193}%(nick)s\x19%(info_col)s} has left the room (%(status)s)"') % {'nick':from_nick, 'spec':get_theme().CHAR_QUIT, 'status': status_message, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
        return self.core.current_tab() is self

    @refresh_wrapper.conditional
    def user_rejoined(self, nick):
        """
        The user (or at least someone with the same nick) came back in the MUC
        """
        self.activate()
        tab = self.core.get_tab_by_name(safeJID(self.name).bare, MucTab)
        color = 3
        if tab and config.get_by_tabname('display_user_color_in_join_part', '', self.general_jid, True):
            user = tab.get_user_by_name(nick)
            if user:
                color = user.color[0]
        self.add_message('\x194}%(spec)s \x19%(color)d}%(nick)s\x19%(info_col)s} joined the room' % {'nick':nick, 'color': color, 'spec':get_theme().CHAR_JOIN, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]})
        return self.core.current_tab() is self

    def activate(self, reason=None):
        self.on = True
        if reason:
            self.add_message(txt=reason)

    def deactivate(self, reason=None):
        self.on = False
        if reason:
            self.add_message(txt=reason)

    def modify_message(self, txt, old_id, new_id):
        self.log_message(txt, time, self.name)
        message = self._text_buffer.modify_message(txt, old_id, new_id, time=time)
        if message:
            self.text_win.modify_message(old_id, message)
            self.core.refresh_window()

    def add_message(self, txt, time=None, nickname=None, forced_user=None, nick_color=None, identifier=None):
        self._text_buffer.add_message(txt, time=time,
                nickname=nickname,
                nick_color=nick_color,
                history=None,
                user=forced_user,
                identifier=identifier)

    def matching_names(self):
        return [safeJID(self.get_name()).resource]

class RosterInfoTab(Tab):
    """
    A tab, splitted in two, containing the roster and infos
    """
    plugin_commands = {}
    plugin_keys = {}
    def __init__(self):
        Tab.__init__(self)
        self.name = "Roster"
        self.v_separator = windows.VerticalSeparator()
        self.information_win = windows.TextWin()
        self.core.information_buffer.add_window(self.information_win)
        self.roster_win = windows.RosterWin()
        self.contact_info_win = windows.ContactInfoWin()
        self.default_help_message = windows.HelpText("Enter commands with “/”. “o”: toggle offline show")
        self.input = self.default_help_message
        self.state = 'normal'
        self.key_func['^I'] = self.completion
        self.key_func[' '] = self.on_space
        self.key_func["/"] = self.on_slash
        self.key_func["KEY_UP"] = self.move_cursor_up
        self.key_func["KEY_DOWN"] = self.move_cursor_down
        self.key_func["M-u"] = self.move_cursor_to_next_contact
        self.key_func["M-y"] = self.move_cursor_to_prev_contact
        self.key_func["M-U"] = self.move_cursor_to_next_group
        self.key_func["M-Y"] = self.move_cursor_to_prev_group
        self.key_func["M-[1;5B"] = self.move_cursor_to_next_group
        self.key_func["M-[1;5A"] = self.move_cursor_to_prev_group
        self.key_func["l"] = self.command_activity
        self.key_func["o"] = self.toggle_offline_show
        self.key_func["v"] = self.get_contact_version
        self.key_func["i"] = self.show_contact_info
        self.key_func["n"] = self.change_contact_name
        self.key_func["s"] = self.start_search
        self.key_func["S"] = self.start_search_slow
        self.commands['deny'] = (self.command_deny, _("Usage: /deny [jid]\nDeny: Deny your presence to the provided JID (or the selected contact in your roster), who is asking you to be in his/here roster."), self.completion_deny)
        self.commands['accept'] = (self.command_accept, _("Usage: /accept [jid]\nAccept: Allow the provided JID (or the selected contact in your roster), to see your presence."), self.completion_deny)
        self.commands['add'] = (self.command_add, _("Usage: /add <jid>\nAdd: Add the specified JID to your roster, ask him to allow you to see his presence, and allow him to see your presence."), None)
        self.commands['name'] = (self.command_name, _("Usage: /name <jid> <name>\nSet the given JID's name."), self.completion_name)
        self.commands['groupadd'] = (self.command_groupadd, _("Usage: /groupadd <jid> <group>\nAdd the given JID to the given group."), self.completion_groupadd)
        self.commands['groupmove'] = (self.command_groupmove, _("Usage: /groupchange <jid> <old group> <new group>\nMoves the given JID from the old group to the new group."), self.completion_groupmove)
        self.commands['groupremove'] = (self.command_groupremove, _("Usage: /groupremove <jid> <group>\nRemove the given JID from the given group."), self.completion_groupremove)
        self.commands['remove'] = (self.command_remove, _("Usage: /remove [jid]\nRemove: Remove the specified JID from your roster. This wil unsubscribe you from its presence, cancel its subscription to yours, and remove the item from your roster."), self.completion_remove)
        self.commands['reconnect'] = (self.command_reconnect, _('Usage: /reconnect\nConnect: Disconnect from the remote server if you are currently connected and then connect to it again.'), None)
        self.commands['export'] = (self.command_export, _("Usage: /export [/path/to/file]\nExport: Export your contacts into /path/to/file if specified, or $HOME/poezio_contacts if not."), self.completion_file)
        self.commands['import'] = (self.command_import, _("Usage: /import [/path/to/file]\nImport: Import your contacts from /path/to/file if specified, or $HOME/poezio_contacts if not."), self.completion_file)
        self.commands['clear_infos'] = (self.command_clear_infos, _("Usage: /clear_infos\nClear Infos: Use this command to clear the info buffer."), None)
        self.commands['activity'] = (self.command_activity, _("Usage: /activity <jid>\nActivity: Informs you of the last activity of a JID."), self.core.completion_activity)
        self.core.xmpp.add_event_handler('session_start',
                lambda event: self.core.xmpp.plugin['xep_0030'].get_info(
                    jid=self.core.xmpp.boundjid.domain,
                    block=False, timeout=5, callback=self.check_blocking)
                )
        self.resize()
        self.update_commands()
        self.update_keys()

    def check_blocking(self, iq):
        if iq['type'] == 'error':
            return
        if 'urn:xmpp:blocking' in iq['disco_info'].get_features():
            self.commands['block'] = (self.command_block, _("Usage: /block [jid]\nBlock: prevent a JID from talking to you."), self.completion_block)
            self.commands['unblock'] = (self.command_unblock, _("Usage: /unblock [jid]\nUnblock: allow a JID to talk to you."), self.completion_unblock)
            self.commands['list_blocks'] = (self.command_list_blocks, _("Usage: /list_blocks\nList Blocks: Retrieve the list of the blocked contacts."), None)
            self.core.xmpp.del_event_handler('session_start', self.check_blocking)
            self.core.xmpp.add_event_handler('blocked_message', self.on_blocked_message)
        else:
            self.core.information('Simple blocking not supported by the server', 'Info')

    def on_blocked_message(self, message):
        """
        When we try to send a message to a blocked contact
        """
        tab = self.core.get_conversation_by_jid(message['from'], False)
        if not tab:
            log.debug('Received message from nonexistent tab: %s', message['from'])
        message = '\x19%(info_col)s}Cannot send message to %(jid)s: contact blocked' % {
                'info_col': get_theme().COLOR_INFORMATION_TEXT[0],
                'jid': message['from'],
            }
        tab.add_message(message)

    def command_block(self, arg):
        """
        /block [jid]
        """
        def callback(iq):
            if iq['type'] == 'error':
                return self.core.information('Could not block the contact.', 'Error')
            elif iq['type'] == 'result':
                return self.core.information('Contact blocked.', 'Info')

        item = self.roster_win.selected_row
        if arg:
            jid = safeJID(arg)
        elif isinstance(item, Contact):
            jid = item.bare_jid
        elif isinstance(item, Resource):
            jid = item.jid.bare
        self.core.xmpp.plugin['xep_0191'].block(jid, block=False, callback=callback)

    def completion_block(self, the_input):
        """
        Completion for /block
        """
        jids = roster.jids()
        return the_input.auto_completion(jids, '', quotify=False)

    def command_unblock(self, arg):
        """
        /unblock [jid]
        """
        def callback(iq):
            if iq['type'] == 'error':
                return self.core.information('Could not unblock the contact.', 'Error')
            elif iq['type'] == 'result':
                return self.core.information('Contact unblocked.', 'Info')

        item = self.roster_win.selected_row
        if arg:
            jid = safeJID(arg)
        elif isinstance(item, Contact):
            jid = item.bare_jid
        elif isinstance(item, Resource):
            jid = item.jid.bare
        self.core.xmpp.plugin['xep_0191'].unblock(jid, block=False, callback=callback)

    def completion_unblock(self, the_input):
        """
        Completion for /unblock
        """
        try:
            iq = self.core.xmpp.plugin['xep_0191'].get_blocked(block=True)
        except Exception as e:
            iq = e.iq
        finally:
            if iq['type'] == 'error':
                return
            l = [str(item) for item in iq['blocklist']['items']]
            return the_input.auto_completion(l, quotify=False)

    def command_list_blocks(self, arg=None):
        """
        /list_blocks
        """
        def callback(iq):
            if iq['type'] == 'error':
                return self.core.information('Could not retrieve the blocklist.', 'Error')
            s = 'List of blocked JIDs:\n'
            items = (str(item) for item in iq['blocklist']['items'])
            jids = '\n'.join(items)
            if jids:
                s += jids
            else:
                s = 'No blocked JIDs.'
            self.core.information(s, 'Info')

        self.core.xmpp.plugin['xep_0191'].get_blocked(block=False, callback=callback)

    def command_reconnect(self, args=None):
        """
        /reconnect
        """
        self.core.disconnect(reconnect=True)

    def command_activity(self, arg=None):
        """
        /activity [jid]
        """

        item = self.roster_win.selected_row
        if arg:
            jid = arg
        elif isinstance(item, Contact):
            jid = item.bare_jid
        elif isinstance(item, Resource):
            jid = item.jid.bare
        else:
            self.core.information('No JID selected.', 'Error')
            return
        self.core.command_activity(jid)

    def resize(self):
        if not self.visible:
            return
        self.need_resize = False
        roster_width = self.width//2
        info_width = self.width-roster_width-1
        self.v_separator.resize(self.height-1 - Tab.tab_win_height(), 1, 0, roster_width)
        self.information_win.resize(self.height-2-4, info_width, 0, roster_width+1, self.core.information_buffer)
        self.roster_win.resize(self.height-1 - Tab.tab_win_height(), roster_width, 0, 0)
        self.contact_info_win.resize(5 - Tab.tab_win_height(), info_width, self.height-2-4, roster_width+1)
        self.input.resize(1, self.width, self.height-1, 0)

    def completion(self):
        # Check if we are entering a command (with the '/' key)
        if isinstance(self.input, windows.Input) and\
                not self.input.help_message:
            self.complete_commands(self.input)

    def completion_file(self, the_input):
        """
        Completion for /import and /export
        """
        text = the_input.get_text()
        args = text.split()
        n = len(args)
        if n == 1:
            home = os.getenv('HOME') or '/'
            return the_input.auto_completion([home, '/tmp'], '')
        else:
            the_path = text[text.index(' ')+1:]
            try:
                names = os.listdir(the_path)
            except:
                names = []
            end_list = []
            for name in names:
                value = os.path.join(the_path, name)
                if not name.startswith('.'):
                    end_list.append(value)

            return the_input.auto_completion(end_list, '')

    def command_clear_infos(self, arg):
        """
        /clear_infos
        """
        self.core.information_buffer.messages = []
        self.information_win.rebuild_everything(self.core.information_buffer)
        self.core.information_win.rebuild_everything(self.core.information_buffer)
        self.refresh()

    def command_deny(self, arg):
        """
        /deny [jid]
        Denies a JID from our roster
        """
        if not arg:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            else:
                self.core.information('No subscription to deny')
                return
        else:
            jid = safeJID(arg).bare
            if not jid in [jid for jid in roster.jids()]:
                self.core.information('No subscription to deny')
                return

        contact = roster[jid]
        if contact:
            contact.unauthorize()

    def command_add(self, args):
        """
        Add the specified JID to the roster, and set automatically
        accept the reverse subscription
        """
        jid = safeJID(safeJID(args.strip()).bare)
        if not jid:
            self.core.information(_('No JID specified'), 'Error')
            return
        if jid in roster and roster[jid].subscription in ('to', 'both'):
            return self.core.information('Already subscribed.', 'Roster')
        roster.add(jid)

    def command_name(self, arg):
        """
        Set a name for the specified JID in your roster
        """
        args = common.shell_split(arg)
        if not args:
            return self.core.command_help('name')
        jid = safeJID(args[0]).bare
        name = args[1] if len(args) == 2 else ''

        contact = roster[jid]
        if contact is None:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        groups = set(contact.groups)
        subscription = contact.subscription
        if not self.core.xmpp.update_roster(jid, name=name, groups=groups, subscription=subscription):
            self.core.information('The name could not be set.', 'Error')

    def command_groupadd(self, args):
        """
        Add the specified JID to the specified group
        """
        args = common.shell_split(args)
        if len(args) != 2:
            return
        jid = safeJID(args[0]).bare
        group = args[1]

        contact = roster[jid]
        if contact is None:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        new_groups = set(contact.groups)
        if group in new_groups:
            self.core.information(_('JID already in group'), 'Error')
            return

        new_groups.add(group)
        try:
            new_groups.remove('none')
        except KeyError:
            pass

        name = contact.name
        subscription = contact.subscription
        if self.core.xmpp.update_roster(jid, name=name, groups=new_groups, subscription=subscription):
            roster.update_contact_groups(jid)

    def command_groupmove(self, arg):
        """
        Remove the specified JID from the first specified group and add it to the second one
        """
        args = common.shell_split(arg)
        if len(args) != 3:
            return self.core.command_help('groupmove')
        jid = safeJID(args[0]).bare
        group_from = args[1]
        group_to = args[2]

        contact = roster[jid]
        if not contact:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        new_groups = set(contact.groups)
        if 'none' in new_groups:
            new_groups.remove('none')

        if group_to == 'none' or group_from == 'none':
            self.core.information(_('"none" is not a group.'), 'Error')
            return

        if group_from not in new_groups:
            self.core.information(_('JID not in first group'), 'Error')
            return

        if group_to in new_groups:
            self.core.information(_('JID already in second group'), 'Error')
            return

        if group_to == group_from:
            self.core.information(_('The groups are the same.'), 'Error')
            return

        new_groups.add(group_to)
        if 'none' in new_groups:
            new_groups.remove('none')

        new_groups.remove(group_from)
        name = contact.name
        subscription = contact.subscription
        if self.core.xmpp.update_roster(jid, name=name, groups=new_groups, subscription=subscription):
            roster.update_contact_groups(contact)

    def command_groupremove(self, args):
        """
        Remove the specified JID from the specified group
        """
        args = common.shell_split(args)
        if len(args) != 2:
            return
        jid = safeJID(args[0]).bare
        group = args[1]

        contact = roster[jid]
        if contact is None:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        new_groups = set(contact.groups)
        try:
            new_groups.remove('none')
        except KeyError:
            pass
        if group not in new_groups:
            self.core.information(_('JID not in group'), 'Error')
            return

        new_groups.remove(group)
        name = contact.name
        subscription = contact.subscription
        if self.core.xmpp.update_roster(jid, name=name, groups=new_groups, subscription=subscription):
            roster.update_contact_groups(jid)

    def command_remove(self, args):
        """
        Remove the specified JID from the roster. i.e. : unsubscribe
        from its presence, and cancel its subscription to our.
        """
        if args.strip():
            jid = safeJID(args.strip()).bare
        else:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            else:
                self.core.information('No roster item to remove')
                return
        del roster[jid]

    def command_import(self, arg):
        """
        Import the contacts
        """
        args = common.shell_split(arg)
        if len(args):
            if args[0].startswith('/'):
                filepath = args[0]
            else:
                filepath = path.join(getenv('HOME'), args[0])
        else:
            filepath = path.join(getenv('HOME'), 'poezio_contacts')
        if not path.isfile(filepath):
            self.core.information('The file %s does not exist' % filepath, 'Error')
            return
        try:
            handle = open(filepath, 'r', encoding='utf-8')
            lines = handle.readlines()
            handle.close()
        except IOError:
            self.core.information('Could not open %s' % filepath, 'Error')
            return
        for jid in lines:
            self.command_add(jid.lstrip('\n'))
        self.core.information('Contacts imported from %s' % filepath, 'Info')

    def command_export(self, arg):
        """
        Export the contacts
        """
        args = common.shell_split(arg)
        if len(args):
            if args[0].startswith('/'):
                filepath = args[0]
            else:
                filepath = path.join(getenv('HOME'), args[0])
        else:
            filepath = path.join(getenv('HOME'), 'poezio_contacts')
        if path.isfile(filepath):
            self.core.information('The file already exists', 'Error')
            return
        elif not path.isdir(path.dirname(filepath)):
            self.core.information('Parent directory not found', 'Error')
            return
        if roster.export(filepath):
            self.core.information('Contacts exported to %s' % filepath, 'Info')
        else:
            self.core.information('Failed to export contacts to %s' % filepath, 'Info')

    def completion_remove(self, the_input):
        """
        Completion for /remove
        """
        jids = [jid for jid in roster.jids()]
        return the_input.auto_completion(jids, '', quotify=False)

    def completion_name(self, the_input):
        text = the_input.get_text()
        n = len(common.shell_split(text))
        if text.endswith(' '):
            n += 1

        if n == 2:
            jids = [jid for jid in roster.jids()]
            return the_input.auto_completion(jids, '')
        return False

    def completion_groupadd(self, the_input):
        text = the_input.get_text()
        n = len(common.shell_split(text))
        if text.endswith(' '):
            n += 1

        if n == 2:
            jids = [jid for jid in roster.jids()]
            return the_input.auto_completion(jids, '')
        elif n == 3:
            groups = [group for group in roster.groups if group != 'none']
            return the_input.auto_completion(groups, '')
        return False

    def completion_groupmove(self, the_input):
        text = the_input.get_text()
        args = common.shell_split(text)
        n = len(args)
        if text.endswith(' '):
            n += 1

        if n == 2:
            jids = [jid for jid in roster.jids()]
            return the_input.auto_completion(jids, '')
        elif n == 3:
            contact = roster[args[1]]
            if not contact:
                return False
            groups = list(contact.groups)
            if 'none' in groups:
                groups.remove('none')
            return the_input.auto_completion(groups, '')
        elif n == 4:
            groups = [group for group in roster.groups]
            return the_input.auto_completion(groups, '')
        return False

    def completion_groupremove(self, the_input):
        text = the_input.get_text()
        args = common.shell_split(text)
        n = len(args)
        if text.endswith(' '):
            n += 1

        if n == 2:
            jids = [jid for jid in roster.jids()]
            return the_input.auto_completion(jids, '')
        elif n == 3:
            contact = roster[args[1]]
            if contact is None:
                return False
            groups = list(contact.groups)
            try:
                groups.remove('none')
            except ValueError:
                pass
            return the_input.auto_completion(groups, '')
        return False

    def completion_deny(self, the_input):
        """
        Complete the first argument from the list of the
        contact with ask=='subscribe'
        """
        jids = [str(contact.bare_jid) for contact in roster.contacts.values()\
             if contact.pending_in]
        return the_input.auto_completion(jids, '', quotify=False)

    def command_accept(self, arg):
        """
        Accept a JID from in roster. Authorize it AND subscribe to it
        """
        if not arg:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            else:
                self.core.information('No subscription to accept')
                return
        else:
            jid = safeJID(arg).bare
        nodepart = jid.user
        # crappy transports putting resources inside the node part
        if '\\2f' in nodepart:
            jid.user = nodepart.split('\\2f')[0]
        contact = roster[jid]
        if contact is None:
            return
        self.core.xmpp.send_presence(pto=jid, ptype='subscribed')
        self.core.xmpp.client_roster.send_last_presence()
        if contact.subscription in ('from', 'none') and not contact.pending_out:
            self.core.xmpp.send_presence(pto=jid, ptype='subscribe')

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s',self.__class__.__name__)
        self.v_separator.refresh()
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
        self.information_win.refresh()
        self.refresh_tab_win()
        self.input.refresh()

    def get_name(self):
        return self.name

    def on_input(self, key, raw):
        if key == '^M':
            selected_row = self.roster_win.get_selected_row()
        res = self.input.do_command(key, raw=raw)
        if res and not isinstance(self.input, windows.Input):
            return True
        elif res:
            return False
        if key == '^M':
            self.core.on_roster_enter_key(selected_row)
            return selected_row
        elif not raw and key in self.key_func:
            return self.key_func[key]()

    @refresh_wrapper.conditional
    def toggle_offline_show(self):
        """
        Show or hide offline contacts
        """
        option = 'roster_show_offline'
        if config.get(option, 'false') == 'false':
            config.set_and_save(option, 'true')
        else:
            config.set_and_save(option, 'false')
        return True

    def on_slash(self):
        """
        '/' is pressed, we enter "input mode"
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message, self.execute_slash_command)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.do_command("/") # we add the slash

    def reset_help_message(self, _=None):
        self.input = self.default_help_message
        if self.core.current_tab() is self:
            curses.curs_set(0)
            self.input.refresh()
            self.core.doupdate()
        return True

    def execute_slash_command(self, txt):
        if txt.startswith('/'):
            self.input.key_enter()
            self.execute_command(txt)
        return self.reset_help_message()

    def on_lose_focus(self):
        self.state = 'normal'

    def on_gain_focus(self):
        self.state = 'current'
        if isinstance(self.input, windows.HelpText):
            curses.curs_set(0)
        else:
            curses.curs_set(1)

    @refresh_wrapper.conditional
    def move_cursor_down(self):
        if isinstance(self.input, windows.Input) and not self.input.history_disabled:
            return
        return self.roster_win.move_cursor_down()

    @refresh_wrapper.conditional
    def move_cursor_up(self):
        if isinstance(self.input, windows.Input) and not self.input.history_disabled:
            return
        return self.roster_win.move_cursor_up()

    def move_cursor_to_prev_contact(self):
        self.roster_win.move_cursor_up()
        while not isinstance(self.roster_win.get_selected_row(), Contact):
            if not self.roster_win.move_cursor_up():
                break
        self.roster_win.refresh(roster)

    def move_cursor_to_next_contact(self):
        self.roster_win.move_cursor_down()
        while not isinstance(self.roster_win.get_selected_row(), Contact):
            if not self.roster_win.move_cursor_down():
                break
        self.roster_win.refresh(roster)

    def move_cursor_to_prev_group(self):
        self.roster_win.move_cursor_up()
        while not isinstance(self.roster_win.get_selected_row(), RosterGroup):
            if not self.roster_win.move_cursor_up():
                break
        self.roster_win.refresh(roster)

    def move_cursor_to_next_group(self):
        self.roster_win.move_cursor_down()
        while not isinstance(self.roster_win.get_selected_row(), RosterGroup):
            if not self.roster_win.move_cursor_down():
                break
        self.roster_win.refresh(roster)

    def on_scroll_down(self):
        return self.roster_win.move_cursor_down(self.height // 2)

    def on_scroll_up(self):
        return self.roster_win.move_cursor_up(self.height // 2)

    @refresh_wrapper.conditional
    def on_space(self):
        if isinstance(self.input, windows.Input):
            return
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, RosterGroup) or\
                isinstance(selected_row, Contact):
            selected_row.toggle_folded()
            return True
        return False

    def get_contact_version(self):
        """
        Show the versions of the resource(s) currently selected
        """
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, Contact):
            for resource in selected_row.resources:
                self.core.command_version(str(resource.jid))
        elif isinstance(selected_row, Resource):
            self.core.command_version(str(selected_row.jid))
        else:
            self.core.information('Nothing to get versions from', 'Info')

    def show_contact_info(self):
        """
        Show the contact info (resource number, status, presence, etc)
        when 'i' is pressed.
        """
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, Contact):
            cont = selected_row
            res = selected_row.get_highest_priority_resource()
            msg = 'Contact: %s (%s)\n%s connected resource%s\nCurrent status: %s' % (
                    cont.bare_jid,
                    res.presence if res else 'unavailable',
                    len(cont),
                    '' if len(cont) == 1 else 's',
                    res.status if res else '',)
        elif isinstance(selected_row, Resource):
            res = selected_row
            msg = 'Resource: %s (%s)\nCurrent status: %s\nPriority: %s' % (
                    res.jid,
                    res.presence,
                    res.status,
                    res.priority)
        elif isinstance(selected_row, RosterGroup):
            rg = selected_row
            msg = 'Group: %s [%s/%s] contacts online' % (
                    rg.name,
                    rg.get_nb_connected_contacts(),
                    len(rg),)
        else:
            msg = None
        if msg:
            self.core.information(msg, 'Info')

    def change_contact_name(self):
        """
        Auto-fill a /name command when 'n' is pressed
        """
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, Contact):
            jid = selected_row.bare_jid
        elif isinstance(selected_row, Resource):
            jid = safeJID(selected_row.jid).bare
        else:
            return
        self.on_slash()
        self.input.text = '/name "%s" ' % jid
        self.input.key_end()
        self.input.refresh()

    @refresh_wrapper.always
    def start_search(self):
        """
        Start the search. The input should appear with a short instruction
        in it.
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("[Search]", self.on_search_terminate, self.on_search_terminate, self.set_roster_filter)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.disable_history()
        return True

    @refresh_wrapper.always
    def start_search_slow(self):
        curses.curs_set(1)
        self.input = windows.CommandInput("[Search]", self.on_search_terminate, self.on_search_terminate, self.set_roster_filter_slow)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.disable_history()
        return True

    def set_roster_filter_slow(self, txt):
        roster.contact_filter = (jid_and_name_match_slow, txt)
        self.refresh()
        return False

    def set_roster_filter(self, txt):
        roster.contact_filter = (jid_and_name_match, txt)
        self.refresh()
        return False

    def on_search_terminate(self, txt):
        curses.curs_set(0)
        roster.contact_filter = None
        self.reset_help_message()
        return False

    def on_close(self):
        return

class ConversationTab(ChatTab):
    """
    The tab containg a normal conversation (not from a MUC)
    """
    plugin_commands = {}
    plugin_keys = {}
    additional_informations = {}
    message_type = 'chat'
    def __init__(self, jid):
        ChatTab.__init__(self, jid)
        self.state = 'normal'
        self.name = jid        # a conversation tab is linked to one specific full jid OR bare jid
        self.text_win = windows.TextWin()
        self._text_buffer.add_window(self.text_win)
        self.upper_bar = windows.ConversationStatusMessageWin()
        self.info_header = windows.ConversationInfoWin()
        self.input = windows.MessageInput()
        self.check_attention()
        # keys
        self.key_func['^I'] = self.completion
        # commands
        self.commands['unquery'] = (self.command_unquery, _("Usage: /unquery\nUnquery: Close the tab."), None)
        self.commands['close'] = (self.command_unquery, _("Usage: /close\Close: Close the tab."), None)
        self.commands['version'] = (self.command_version, _('Usage: /version\nVersion: Get the software version of the current interlocutor (usually its XMPP client and Operating System).'), None)
        self.commands['info'] = (self.command_info, _('Usage: /info\nInfo: Get the status of the contact.'), None)
        self.commands['activity'] = (self.command_activity, _('Usage: /activity [jid]\nActivity: Get the last activity of the given or the current contact.'), self.core.completion_activity)
        self.resize()
        self.update_commands()
        self.update_keys()

    @property
    def general_jid(self):
        return safeJID(self.get_name()).bare

    @staticmethod
    def add_information_element(plugin_name, callback):
        """
        Lets a plugin add its own information to the ConversationInfoWin
        """
        ConversationTab.additional_informations[plugin_name] = callback

    @staticmethod
    def remove_information_element(plugin_name):
        del ConversationTab.additional_informations[plugin_name]

    def completion(self):
        self.complete_commands(self.input)

    def command_say(self, line, attention=False, correct=False):
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = 'chat'
        msg['body'] = line
        # trigger the event BEFORE looking for colors.
        # and before displaying the message in the window
        # This lets a plugin insert \x19xxx} colors, that will
        # be converted in xhtml.
        self.core.events.trigger('conversation_say', msg, self)
        if correct:
            msg['replace']['id'] = self.last_sent_message['id']
            self.modify_message(line, self.last_sent_message['id'], msg['id'])
        else:
            self.add_message(msg['body'],
                    nickname=self.core.own_nick,
                    nick_color=get_theme().COLOR_OWN_NICK,
                    identifier=msg['id'])
        if msg['body'].find('\x19') != -1:
            msg['xhtml_im'] = xhtml.poezio_colors_to_html(msg['body'])
            msg['body'] = xhtml.clean_text(msg['body'])
        if config.get_by_tabname('send_chat_states', 'true', self.general_jid, True) == 'true' and self.remote_wants_chatstates is not False:
            needed = 'inactive' if self.inactive else 'active'
            msg['chat_state'] = needed
        if attention and self.remote_supports_attention:
            msg['attention'] = True
        self.core.events.trigger('conversation_say_after', msg, self)
        self.last_sent_message = msg
        msg.send()
        logger.log_message(safeJID(self.get_name()).bare, self.core.own_nick, line)
        self.cancel_paused_delay()
        self.text_win.refresh()
        self.input.refresh()

    def command_activity(self, arg):
        """
        /activity [jid]
        """
        if arg.strip():
            return self.core.command_activity(arg)

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
            msg = '\x19%s}The last activity of %s was %s ago%s'
            if not safeJID(from_).user:
                msg = '\x19%s}The uptime of %s is %s.' % (
                        get_theme().COLOR_INFORMATION_TEXT[0],
                        from_,
                        common.parse_secs_to_str(seconds))
            else:
                msg = '\x19%s}The last activity of %s was %s ago%s' % (
                    get_theme().COLOR_INFORMATION_TEXT[0],
                    from_,
                    common.parse_secs_to_str(seconds),
                    (' and his/her last status was %s' % status) if status else '',)
            self.add_message(msg)
            self.core.refresh_window()

        self.core.xmpp.plugin['xep_0012'].get_last_activity(self.general_jid, block=False, callback=callback)

    @refresh_wrapper.conditional
    def command_info(self, arg):
        contact = roster[self.get_name()]
        jid = safeJID(self.get_name())
        if jid.resource:
            resource = contact[jid.full]
        else:
            resource = contact.get_highest_priority_resource()
        if resource:
            self._text_buffer.add_message("\x19%(info_col)s}Status: %(status)s\x193}" % {'status': resource.status, 'info_col': get_theme().COLOR_INFORMATION_TEXT[0]}, None, None, None, None, None)
            return True

    def command_attention(self, message=''):
        if message is not '':
            self.command_say(message, attention=True)
        else:
            msg = self.core.xmpp.make_message(self.get_name())
            msg['type'] = 'chat'
            msg['attention'] = True
            msg.send()

    def check_attention(self):
        self.core.xmpp.plugin['xep_0030'].get_info(jid=self.get_name(), block=False, timeout=5, callback=self.on_attention_checked)

    def on_attention_checked(self, iq):
        if 'urn:xmpp:attention:0' in iq['disco_info'].get_features():
            self.core.information('Attention is supported', 'Info')
            self.remote_supports_attention = True
            self.commands['attention'] =  (self.command_attention, _('Usage: /attention [message]\nAttention: Require the attention of the contact. Can also send a message along with the attention.'), None)
        else:
            self.remote_supports_attention = False

    def command_unquery(self, arg):
        self.core.close_tab()

    def command_version(self, arg):
        """
        /version
        """
        def callback(res):
            if not res:
                return self.core.information('Could not get the software version from %s' % (jid,), 'Warning')
            version = '%s is running %s version %s on %s' % (jid,
                                                             res.get('name') or _('an unknown software'),
                                                             res.get('version') or _('unknown'),
                                                             res.get('os') or _('on an unknown platform'))
            self.core.information(version, 'Info')
        if arg:
            return self.core.command_version(arg)
        jid = safeJID(self.name)
        if not jid.resource:
            if jid in roster:
                resource = roster[jid].get_highest_priority_resource()
                jid = resource.jid if resource else jid
        self.core.xmpp.plugin['xep_0092'].get_version(jid, callback=callback)

    def resize(self):
        if self.core.information_win_size >= self.height-3 or not self.visible:
            return
        self.need_resize = False
        self.text_win.resize(self.height-3-self.core.information_win_size - Tab.tab_win_height(), self.width, 1, 0)
        self.text_win.rebuild_everything(self._text_buffer)
        self.upper_bar.resize(1, self.width, 0, 0)
        self.info_header.resize(1, self.width, self.height-2-self.core.information_win_size - Tab.tab_win_height(), 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s',self.__class__.__name__)
        self.text_win.refresh()
        self.upper_bar.refresh(self.get_name(), roster[self.get_name()])
        self.info_header.refresh(self.get_name(), roster[self.get_name()], self.text_win, self.chatstate, ConversationTab.additional_informations)
        self.info_win.refresh()
        self.refresh_tab_win()
        self.input.refresh()

    def refresh_info_header(self):
        self.info_header.refresh(self.get_name(), roster[self.get_name()] or safeJID(self.get_name()).user,
                self.text_win, self.chatstate, ConversationTab.additional_informations)
        self.input.refresh()

    def get_name(self):
        return self.name

    def get_nick(self):
        jid = safeJID(self.name)
        contact = roster[jid.bare]
        if contact:
            return contact.name or jid.user
        else:
            return jid.user

    def on_input(self, key, raw):
        if not raw and key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key, raw=raw)
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)
        return False

    def on_lose_focus(self):
        contact = roster[self.get_name()]
        jid = safeJID(self.get_name())
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        self.state = 'normal'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        if config.get_by_tabname('send_chat_states', 'true', self.general_jid, True) == 'true' and (not self.input.get_text() or not self.input.get_text().startswith('//')):
            if resource:
                self.send_chat_state('inactive')

    def on_gain_focus(self):
        contact = roster[self.get_name()]
        jid = safeJID(self.get_name())
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None

        self.state = 'current'
        curses.curs_set(1)
        if config.get_by_tabname('send_chat_states', 'true', self.general_jid, True) == 'true' and (not self.input.get_text() or not self.input.get_text().startswith('//')):
            if resource:
                self.send_chat_state('active')

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        self.text_win.resize(self.height-3-self.core.information_win_size - Tab.tab_win_height(), self.width, 1, 0)
        self.info_header.resize(1, self.width, self.height-2-self.core.information_win_size - Tab.tab_win_height(), 0)


    def get_text_window(self):
        return self.text_win

    def on_close(self):
        Tab.on_close(self)
        if config.get_by_tabname('send_chat_states', 'true', self.general_jid, True) == 'true':
            self.send_chat_state('gone')

    def modify_message(self, txt, old_id, new_id):
        self.log_message(txt, time, self.name)
        message = self._text_buffer.modify_message(txt, old_id, new_id, time=time)
        if message:
            self.text_win.modify_message(old_id, message)
            self.core.refresh_window()

    def add_message(self, txt, time=None, nickname=None, forced_user=None, nick_color=None, identifier=None):
        self._text_buffer.add_message(txt, time=time,
                nickname=nickname,
                nick_color=nick_color,
                history=None,
                user=forced_user,
                identifier=identifier)

    def matching_names(self):
        contact = roster[self.get_name()]
        res = [contact.bare_jid if contact else safeJID(self.get_name()).bare]
        if contact and contact.name:
            res.append(contact.name)
        return res

class MucListTab(Tab):
    """
    A tab listing rooms from a specific server, displaying various information,
    scrollable, and letting the user join them, etc
    """
    plugin_commands = {}
    plugin_keys = {}
    def __init__(self, server):
        Tab.__init__(self)
        self.state = 'normal'
        self.name = server
        self.upper_message = windows.Topic()
        self.upper_message.set_message('Chatroom list on server %s (Loading)' % self.name)
        columns = ('node-part', 'name', 'users')
        self.list_header = windows.ColumnHeaderWin(columns)
        self.listview = windows.ListWin(columns)
        self.default_help_message = windows.HelpText("“j”: join room.")
        self.input = self.default_help_message
        self.key_func["KEY_DOWN"] = self.move_cursor_down
        self.key_func["KEY_UP"] = self.move_cursor_up
        self.key_func['^I'] = self.completion
        self.key_func["/"] = self.on_slash
        self.key_func['j'] = self.join_selected
        self.key_func['J'] = self.join_selected_no_focus
        self.key_func['^M'] = self.join_selected
        self.key_func['KEY_LEFT'] = self.list_header.sel_column_left
        self.key_func['KEY_RIGHT'] = self.list_header.sel_column_right
        self.key_func[' '] = self.sort_by
        self.commands['close'] = (self.close, _("Usage: /close\nClose: Just close this tab."), None)
        self.resize()
        self.update_keys()
        self.update_commands()

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s',self.__class__.__name__)
        self.upper_message.refresh()
        self.list_header.refresh()
        self.listview.refresh()
        self.refresh_tab_win()
        self.input.refresh()
        self.update_commands()

    def resize(self):
        if not self.visible:
            return
        self.need_resize = False
        self.upper_message.resize(1, self.width, 0, 0)
        column_size = {'node-part': int(self.width*2/8) ,
                       'name': int(self.width*5/8),
                       'users': self.width-int(self.width*2/8)-int(self.width*5/8)}
        self.list_header.resize_columns(column_size)
        self.list_header.resize(1, self.width, 1, 0)
        self.listview.resize_columns(column_size)
        self.listview.resize(self.height-4, self.width, 2, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def on_slash(self):
        """
        '/' is pressed, activate the input
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message, self.execute_slash_command)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.do_command("/") # we add the slash

    def close(self, arg=None):
        self.input.on_delete()
        self.core.close_tab(self)

    def join_selected_no_focus(self):
        return

    def set_error(self, msg, code, body):
        """
        If there's an error (retrieving the values etc)
        """
        self._error_message = _('Error: %(code)s - %(msg)s: %(body)s') % {'msg':msg, 'body':body, 'code':code}
        self.upper_message.set_message(self._error_message)
        self.upper_message.refresh()
        curses.doupdate()

    def on_muc_list_item_received(self, iq):
        """
        Callback called when a disco#items result is received
        Used with command_list
        """
        if iq['type'] == 'error':
            self.set_error(iq['error']['type'], iq['error']['code'], iq['error']['text'])
            return
        items = [{'node-part': safeJID(item[0]).user if safeJID(item[0]).server == self.name else safeJID(item[0]).bare,
                  'jid': item[0],
                  'name': item[2] or '' ,'users': ''} for item in iq['disco_items'].get_items()]
        self.listview.add_lines(items)
        self.upper_message.set_message('Chatroom list on server %s' % self.name)
        if self.core.current_tab() is self:
            self.listview.refresh()
            self.upper_message.refresh()
        else:
            self.state = 'highlight'
            self.refresh_tab_win()
        curses.doupdate()

    def sort_by(self):
        if self.list_header.get_order():
            self.listview.sort_by_column(col_name=self.list_header.get_sel_column(),asc=False)
            self.list_header.set_order(False)
            self.list_header.refresh()
        else:
            self.listview.sort_by_column(col_name=self.list_header.get_sel_column(),asc=True)
            self.list_header.set_order(True)
            self.list_header.refresh()
        curses.doupdate()

    def join_selected(self):
        row = self.listview.get_selected_row()
        if not row:
            return
        self.core.command_join(row['jid'])

    def reset_help_message(self, _=None):
        curses.curs_set(0)
        self.input = self.default_help_message
        return True

    def execute_slash_command(self, txt):
        if txt.startswith('/'):
            self.input.key_enter()
            self.execute_command(txt)
        return self.reset_help_message()

    def get_name(self):
        return self.name

    def completion(self):
        if isinstance(self.input, windows.Input):
            self.complete_commands(self.input)

    def on_input(self, key, raw):
        res = self.input.do_command(key, raw=raw)
        if res:
            return True
        if not raw and key in self.key_func:
            return self.key_func[key]()

    def on_lose_focus(self):
        self.state = 'normal'

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(0)

    def on_scroll_up(self):
        return self.listview.scroll_up()

    def on_scroll_down(self):
        return self.listview.scroll_down()

    def move_cursor_up(self):
        self.listview.move_cursor_up()
        self.listview.refresh()
        self.core.doupdate()

    def move_cursor_down(self):
        self.listview.move_cursor_down()
        self.listview.refresh()
        self.core.doupdate()

class XMLTab(Tab):
    def __init__(self):
        Tab.__init__(self)
        self.state = 'normal'
        self.text_win = windows.TextWin()
        self.core.xml_buffer.add_window(self.text_win)
        self.default_help_message = windows.HelpText("/ to enter a command")
        self.commands['close'] = (self.close, _("Usage: /close\nClose: Just close this tab."), None)
        self.commands['clear'] = (self.command_clear, _("Usage: /clear\nClear: Clear the content of the current buffer."), None)
        self.commands['reset'] = (self.command_reset, _("Usage: /reset\nReset: Reset the stanza filter."), None)
        self.commands['filter_id'] = (self.command_filter_id, _("Usage: /filter_id <id>\nFilterId: Show only the stanzas with the id <id>."), None)
        self.commands['filter_xpath'] = (self.command_filter_xpath, _("Usage: /filter_xpath <xpath>\nFilterXPath: Show only the stanzas matching the xpath <xpath>."), None)
        self.commands['filter_xmlmask'] = (self.command_filter_xmlmask, _("Usage: /filter_xmlmask <xml mask>\nFilterXMLMask: Show only the stanzas matching the given xml mask."), None)
        self.input = self.default_help_message
        self.key_func['^T'] = self.close
        self.key_func['^I'] = self.completion
        self.key_func["KEY_DOWN"] = self.on_scroll_down
        self.key_func["KEY_UP"] = self.on_scroll_up
        self.key_func["^K"] = self.on_freeze
        self.key_func["/"] = self.on_slash
        self.resize()

    def on_freeze(self):
        self.text_win.toggle_lock()
        self.refresh()

    def command_filter_xmlmask(self, arg):
        """/filter_xmlmask <xml mask>"""
        try:
            handler = Callback('custom matcher', matcher.MatchXMLMask(arg),
                    self.core.incoming_stanza)
            self.core.xmpp.remove_handler('custom matcher')
            self.core.xmpp.register_handler(handler)
        except:
            self.core.information('Invalid XML Mask', 'Error')
            self.command_reset('')

    def command_filter_id(self, arg):
        """/filter_id <id>"""
        self.core.xmpp.remove_handler('custom matcher')
        handler = Callback('custom matcher', matcher.MatcherId(arg),
                self.core.incoming_stanza)
        self.core.xmpp.register_handler(handler)

    def command_filter_xpath(self, arg):
        """/filter_xpath <xpath>"""
        try:
            handler = Callback('custom matcher', matcher.MatchXPath(
                arg.replace('%n', self.core.xmpp.default_ns)),
                    self.core.incoming_stanza)
            self.core.xmpp.remove_handler('custom matcher')
            self.core.xmpp.register_handler(handler)
        except:
            self.core.information('Invalid XML Path', 'Error')
            self.command_reset('')

    def command_reset(self, arg):
        """/reset"""
        self.core.xmpp.remove_handler('custom matcher')
        self.core.xmpp.register_handler(self.core.all_stanzas)

    def on_slash(self):
        """
        '/' is pressed, activate the input
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message, self.execute_slash_command)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.do_command("/") # we add the slash

    def reset_help_message(self, _=None):
        if self.core.current_tab() is self:
            curses.curs_set(0)
        self.input = self.default_help_message
        self.input.refresh()
        self.core.doupdate()
        return True

    def on_scroll_up(self):
        return self.text_win.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        return self.text_win.scroll_down(self.text_win.height-1)

    def command_clear(self, args):
        """
        /clear
        """
        self.core.xml_buffer.messages = []
        self.text_win.rebuild_everything(self.core.xml_buffer)
        self.refresh()
        self.core.doupdate()

    def execute_slash_command(self, txt):
        if txt.startswith('/'):
            self.input.key_enter()
            self.execute_command(txt)
        return self.reset_help_message()

    def completion(self):
        if isinstance(self.input, windows.Input):
            self.complete_commands(self.input)

    def on_input(self, key, raw):
        res = self.input.do_command(key, raw=raw)
        if res:
            return True
        if not raw and key in self.key_func:
            return self.key_func[key]()

    def close(self, arg=None):
        self.core.close_tab()

    def resize(self):
        if not self.visible:
            return
        self.need_resize = False
        min = 1 if self.left_tab_win else 2
        self.text_win.resize(self.height-min, self.width, 0, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s',self.__class__.__name__)
        self.text_win.refresh()
        self.refresh_tab_win()
        self.input.refresh()

    def on_lose_focus(self):
        self.state = 'normal'

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(0)

    def on_close(self):
        self.core.xml_tab = False

class SimpleTextTab(Tab):
    """
    A very simple tab, with just a text displaying some
    information or whatever.
    For example used to display tracebacks
    """
    def __init__(self, text):
        Tab.__init__(self)
        self.state = 'normal'
        self.text_win = windows.SimpleTextWin(text)
        self.default_help_message = windows.HelpText("“Ctrl+q”: close")
        self.input = self.default_help_message
        self.key_func['^T'] = self.close
        self.key_func["/"] = self.on_slash
        self.resize()

    def on_slash(self):
        """
        '/' is pressed, activate the input
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message, self.execute_slash_command)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.do_command("/") # we add the slash

    def on_input(self, key, raw):
        res = self.input.do_command(key, raw=raw)
        if res:
            return True
        if not raw and key in self.key_func:
            return self.key_func[key]()

    def close(self):
        self.core.close_tab()

    def resize(self):
        if not self.visible:
            return
        self.need_resize = False
        self.text_win.resize(self.height-2, self.width, 0, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s',self.__class__.__name__)
        self.text_win.refresh()
        self.refresh_tab_win()
        self.input.refresh()

    def on_lose_focus(self):
        self.state = 'normal'

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(0)

def diffmatch(search, string):
    """
    Use difflib and a loop to check if search_pattern can
    be 'almost' found INSIDE a string.
    'almost' being defined by difflib
    """
    if len(search) > len(string):
        return False
    l = len(search)
    ratio = 0.7
    for i in range(len(string) - l + 1):
        if difflib.SequenceMatcher(None, search, string[i:i+l]).ratio() >= ratio:
            return True
    return False

def jid_and_name_match(contact, txt):
    """
    Match jid with text precisely
    """
    if not txt:
        return True
    if txt in safeJID(contact.bare_jid).user:
        return True
    if txt in contact.name:
        return True
    return False

def jid_and_name_match_slow(contact, txt):
    """
    A function used to know if a contact in the roster should
    be shown in the roster
    """
    if not txt:
        return True             # Everything matches when search is empty
    user = safeJID(contact.bare_jid).user
    if diffmatch(txt, user):
        return True
    if contact.name and diffmatch(txt, contact.name):
        return True
    return False
