# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
a Tab object is a way to organize various Windows (see windows.py)
around the screen at once.
A tab is then composed of multiple Buffer.
Each Tab object has different refresh() and resize() methods, defining how its
Windows are displayed, resized, etc
"""

MIN_WIDTH = 50
MIN_HEIGHT = 22

import logging
log = logging.getLogger(__name__)

from gettext import gettext as _

import windows
import curses
import difflib
import text_buffer
import string
import common
import core
import singleton
import xhtml
import weakref
import timed_events

import multiuserchat as muc

from theming import get_theme

from sleekxmpp.xmlstream.stanzabase import JID
from config import config
from roster import RosterGroup, roster
from contact import Contact, Resource
from user import User
from os import getenv, path
from logger import logger

from datetime import datetime, timedelta

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
        'message': lambda: get_theme().COLOR_TAB_NEW_MESSAGE,
        'highlight': lambda: get_theme().COLOR_TAB_HIGHLIGHT,
        'private': lambda: get_theme().COLOR_TAB_PRIVATE,
        'normal': lambda: get_theme().COLOR_TAB_NORMAL,
        'current': lambda: get_theme().COLOR_TAB_CURRENT,
#        'attention': lambda: get_theme().COLOR_TAB_ATTENTION,
    }

STATE_PRIORITY = {
        'normal': -1,
        'current': -1,
        'disconnected': 0,
        'message': 1,
        'highlight': 2,
        'private': 2,
#        'attention': 3
    }

class Tab(object):
    number = 0
    tab_core = None
    def __init__(self):
        self.input = None
        self._state = 'normal'
        self.need_resize = False
        self.nb = Tab.number
        Tab.number += 1
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
    def tab_win(self):
        if not Tab.tab_core:
            Tab.tab_core = singleton.Singleton(core.Core)
        return Tab.tab_core.tab_win

    @property
    def info_win(self):
        return self.core.information_win

    @property
    def color(self):
        return STATE_COLORS[self.state]()

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        if not value in STATE_COLORS:
            log.debug("WARNING: invalid value for tab state")
            return
        elif STATE_PRIORITY[value] < STATE_PRIORITY[self._state] and \
                value != 'current':
            log.debug("WARNING: did not set status because of lower priority")
            return
        self._state = value

    @staticmethod
    def resize(scr):
        Tab.size = (Tab.height, Tab.width) = scr.getmaxyx()
        if Tab.height < MIN_HEIGHT or Tab.width < MIN_WIDTH:
            Tab.visible = False
        else:
            Tab.visible = True

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
                if command_name in self.core.commands:
                    command = self.core.commands[command_name]
                elif command_name in self.commands:
                    command = self.commands[command_name]
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
                the_input.auto_completion(words, '')
                # Do not try to cycle command completion if there was only
                # one possibily. The next tab will complete the argument.
                # Otherwise we would need to add a useless space before being
                # able to complete the arguments.
                if len(the_input.hit_list) == 1:
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
            if command in self.commands: # check tab-specific commands
                self.commands[command][0](arg)
            elif command in self.core.commands: # check global commands
                self.core.commands[command][0](arg)
            else:
                low = command.lower()
                if low in self.commands:
                    self.commands[low][0](arg)
                elif low in self.core.commands:
                    self.core.commands[low][0](arg)
                else:
                    self.core.information(_("Unknown command (%s)") % (command), _('Error'))
            return True
        else:
            return False

    def refresh(self):
        """
        Called on each screen refresh (when something has changed)
        """
        raise NotImplementedError

    def get_name(self):
        """
        get the name of the tab
        """
        return self.__class__.__name__

    def get_text_window(self):
        """
        Returns the principal TextWin window, if there's one
        """
        return None

    def on_input(self, key):
        pass

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

    def add_message(self):
        """
        Adds a message in the tab.
        If the tab cannot add a message in itself (for example
        FormTab, where text is not intented to be appened), it returns False.
        If the tab can, it returns True
        """
        return False

    def on_scroll_down(self):
        """
        Defines what happens when we scrol down
        """
        pass

    def on_scroll_up(self):
        """
        Defines what happens when we scrol down
        """
        pass

    def on_info_win_size_changed(self):
        """
        Called when the window with the informations is resized
        """
        pass

    def just_before_refresh(self):
        """
        Method called just before the screen refresh.
        Particularly useful to move the cursor at the
        correct position.
        """
        pass

    def on_close(self):
        """
        Called when the tab is to be closed
        """
        if self.input:
            self.input.on_delete()

    def __del__(self):
        log.debug('------ Closing tab %s' % self.__class__.__name__)

class ChatTab(Tab):
    """
    A tab containing a chat of any type.
    Just use this class instead of Tab if the tab needs a recent-words completion
    Also, ^M is already bound to on_enter
    And also, add the /say command
    """
    def __init__(self, room):
        Tab.__init__(self)
        self._room = room
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
        self.key_func['M-v'] = self.move_separator
        self.key_func['M-/'] = self.last_words_completion
        self.key_func['^M'] = self.on_enter
        self.commands['say'] =  (self.command_say,
                                 _("""Usage: /say <message>\nSay: Just send the message.
                                        Useful if you want your message to begin with a '/'"""), None)
        self.chat_state = None

    def last_words_completion(self):
        """
        Complete the input with words recently said
        """
        # build the list of the recent words
        char_we_dont_want = string.punctuation+' '
        words = list()
        for msg in self._room.messages[:-40:-1]:
            if not msg:
                continue
            txt = xhtml.clean_text(msg.txt)
            for char in char_we_dont_want:
                txt = txt.replace(char, ' ')
            for word in txt.split():
                if len(word) >= 4 and word not in words:
                    words.append(word)
        self.input.auto_completion(words, ' ')

    def on_enter(self):
        txt = self.input.key_enter()
        if txt:
            clean_text = xhtml.clean_text_simple(txt)
            if not self.execute_command(clean_text):
                if txt.startswith('//'):
                    txt = txt[1:]
                self.command_say(txt)
        self.cancel_paused_delay()

    def send_chat_state(self, state, always_send=False):
        """
        Send an empty chatstate message
        """
        if not isinstance(self, MucTab) or self.get_room().joined:
            if state in ('active', 'inactive', 'gone') and self.core.status.show in ('xa', 'away') and not always_send:
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
        if config.get('send_chat_states', 'true') == 'true' and self.remote_wants_chatstates:
            needed = 'inactive' if self.core.status.show in ('xa', 'away') else 'active'
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
        if config.get('send_chat_states', 'true') != 'true':
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

    def move_separator(self):
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator()
        self.text_win.refresh(self._room)
        self.input.refresh()

    def command_say(self, line):
        raise NotImplementedError

class MucTab(ChatTab):
    """
    The tab containing a multi-user-chat room.
    It contains an userlist, an input, a topic, an information and a chat zone
    """
    message_type = 'groupchat'
    def __init__(self, room):
        ChatTab.__init__(self, room)
        self.remote_wants_chatstates = True
        # We send active, composing and paused states to the MUC because
        # the chatstate may or may not be filtered by the MUC,
        # that’s not our problem.
        self.topic_win = windows.Topic()
        self.text_win = windows.TextWin()
        room.add_window(self.text_win)
        self.v_separator = windows.VerticalSeparator()
        self.user_win = windows.UserList()
        self.info_header = windows.MucInfoWin()
        self.input = windows.MessageInput()
        self.ignores = []       # set of Users
        # keys
        self.key_func['^I'] = self.completion
        self.key_func['M-u'] = self.scroll_user_list_down
        self.key_func['M-y'] = self.scroll_user_list_up
        # commands
        self.commands['ignore'] = (self.command_ignore, _("Usage: /ignore <nickname> \nIgnore: Ignore a specified nickname."), None)
        self.commands['unignore'] = (self.command_unignore, _("Usage: /unignore <nickname>\nUnignore: Remove the specified nickname from the ignore list."), self.completion_unignore)
        self.commands['kick'] =  (self.command_kick, _("Usage: /kick <nick> [reason]\nKick: Kick the user with the specified nickname. You also can give an optional reason."), None)
        self.commands['role'] =  (self.command_role, _("Usage: /role <nick> <role> [reason]\nRole: Set the role of an user. Roles can be: none, visitor, participant, moderator. You also can give an optional reason."), None)
        self.commands['affiliation'] =  (self.command_affiliation, _("Usage: /affiliation <nick> <affiliation> [reason]\nAffiliation: Set the affiliation of an user. Affiliations can be: outcast, none, member, admin, owner. You also can give an optional reason."), None)
        self.commands['topic'] = (self.command_topic, _("Usage: /topic <subject>\nTopic: Change the subject of the room"), self.completion_topic)
        self.commands['query'] = (self.command_query, _('Usage: /query <nick> [message]\nQuery: Open a private conversation with <nick>. This nick has to be present in the room you\'re currently in. If you specified a message after the nickname, it will immediately be sent to this user'), None)
        self.commands['part'] = (self.command_part, _("Usage: /part [message]\nPart: disconnect from a room. You can specify an optional message."), None)
        self.commands['close'] = (self.command_close, _("Usage: /close [message]\nClose: disconnect from a room and close the tab. You can specify an optional message if you are still connected."), None)
        self.commands['nick'] = (self.command_nick, _("Usage: /nick <nickname>\nNick: Change your nickname in the current room"), None)
        self.commands['recolor'] = (self.command_recolor, _('Usage: /recolor\nRecolor: Re-assign a color to all participants of the current room, based on the last time they talked. Use this if the participants currently talking have too many identical colors.'), None)
        self.commands['cycle'] = (self.command_cycle, _('Usage: /cycle [message]\nCycle: Leaves the current room and rejoin it immediately'), None)
        self.commands['info'] = (self.command_info, _('Usage: /info <nickname>\nInfo: Display some information about the user in the MUC: his/here role, affiliation, status and status message.'), None)
        self.commands['configure'] = (self.command_configure, _('Usage: /configure\nConfigure: Configure the current room, through a form.'), None)
        self.commands['version'] = (self.command_version, _('Usage: /version <jid or nick>\nVersion: get the software version of the given JID or nick in room (usually its XMPP client and Operating System)'), None)
        self.commands['names'] = (self.command_names, _('Usage: /names\nNames: get the list of the users in the room, and the list of the people assuming the different roles.'), None)
        self.commands['clear'] =  (self.command_clear,
                                 _("""Usage: /clear\nClear: clears the current buffer'"""), None)
        self.resize()

    def scroll_user_list_up(self):
        self.user_win.scroll_up()
        self.user_win.refresh(self._room.users)
        self.input.refresh()

    def scroll_user_list_down(self):
        self.user_win.scroll_down()
        self.user_win.refresh(self._room.users)
        self.input.refresh()

    def command_info(self, arg):
        args = common.shell_split(arg)
        if len(args) != 1:
            return self.core.information("Info command takes only 1 argument")
        user = self.get_room().get_user_by_name(args[0])
        if not user:
            return self.core.information("Unknown user: %s" % args[0])
        info = '%s%s: show: %s, affiliation: %s, role: %s%s' % (args[0],
                                                                ' (%s)' % user.jid if user.jid else '',
                                                                user.show or 'Available',
                                                                user.role or 'None',
                                                                user.affiliation or 'None',
                                                                '\n%s' % user.status if user.status else '')
        self.core.information(info, 'Info')

    def command_configure(self, arg):
        form = self.core.xmpp.plugin['xep_0045'].getRoomForm(self.get_name())
        if not form:
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

    def command_clear(self, args):
        """
        /clear
        """
        self._room.messages = []
        self.text_win.rebuild_everything(self._room)
        self.refresh()
        self.core.doupdate()

    def command_cycle(self, arg):
        if self.get_room().joined:
            muc.leave_groupchat(self.core.xmpp, self.get_name(), self.get_room().own_nick, arg)
        self.get_room().disconnect()
        self.core.disable_private_tabs(self.get_room().name)
        self.core.command_join('"/%s"' % self.core.get_bookmark_nickname(self.get_room().name), '0')
        self.user_win.pos = 0

    def command_recolor(self, arg):
        """
        Re-assign color to the participants of the room
        """
        room = self.get_room()
        compare_users = lambda x: x.last_talked
        users = list(room.users)
        # search our own user, to remove it from the room
        for user in users:
            if user.nick == room.own_nick:
                users.remove(user)
        nb_color = len(get_theme().LIST_COLOR_NICKNAMES)
        for i, user in enumerate(sorted(users, key=compare_users, reverse=True)):
            user.color = get_theme().LIST_COLOR_NICKNAMES[i % nb_color]
        self.text_win.rebuild_everything(self._room)
        self.text_win.refresh(self._room)
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

        args = common.shell_split(arg)
        if len(args) < 1:
            return
        if args[0] in [user.nick for user in self.get_room().users]:
            jid = self._room.name + '/' + args[0]
        else:
            jid = args[0]
        self.core.xmpp.plugin['xep_0092'].get_version(jid, callback=callback)

    def command_nick(self, arg):
        """
        /nick <nickname>
        """
        args = common.shell_split(arg)
        if len(args) != 1:
            return
        nick = args[0]
        room = self.get_room()
        if not room.joined:
            return
        current_status = self.core.get_status()
        muc.change_nick(self.core.xmpp, room.name, nick, current_status.message, current_status.show)

    def command_part(self, arg):
        """
        /part [msg]
        """
        args = arg.split()
        room = self.get_room()
        if len(args):
            msg = ' '.join(args)
        else:
            msg = None
        if self.get_room().joined:
            muc.leave_groupchat(self.core.xmpp, room.name, room.own_nick, arg)
            self.get_room().joined = False
            self.get_room().add_message(_("\x195}You left the chatroom\x193}"))
            self.refresh()
            self.core.doupdate()
        self.core.disable_private_tabs(self.get_room().name)

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
        room = self.get_room()
        r = None
        for user in room.users:
            if user.nick == nick:
                r = self.core.open_private_window(room.name, user.nick)
        if r and len(args) > 1:
            msg = arg[len(nick)+1:]
            self.core.current_tab().command_say(msg)
        if not r:
            self.core.information(_("Cannot find user: %s" % nick), 'Error')

    def command_topic(self, arg):
        """
        /topic [new topic]
        """
        if not arg.strip():
            self.core.add_message_to_text_buffer(self.get_room(),
                                                 _("The subject of the room is: %s") % self.get_room().topic)
            self.text_win.refresh(self.get_room())
            self.input.refresh()
            return
        subject = arg
        muc.change_subject(self.core.xmpp, self.get_room().name, subject)

    def command_names(self, arg=None):
        """
        /names
        """
        room = self.get_room()
        if not room.joined:
            return
        users, visitors, moderators, participants, others = [], [], [], [], []
        for user in room.users:
            if user.role == 'visitor':
                visitors.append(user.nick)
            elif user.role == 'participant':
                participants.append(user.nick)
            elif user.role == 'moderator':
                moderators.append(user.nick)
            else:
                others.append(user.nick)
            users.append(user.nick)

        message = ''
        roles = (('Users', users), ('Visitors', visitors), ('Participants', participants), ('Moderators', moderators), ('Others', others))
        for role in roles:
            if role[1]:
                role[1].sort()
                message += '%s: %i\n    ' % (role[0], len(role[1]))
                last = role[1].pop()
                for item in role[1]:
                    message += '%s, ' % item
                message += '%s\n' % last

        self.core.add_message_to_text_buffer(room, message)
        self.text_win.refresh(self.get_room())
        self.input.refresh()

    def completion_topic(self, the_input):
        current_topic = self.get_room().topic
        return the_input.auto_completion([current_topic], '')

    def command_kick(self, arg):
        """
        /kick <nick> [reason]
        """
        args = common.shell_split(arg)
        if not len(args):
            self.core.command_help('kick')
        else:
            self.command_role(arg+ ' none')

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
        if not self.get_room().joined or \
                not role in ('none', 'visitor', 'participant', 'moderator'):
            return
        res = muc.set_user_role(self.core.xmpp, self.get_name(), nick, reason, role)
        if res['type'] == 'error':
            self.core.room_error(res, self.get_name())

    def command_affiliation(self, arg):
        """
        /affiliation <nick> <role> [reason]
        Changes the affiliation of an user
        roles can be: none, visitor, participant, moderator
        """
        args = common.shell_split(arg)
        if len(args) < 2:
            self.core.command_help('role')
            return
        nick, affiliation = args[0],args[1]
        if len(args) > 2:
            reason = ' '.join(args[2:])
        else:
            reason = ''
        if not self.get_room().joined or \
                not affiliation in ('none', 'member', 'admin', 'owner'):
#                replace this ↑ with this ↓ when the ban list support is done
#                not affiliation in ('outcast', 'none', 'member', 'admin', 'owner'):
            return
        res = muc.set_user_affiliation(self.core.xmpp, self.get_name(), nick, reason, affiliation)
        if res['type'] == 'error':
            self.core.room_error(res, self.get_name())

    def command_say(self, line):
        needed = 'inactive' if self.core.status.show in ('xa', 'away') else 'active'
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = 'groupchat'
        if line.find('\x19') == -1:
            msg['body'] = line
        else:
            msg['body'] = xhtml.clean_text_simple(line)
            msg['xhtml_im'] = xhtml.poezio_colors_to_html(line)
        if config.get('send_chat_states', 'true') == 'true' and self.remote_wants_chatstates is not False:
            msg['chat_state'] = needed
        self.cancel_paused_delay()
        msg.send()
        self.chat_state = needed

    def command_ignore(self, arg):
        """
        /ignore <nick>
        """
        args = common.shell_split(arg)
        if len(args) != 1:
            self.core.command_help('ignore')
            return
        nick = args[0]
        user = self._room.get_user_by_name(nick)
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
        args = common.shell_split(arg)
        if len(args) != 1:
            self.core.command_help('unignore')
            return
        nick = args[0]
        user = self._room.get_user_by_name(nick)
        if not user:
            self.core.information(_('%s is not in the room') % nick)
        elif user not in self.ignores:
            self.core.information(_('%s is not ignored') % nick)
        else:
            self.ignores.remove(user)
            self.core.information(_('%s is now unignored') % nick)

    def completion_unignore(self, the_input):
        return the_input.auto_completion([user.nick for user in self.ignores], ' ')

    def resize(self):
        """
        Resize the whole window. i.e. all its sub-windows
        """
        if not self.visible:
            return
        self.need_resize = False
        text_width = (self.width//10)*9
        self.topic_win.resize(1, self.width, 0, 0)
        self.v_separator.resize(self.height-3, 1, 1, 9*(self.width//10))
        self.text_win.resize(self.height-4-self.core.information_win_size, text_width, 1, 0)
        self.text_win.rebuild_everything(self._room)
        self.user_win.resize(self.height-3-self.core.information_win_size-1, self.width-text_width-1, 1, text_width+1)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s'%self.__class__.__name__)
        self.topic_win.refresh(self._room.get_single_line_topic())
        self.text_win.refresh(self._room)
        self.v_separator.refresh()
        self.user_win.refresh(self._room.users)
        self.info_header.refresh(self._room, self.text_win)
        self.tab_win.refresh()
        self.info_win.refresh(self.core.informations)
        self.input.refresh()

    def on_input(self, key):
        if key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key)
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
        word_list = [user.nick for user in sorted(self._room.users, key=compare_users, reverse=True)\
                         if user.nick != self._room.own_nick]
        after = config.get('after_completion', ',')+" "
        input_pos = self.input.pos + self.input.line_pos
        if ' ' not in self.input.get_text()[:input_pos] or (self.input.last_completion and\
                     self.input.get_text()[:input_pos] == self.input.last_completion + after):
            add_after = after
        else:
            add_after = ' '
        self.input.auto_completion(word_list, add_after)
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)

    def get_name(self):
        return self._room.name

    def get_text_window(self):
        return self.text_win

    def get_room(self):
        return self._room

    @property
    def color(self):
        return STATE_COLORS[self._room.state]()

    def on_lose_focus(self):
        self._room.state = 'normal'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator()
        if config.get('send_chat_states', 'true') == 'true' and not self.input.get_text():
            self.send_chat_state('inactive')

    def on_gain_focus(self):
        self._room.state = 'current'
        if self.text_win.built_lines and self.text_win.built_lines[-1] is None:
            self.text_win.remove_line_separator()
        curses.curs_set(1)
        if self.get_room().joined and config.get('send_chat_states', 'true') == 'true' and not self.input.get_text():
            self.send_chat_state('active')

    def on_scroll_up(self):
        self.text_win.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self.text_win.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        text_width = (self.width//10)*9
        self.text_win.resize(self.height-4-self.core.information_win_size, text_width, 1, 0)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0)
        self.user_win.resize(self.height-3-self.core.information_win_size-1, self.width-text_width-1, 1, text_width+1)

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
        room = self.get_room()
        if not room.joined:     # user in the room BEFORE us.
            # ignore redondant presence message, see bug #1509
            if from_nick not in [user.nick for user in room.users] and typ != "unavailable":
                new_user = User(from_nick, affiliation, show, status, role, jid)
                room.users.append(new_user)
                if from_nick == room.own_nick:
                    room.joined = True
                    if self.core.current_tab() == self and self.core.status.show not in ('xa', 'away'):
                        self.send_chat_state('active')
                    new_user.color = get_theme().COLOR_OWN_NICK
                    room.add_message(_("\x195}Your nickname is \x193}%s") % (from_nick))
                    if '170' in status_codes:
                        room.add_message('\x191}Warning: \x195}this room is publicly logged')
        else:
            change_nick = '303' in status_codes
            kick = '307' in status_codes and typ == 'unavailable'
            ban = '301' in status_codes and typ == 'unavailable'
            user = room.get_user_by_name(from_nick)
            # New user
            if not user:
                self.on_user_join(room, from_nick, affiliation, show, status, role, jid)
            # nick change
            elif change_nick:
                self.on_user_nick_change(room, presence, user, from_nick, from_room)
            elif ban:
                self.on_user_banned(room, presence, user, from_nick)
            # kick
            elif kick:
                self.on_user_kicked(room, presence, user, from_nick)
            # user quit
            elif typ == 'unavailable':
                self.on_user_leave_groupchat(room, user, jid, status, from_nick, from_room)
            # status change
            else:
                self.on_user_change_status(room, user, from_nick, from_room, affiliation, role, show, status)
        if self.core.current_tab() is self:
            self.text_win.refresh(self._room)
            self.user_win.refresh(self._room.users)
            self.info_header.refresh(self._room, self.text_win)
            self.input.refresh()
            self.core.doupdate()

    def on_user_join(self, room, from_nick, affiliation, show, status, role, jid):
        """
        When a new user joins the groupchat
        """
        user = User(from_nick, affiliation,
                    show, status, role, jid)
        room.users.append(user)
        hide_exit_join = config.get('hide_exit_join', -1)
        if hide_exit_join != 0:
            color = user.color[0] if config.get('display_user_color_in_join_part', '') == 'true' else 3
            if not jid.full:
                room.add_message('\x194}%(spec)s \x19%(color)d}%(nick)s\x195} joined the room' % {'nick':from_nick, 'color':color, 'spec':get_theme().CHAR_JOIN})
            else:
                room.add_message('\x194}%(spec)s \x19%(color)d}%(nick)s \x195}(\x194}%(jid)s\x195}) joined the room' % {'spec':get_theme().CHAR_JOIN, 'nick':from_nick, 'color':color, 'jid':jid.full})
        self.core.on_user_rejoined_private_conversation(room.name, from_nick)


    def on_user_nick_change(self, room, presence, user, from_nick, from_room):
        new_nick = presence.find('{%s}x/{%s}item' % (NS_MUC_USER, NS_MUC_USER)).attrib['nick']
        if user.nick == room.own_nick:
            room.own_nick = new_nick
            # also change our nick in all private discussion of this room
            for _tab in self.core.tabs:
                if isinstance(_tab, PrivateTab) and JID(_tab.get_name()).bare == room.name:
                    _tab.get_room().own_nick = new_nick
        user.change_nick(new_nick)
        color = user.color[0] if config.get('display_user_color_in_join_part', '') == 'true' else 3
        room.add_message('\x19%(color)d}%(old)s\x195} is now known as \x19%(color)d}%(new)s' % {'old':from_nick, 'new':new_nick, 'color':color})
        # rename the private tabs if needed
        self.core.rename_private_tabs(room.name, from_nick, new_nick)

    def on_user_banned(self, room, presence, user, from_nick):
        """
        When someone is banned from a muc
        """
        room.users.remove(user)
        by = presence.find('{%s}x/{%s}item/{%s}actor' % (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        reason = presence.find('{%s}x/{%s}item/{%s}reason' % (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        by = by.attrib['jid'] if by is not None else None
        if from_nick == room.own_nick: # we are banned
            room.disconnect()
            self.core.disable_private_tabs(room.name)
            self.tab_win.refresh()
            self.core.doupdate()
            if by:
                kick_msg = _('\x191}%(spec)s \x193}You\x195} have been banned by \x194}%(by)s') % {'spec': get_theme().CHAR_KICK, 'by':by}
            else:
                kick_msg = _('\x191}%(spec)s \x193}You\x195} have been banned.') % {'spec':get_theme().CHAR_KICK}
        else:
            color = user.color[0] if config.get('display_user_color_in_join_part', '') == 'true' else 3
            if by:
                kick_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x195} has been banned by \x194}%(by)s') % {'spec':get_theme().CHAR_KICK, 'nick':from_nick, 'color':color, 'by':by}
            else:
                kick_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x195} has been banned') % {'spec':get_theme().CHAR_KICK, 'nick':from_nick.replace('"', '\\"'), 'color':color}
        if reason is not None and reason.text:
            kick_msg += _('\x195} Reason: \x196}%(reason)s\x195}') % {'reason': reason.text}
        room.add_message(kick_msg)

    def on_user_kicked(self, room, presence, user, from_nick):
        """
        When someone is kicked from a muc
        """
        room.users.remove(user)
        by = presence.find('{%s}x/{%s}item/{%s}actor' % (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        reason = presence.find('{%s}x/{%s}item/{%s}reason' % (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        by = by.attrib['jid'] if by is not None else None
        if from_nick == room.own_nick: # we are kicked
            room.disconnect()
            self.core.disable_private_tabs(room.name)
            self.tab_win.refresh()
            self.core.doupdate()
            if by:
                kick_msg = _('\x191}%(spec)s \x193}You\x195} have been kicked by \x193}%(by)s') % {'spec': get_theme().CHAR_KICK, 'by':by}
            else:
                kick_msg = _('\x191}%(spec)s \x193}You\x195} have been kicked.') % {'spec':get_theme().CHAR_KICK}
            # try to auto-rejoin
            if config.get('autorejoin', 'false') == 'true':
                muc.join_groupchat(self.core.xmpp, room.name, room.own_nick)
        else:
            color = user.color[0] if config.get('display_user_color_in_join_part', '') == 'true' else 3
            if by:
                kick_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x195} has been kicked by \x193}%(by)s') % {'spec':get_theme().CHAR_KICK.replace('"', '\\"'), 'nick':from_nick.replace('"', '\\"'), 'color':color, 'by':by.replace('"', '\\"')}
            else:
                kick_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x195} has been kicked') % {'spec':get_theme().CHAR_KICK, 'nick':from_nick.replace('"', '\\"'), 'color':color}
        if reason is not None and reason.text:
            kick_msg += _('\x195} Reason: \x196}%(reason)s') % {'reason': reason.text}
        room.add_message(kick_msg)

    def on_user_leave_groupchat(self, room, user, jid, status, from_nick, from_room):
        """
        When an user leaves a groupchat
        """
        room.users.remove(user)
        if room.own_nick == user.nick:
            # We are now out of the room. Happens with some buggy (? not sure) servers
            room.disconnect()
            self.core.disable_private_tabs(from_room)
            self.tab_win.refresh()
            self.core.doupdate()
        hide_exit_join = config.get('hide_exit_join', -1) if config.get('hide_exit_join', -1) >= -1 else -1
        if hide_exit_join == -1 or user.has_talked_since(hide_exit_join):
            log.debug("\n\nALLO: USERCOLOR: %s\n\n" % user.color.__repr__())
            color = user.color[0] if config.get('display_user_color_in_join_part', '') == 'true' else 3
            if not jid.full:
                leave_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x195} has left the room') % {'nick':from_nick, 'color':color, 'spec':get_theme().CHAR_QUIT}
            else:
                leave_msg = _('\x191}%(spec)s \x19%(color)d}%(nick)s\x195} (\x194}%(jid)s\x195}) has left the room') % {'spec':get_theme().CHAR_QUIT, 'nick':from_nick, 'color':color, 'jid':jid.full}
            if status:
                leave_msg += ' (%s)' % status
            room.add_message(leave_msg)
            self.core.refresh_window()
        self.core.on_user_left_private_conversation(from_room, from_nick, status)

    def on_user_change_status(self, room, user, from_nick, from_room, affiliation, role, show, status):
        """
        When an user changes her status
        """
        # build the message
        display_message = False # flag to know if something significant enough
        # to be displayed has changed
        color = user.color[0] if config.get('display_user_color_in_join_part', '') == 'true' else 3
        if from_nick == room.own_nick:
            msg = _('\x193}You\x195} changed: ')
        else:
            msg = _('\x19%(color)d}%(nick)s\x195} changed: ') % {'nick': from_nick.replace('"', '\\"'), 'color': color}
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
            if not status and show in SHOW_NAME:
                msg += _('show: %s, ') % SHOW_NAME[show]
            else:
                msg += _('status: %s, ') % status
            display_message = True

        if not display_message:
            return
        msg = msg[:-2] # remove the last ", "
        hide_status_change = config.get('hide_status_change', -1)
        if hide_status_change < -1:
            hide_status_change = -1
        if (hide_status_change == -1 or \
                user.has_talked_since(hide_status_change) or\
                user.nick == room.own_nick)\
                and\
                (affiliation != user.affiliation or\
                    role != user.role or\
                    show != user.show or\
                    status != user.status):
            # display the message in the room
            room.add_message(msg)
        self.core.on_user_changed_status_in_private('%s/%s' % (from_room, from_nick), msg)
        # finally, effectively change the user status
        user.update(affiliation, show, status, role)

class PrivateTab(ChatTab):
    """
    The tab containg a private conversation (someone from a MUC)
    """
    message_type = 'chat'
    def __init__(self, room):
        ChatTab.__init__(self, room)
        self.text_win = windows.TextWin()
        room.add_window(self.text_win)
        self.info_header = windows.PrivateInfoWin()
        self.input = windows.MessageInput()
        # keys
        self.key_func['^I'] = self.completion
        # commands
        self.commands['info'] = (self.command_info, _('Usage: /info\nInfo: Display some information about the user in the MUC: '), None)
        self.commands['unquery'] = (self.command_unquery, _("Usage: /unquery\nUnquery: close the tab"), None)
        self.commands['close'] = (self.command_unquery, _("Usage: /close\nClose: close the tab"), None)
        self.commands['version'] = (self.command_version, _('Usage: /version\nVersion: get the software version of the current interlocutor (usually its XMPP client and Operating System)'), None)
        self.resize()
        self.parent_muc = self.core.get_tab_by_name(JID(room.name).bare, MucTab)
        self.on = True

    def completion(self):
        self.complete_commands(self.input)

    def command_say(self, line):
        if not self.on:
            return
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = 'chat'
        if line.find('\x19') == -1:
            msg['body'] = line
        else:
            msg['body'] = xhtml.clean_text_simple(line)
            msg['xhtml_im'] = xhtml.poezio_colors_to_html(line)
        if config.get('send_chat_states', 'true') == 'true' and self.remote_wants_chatstates is not False:
            needed = 'inactive' if self.core.status.show in ('xa', 'away') else 'active'
            msg['chat_state'] = needed
        msg.send()
        self.core.add_message_to_text_buffer(self.get_room(), line, None, self.core.own_nick or self.get_room().own_nick)
        logger.log_message(JID(self.get_name()).bare, self.core.own_nick, line)
        self.cancel_paused_delay()
        self.text_win.refresh(self._room)
        self.input.refresh()

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
        jid = self.get_room().name
        self.core.xmpp.plugin['xep_0092'].get_version(jid, callback=callback)

    def command_info(self, arg):
        """
        /info
        """
        if arg:
            self.parent_muc.command_info(arg)
        else:
            user = JID(self.get_room().name).resource
            self.parent_muc.command_info(user)

    def resize(self):
        if self.core.information_win_size >= self.height-3 or not self.visible:
            return
        self.need_resize = False
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0)
        self.text_win.rebuild_everything(self._room)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s'%self.__class__.__name__)
        self.text_win.refresh(self._room)
        self.info_header.refresh(self._room, self.text_win, self.chatstate)
        self.info_win.refresh(self.core.informations)
        self.tab_win.refresh()
        self.input.refresh()

    def refresh_info_header(self):
        self.info_header.refresh(self._room, self.text_win, self.chatstate)
        self.input.refresh()

    @property
    def color(self):
        if self._room.state == 'normal' or\
                self._room.state == 'current':
            return STATE_COLORS[self._room.state]()
        return get_theme().COLOR_TAB_PRIVATE

    def get_name(self):
        return self._room.name

    def on_input(self, key):
        if key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key)
        if not self.on:
            return False
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        tab = self.core.get_tab_by_name(JID(self.get_room().name).bare, MucTab)
        if tab and tab.get_room().joined:
            self.send_composing_chat_state(empty_after)
        return False

    def on_lose_focus(self):
        self._room.state = 'normal'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator()
        if self.get_room().joined and config.get('send_chat_states', 'true') == 'true' and not self.input.get_text():
            self.send_chat_state('inactive')

    def on_gain_focus(self):
        self._room.state = 'CURRENT'
        curses.curs_set(1)
        if self.get_room().joined and config.get('send_chat_states', 'true') == 'true' and not self.input.get_text():
            self.send_chat_state('active')

    def on_scroll_up(self):
        self.text_win.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self.text_win.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0)

    def get_room(self):
        return self._room

    def get_text_window(self):
        return self.text_win

    def rename_user(self, old_nick, new_nick):
        """
        The user changed her nick in the corresponding muc: update the tab’s name and
        display a message.
        """
        self.get_room().add_message(_('"[%(old_nick)s]" is now known as "[%(new_nick)s]"') % {'old_nick':old_nick.replace('"', '\\"'), 'new_nick':new_nick.replace('"', '\\"')})
        new_jid = JID(self.get_room().name).bare+'/'+new_nick
        self.get_room().name = new_jid

    def user_left(self, status_message, from_nick):
        """
        The user left the associated MUC
        """
        self.deactivate()
        if not status_message:
            self.get_room().add_message(_('\x191}%(spec)s \x193}%(nick)s\x195} has left the room') % {'nick':from_nick.replace('"', '\\"'), 'spec':get_theme().CHAR_QUIT.replace('"', '\\"')})
        else:
            self.get_room().add_message(_('\x191}%(spec)s \x193}%(nick)s\x195} has left the room (%(status)s)"') % {'nick':from_nick.replace('"', '\\"'), 'spec':get_theme().CHAR_QUIT, 'status': status_message.replace('"', '\\"')})
        if self.core.current_tab() is self:
            self.refresh()
            self.core.doupdate()

    def user_rejoined(self, nick):
        """
        The user (or at least someone with the same nick) came back in the MUC
        """
        self.activate()
        self.get_room().add_message('\x194}%(spec)s \x19%(color)d}%(nick)s\x195} joined the room' % {'nick':nick, 'color':user.color, 'spec':get_theme().CHAR_JOIN})
        if self.core.current_tab() is self:
            self.refresh()
            self.core.doupdate()


    def activate(self):
        self.on = True

    def deactivate(self):
        self.on = False

class RosterInfoTab(Tab):
    """
    A tab, splitted in two, containing the roster and infos
    """
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
        self.key_func["M-u"] = self.move_cursor_to_next_group
        self.key_func["M-y"] = self.move_cursor_to_prev_group
        self.key_func["M-[1;5B"] = self.move_cursor_to_next_group
        self.key_func["M-[1;5A"] = self.move_cursor_to_prev_group
        self.key_func["o"] = self.toggle_offline_show
        self.key_func["s"] = self.start_search
        self.key_func["S"] = self.start_search_slow
        self.commands['deny'] = (self.command_deny, _("Usage: /deny [jid]\nDeny: Use this command to remove and deny your presence to the provided JID (or the selected contact in your roster), who is asking you to be in his/here roster"), self.completion_deny)
        self.commands['accept'] = (self.command_accept, _("Usage: /accept [jid]\nAccept: Use this command to authorize the provided JID (or the selected contact in your roster), to see your presence, and to ask to subscribe to it (mutual presence subscription)."), self.completion_deny)
        self.commands['add'] = (self.command_add, _("Usage: /add <jid>\nAdd: Use this command to add the specified JID to your roster. The reverse authorization will automatically be accepted if the remote JID accepts your subscription, leading to a mutual presence subscription."), None)
        self.commands['name'] = (self.command_name, _("Usage: /name <jid> <name>\nSet the given JID's name"), self.completion_name)
        self.commands['groupadd'] = (self.command_groupadd, _("Usage: /groupadd <jid> <group>\nAdd the given JID to the given group"), self.completion_groupadd)
        self.commands['groupremove'] = (self.command_groupremove, _("Usage: /groupremove <jid> <group>\nRemove the given JID from the given group"), self.completion_groupremove)
        self.commands['remove'] = (self.command_remove, _("Usage: /remove [jid]\nRemove: Use this command to remove the specified JID from your roster. This wil unsubscribe you from its presence, cancel its subscription to yours, and remove the item from your roster"), self.completion_remove)
        self.commands['export'] = (self.command_export, _("Usage: /export [/path/to/file]\nExport: Use this command to export your contacts into /path/to/file if specified, or $HOME/poezio_contacts if not."), None)
        self.commands['import'] = (self.command_import, _("Usage: /import [/path/to/file]\nImport: Use this command to import your contacts from /path/to/file if specified, or $HOME/poezio_contacts if not."), None)
        self.resize()

    def resize(self):
        if not self.visible:
            return
        self.need_resize = False
        roster_width = self.width//2
        info_width = self.width-roster_width-1
        self.v_separator.resize(self.height-2, 1, 0, roster_width)
        self.information_win.resize(self.height-2-4, info_width, 0, roster_width+1, self.core.information_buffer)
        self.roster_win.resize(self.height-2, roster_width, 0, 0)
        self.contact_info_win.resize(4, info_width, self.height-2-4, roster_width+1)
        self.input.resize(1, self.width, self.height-1, 0)

    def completion(self):
        # Check if we are entering a command (with the '/' key)
        if isinstance(self.input, windows.CommandInput) and\
                not self.input.help_message:
            self.complete_commands(self.input)

    def command_deny(self, args):
        """
        Denies a JID from our roster
        """
        args = args.split()
        if not args:
            item = self.roster_win.selected_row
            if isinstance(item, Contact) and item.get_ask() == 'asked':
                jid = item.get_bare_jid()
            else:
                self.core.information('No subscription to deny')
                return
        else:
            jid = JID(args[0]).bare
        self.core.xmpp.sendPresence(pto=jid, ptype='unsubscribed')
        if self.core.xmpp.update_roster(jid, subscription='remove'):
            roster.remove_contact(jid)

    def command_add(self, args):
        """
        Add the specified JID to the roster, and set automatically
        accept the reverse subscription
        """
        jid = JID(args.strip()).bare
        if not jid:
            self.core.information(_('No JID specified'), 'Error')
            return
        self.core.xmpp.sendPresence(pto=jid, ptype='subscribe')

    def command_name(self, args):
        """
        Set a name for the specified JID in your roster
        """
        args = args.split(None, 1)
        if len(args) < 1:
            return
        jid = JID(args[0]).bare
        name = args[1] if len(args) == 2 else ''

        contact = roster.get_contact_by_jid(jid)
        if not contact:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        groups = set(contact.get_groups())
        subscription = contact.get_subscription()
        if self.core.xmpp.update_roster(jid, name=name, groups=groups, subscription=subscription):
            contact.set_name(name)

    def command_groupadd(self, args):
        """
        Add the specified JID to the specified group
        """
        args = args.split(None, 1)
        if len(args) != 2:
            return
        jid = JID(args[0]).bare
        group = args[1]

        contact = roster.get_contact_by_jid(jid)
        if not contact:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        new_groups = set(contact.get_groups())
        if group in new_groups:
            self.core.information(_('JID already in group'), 'Error')
            return

        new_groups.add(group)
        try:
            new_groups.remove('none')
        except KeyError:
            pass

        name = contact.get_name()
        subscription = contact.get_subscription()
        if self.core.xmpp.update_roster(jid, name=name, groups=new_groups, subscription=subscription):
            roster.edit_groups_of_contact(contact, new_groups)

    def command_groupremove(self, args):
        """
        Remove the specified JID to the specified group
        """
        args = args.split(None, 1)
        if len(args) != 2:
            return
        jid = JID(args[0]).bare
        group = args[1]

        contact = roster.get_contact_by_jid(jid)
        if not contact:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        new_groups = set(contact.get_groups())
        try:
            new_groups.remove('none')
        except KeyError:
            pass
        if group not in new_groups:
            self.core.information(_('JID not in group'), 'Error')
            return

        new_groups.remove(group)
        name = contact.get_name()
        subscription = contact.get_subscription()
        if self.core.xmpp.update_roster(jid, name=name, groups=new_groups, subscription=subscription):
            roster.edit_groups_of_contact(contact, new_groups)

    def command_remove(self, args):
        """
        Remove the specified JID from the roster. i.e. : unsubscribe
        from its presence, and cancel its subscription to our.
        """
        if args.strip():
            jid = JID(args.strip()).bare
        else:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.get_bare_jid()
            else:
                self.core.information('No roster item to remove')
                return
        self.core.xmpp.sendPresence(pto=jid, ptype='unsubscribe')
        self.core.xmpp.sendPresence(pto=jid, ptype='unsubscribed')
        self.core.xmpp.del_roster_item(jid=jid)

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
            handle = open(filepath, 'r')
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
        From with any JID presence in the roster
        """
        jids = [contact.get_bare_jid() for contact in roster.get_contacts()]
        return the_input.auto_completion(jids, '')

    def completion_name(self, the_input):
        text = the_input.get_text()
        n = len(text.split())
        if text.endswith(' '):
            n += 1

        if n == 2:
            jids = [contact.get_bare_jid() for contact in roster.get_contacts()]
            return the_input.auto_completion(jids, '')
        return False

    def completion_groupadd(self, the_input):
        text = the_input.get_text()
        n = len(text.split())
        if text.endswith(' '):
            n += 1

        if n == 2:
            jids = [contact.get_bare_jid() for contact in roster.get_contacts()]
            return the_input.auto_completion(jids, '')
        elif n == 3:
            groups = [group.name for group in roster.get_groups() if group.name != 'none']
            return the_input.auto_completion(groups, '')
        return False

    def completion_groupremove(self, the_input):
        text = the_input.get_text()
        args = text.split()
        n = len(args)
        if text.endswith(' '):
            n += 1

        if n == 2:
            jids = [contact.get_bare_jid() for contact in roster.get_contacts()]
            return the_input.auto_completion(jids, '')
        elif n == 3:
            contact = roster.get_contact_by_jid(args[1])
            if not contact:
                return False
            groups = list(contact.get_groups())
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
        jids = [contact.get_bare_jid() for contact in roster.get_contacts()\
             if contact.get_ask() == 'asked']
        return the_input.auto_completion(jids, '')

    def command_accept(self, args):
        """
        Accept a JID from in roster. Authorize it AND subscribe to it
        """
        args = args.split()
        if not args:
            item = self.roster_win.selected_row
            if isinstance(item, Contact) and item.get_ask() == 'asked':
                jid = item.get_bare_jid()
            else:
                self.core.information('No subscription to accept')
                return
        else:
            jid = args[0]
        self.core.xmpp.sendPresence(pto=jid, ptype='subscribed')
        self.core.xmpp.sendPresence(pto=jid, ptype='subscribe')

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s'%self.__class__.__name__)
        self.v_separator.refresh()
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
        self.information_win.refresh(self.core.informations)
        self.tab_win.refresh()
        self.input.refresh()

    def get_name(self):
        return self.name

    def on_input(self, key):
        if key == '^M':
            selected_row = self.roster_win.get_selected_row()
        res = self.input.do_command(key)
        if res:
            return True
        if key == '^M':
            self.core.on_roster_enter_key(selected_row)
            return selected_row
        elif key in self.key_func:
            return self.key_func[key]()

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
        if self.core.current_tab() is self:
            curses.curs_set(0)
        self.input = self.default_help_message
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

    def add_message(self):
        return False

    def move_cursor_down(self):
        if isinstance(self.input, windows.CommandInput):
            return
        self.roster_win.move_cursor_down()
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
        self.input.refresh()
        self.core.doupdate()

    def move_cursor_up(self):
        if isinstance(self.input, windows.CommandInput):
            return
        self.roster_win.move_cursor_up()
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
        self.input.refresh()
        self.core.doupdate()

    def move_cursor_to_prev_group(self):
        self.roster_win.move_cursor_up()
        while not isinstance(self.roster_win.get_selected_row(), RosterGroup):
            if not self.roster_win.move_cursor_up():
                break
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
        self.input.refresh()
        self.core.doupdate()

    def move_cursor_to_next_group(self):
        self.roster_win.move_cursor_down()
        while not isinstance(self.roster_win.get_selected_row(), RosterGroup):
            if not self.roster_win.move_cursor_down():
                break
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
        self.input.refresh()
        self.core.doupdate()

    def on_scroll_down(self):
        for i in range(self.height-1):
            self.roster_win.move_cursor_down()
        return True

    def on_scroll_up(self):
        for i in range(self.height-1):
            self.roster_win.move_cursor_up()
        return True

    def on_space(self):
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, RosterGroup) or\
                isinstance(selected_row, Contact):
            selected_row.toggle_folded()
            return True

    def start_search(self):
        """
        Start the search. The input should appear with a short instruction
        in it.
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("[Search]", self.on_search_terminate, self.on_search_terminate, self.set_roster_filter)
        self.input.resize(1, self.width, self.height-1, 0)
        return True

    def start_search_slow(self):
        curses.curs_set(1)
        self.input = windows.CommandInput("[Search]", self.on_search_terminate, self.on_search_terminate, self.set_roster_filter_slow)
        self.input.resize(1, self.width, self.height-1, 0)
        return True

    def set_roster_filter_slow(self, txt):
        roster._contact_filter = (jid_and_name_match_slow, txt)
        self.roster_win.refresh(roster)
        return False

    def set_roster_filter(self, txt):
        roster._contact_filter = (jid_and_name_match, txt)
        self.roster_win.refresh(roster)
        return False

    def on_search_terminate(self, txt):
        curses.curs_set(0)
        roster._contact_filter = None
        self.reset_help_message()
        return False

    def on_close(self):
        return

class ConversationTab(ChatTab):
    """
    The tab containg a normal conversation (not from a MUC)
    """
    message_type = 'chat'
    def __init__(self, jid):
        txt_buff = text_buffer.TextBuffer()
        ChatTab.__init__(self, txt_buff)
        self.state = 'normal'
        self._name = jid        # a conversation tab is linked to one specific full jid OR bare jid
        self.text_win = windows.TextWin()
        txt_buff.add_window(self.text_win)
        self.upper_bar = windows.ConversationStatusMessageWin()
        self.info_header = windows.ConversationInfoWin()
        self.input = windows.MessageInput()
        # keys
        self.key_func['^I'] = self.completion
        # commands
        self.commands['unquery'] = (self.command_unquery, _("Usage: /unquery\nUnquery: close the tab"), None)
        self.commands['close'] = (self.command_unquery, _("Usage: /close\Close: close the tab"), None)
        self.resize()

    def completion(self):
        self.complete_commands(self.input)

    def command_say(self, line):
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = 'chat'
        if line.find('\x19') == -1:
            msg['body'] = line
        else:
            msg['body'] = xhtml.clean_text_simple(line)
            msg['xhtml_im'] = xhtml.poezio_colors_to_html(line)
        if config.get('send_chat_states', 'true') == 'true' and self.remote_wants_chatstates is not False:
            needed = 'inactive' if self.core.status.show in ('xa', 'away') else 'active'
            msg['chat_state'] = needed
        msg.send()
        self.core.add_message_to_text_buffer(self.get_room(), line, None, self.core.own_nick)
        logger.log_message(JID(self.get_name()).bare, self.core.own_nick, line)
        self.cancel_paused_delay()
        self.text_win.refresh(self._room)
        self.input.refresh()

    def command_unquery(self, arg):
        self.core.close_tab()

    def resize(self):
        if self.core.information_win_size >= self.height-3 or not self.visible:
            return
        self.need_resize = False
        self.text_win.resize(self.height-4-self.core.information_win_size, self.width, 1, 0)
        self.text_win.rebuild_everything(self._room)
        self.upper_bar.resize(1, self.width, 0, 0)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s'%self.__class__.__name__)
        self.text_win.refresh(self._room)
        self.upper_bar.refresh(self.get_name(), roster.get_contact_by_jid(self.get_name()))
        self.info_header.refresh(self.get_name(), roster.get_contact_by_jid(self.get_name()), self._room, self.text_win, self.chatstate)
        self.info_win.refresh(self.core.informations)
        self.tab_win.refresh()
        self.input.refresh()

    def refresh_info_header(self):
        self.info_header.refresh(self.get_name(), roster.get_contact_by_jid(self.get_name()), self._room, self.text_win, self.chatstate)
        self.input.refresh()

    @property
    def color(self):
        if self.state == 'normal' or \
                self.state == 'current':
            return STATE_COLORS[self.state]()
        return get_theme().COLOR_TAB_PRIVATE

    def get_name(self):
        return self._name

    def on_input(self, key):
        if key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key)
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)
        return False

    def on_lose_focus(self):
        self.state = 'normal'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator()
        if config.get('send_chat_states', 'true') == 'true' and not self.input.get_text() or not self.input.get_text().startswith('//'):
            self.send_chat_state('inactive')

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(1)
        if config.get('send_chat_states', 'true') == 'true' and not self.input.get_text() or not self.input.get_text().startswith('//'):
            self.send_chat_state('active')

    def on_scroll_up(self):
        self.text_win.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self.text_win.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        self.text_win.resize(self.height-4-self.core.information_win_size, self.width, 1, 0)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0)

    def get_room(self):
        return self._room

    def get_text_window(self):
        return self.text_win

    def on_close(self):
        Tab.on_close(self)
        if config.get('send_chat_states', 'true') == 'true':
            self.send_chat_state('gone')

class MucListTab(Tab):
    """
    A tab listing rooms from a specific server, displaying various information,
    scrollable, and letting the user join them, etc
    """
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
        self.key_func["KEY_DOWN"] = self.listview.move_cursor_down
        self.key_func["KEY_UP"] = self.listview.move_cursor_up
        self.key_func['^I'] = self.completion
        self.key_func["/"] = self.on_slash
        self.key_func['j'] = self.join_selected
        self.key_func['J'] = self.join_selected_no_focus
        self.key_func['^M'] = self.join_selected
        self.commands['close'] = (self.close, _("Usage: /close\nClose: Just close this tab"), None)
        self.resize()

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s'%self.__class__.__name__)
        self.upper_message.refresh()
        self.list_header.refresh()
        self.listview.refresh()
        self.tab_win.refresh()
        self.input.refresh()

    def resize(self):
        if not self.visible:
            return
        self.need_resize = False
        self.upper_message.resize(1, self.width, 0, 0)
        column_size = {'node-part': (self.width-5)//4,
                       'name': (self.width-5)//4*3,
                       'users': 5}
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
        items = [{'node-part':JID(item[0]).user,
                  'jid': item[0],
                  'name': item[2]} for item in iq['disco_items'].get_items()]
        self.listview.add_lines(items)
        self.upper_message.set_message('Chatroom list on server %s' % self.name)
        self.upper_message.refresh()
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
        self.execute_command(txt)
        return self.reset_help_message()

    def get_name(self):
        return self.name

    def completion(self):
        if isinstance(self.input, windows.CommandInput):
            self.complete_commands(self.input)

    def on_input(self, key):
        res = self.input.do_command(key)
        if res:
            return True
        if key in self.key_func:
            return self.key_func[key]()

    def on_lose_focus(self):
        self.state = 'normal'

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(0)

    def on_scroll_up(self):
        self.listview.scroll_up()

    def on_scroll_down(self):
        self.listview.scroll_down()

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

    def on_input(self, key):
        res = self.input.do_command(key)
        if res:
            return True
        if key in self.key_func:
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
        log.debug('  TAB   Refresh: %s'%self.__class__.__name__)
        self.text_win.refresh()
        self.tab_win.refresh()
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
    if txt in JID(contact.get_bare_jid()).user:
        return True
    return False

def jid_and_name_match_slow(contact, txt):
    """
    A function used to know if a contact in the roster should
    be shown in the roster
    """
    if not txt:
        return True             # Everything matches when search is empty
    user = JID(contact.get_bare_jid()).user
    if diffmatch(txt, user):
        return True
    if contact.get_name() and diffmatch(txt, contact.get_name()):
        return True
    return False
