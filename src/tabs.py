# Copyright 2010-2011 Le Coz Florent <louiz@louiz.org>
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

"""
a Tab object is a way to organize various Windows (see windows.py)
around the screen at once.
A tab is then composed of multiple Buffer.
Each Tab object has different refresh() and resize() methods, defining how its
Windows are displayed, resized, etc
"""

MIN_WIDTH = 50
MIN_HEIGHT = 16

import logging
log = logging.getLogger(__name__)

from gettext import gettext as _

import windows
import theme
import curses
import difflib
import text_buffer
import string
import common
import core
import singleton

import multiuserchat as muc

from sleekxmpp.xmlstream.stanzabase import JID
from config import config
from roster import RosterGroup, roster
from contact import Contact, Resource
from user import User
from logger import logger

SHOW_NAME = {
    'dnd': _('busy'),
    'away': _('away'),
    'xa': _('not available'),
    'chat': _('chatty'),
    '': _('available')
    }

class Tab(object):
    number = 0
    tab_core = None
    def __init__(self):
        self.input = None
        self._color_state = theme.COLOR_TAB_NORMAL
        self.need_resize = False
        self.nb = Tab.number
        Tab.number += 1
        self.visible = True
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
    def info_win(self):
        return self.core.information_win

    @staticmethod
    def resize(scr):
        Tab.size = (Tab.height, Tab.width) = scr.getmaxyx()

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
                words = ['/%s'%(name) for name in list(self.core.commands.keys())] +\
                    ['/%s'% (name) for name in list(self.commands.keys())]
                the_input.auto_completion(words, '')
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
            if command in self.core.commands: # check global commands
                self.core.commands[command][0](arg)
            elif command in self.commands: # check tab-specific commands
                self.commands[command][0](arg)
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

    def get_color_state(self):
        """
        returns the color that should be used in the GlobalInfoBar
        """
        return self._color_state

    def set_color_state(self, color):
        """
        set the color state
        """
        pass

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
        self._color_state = theme.COLOR_TAB_NORMAL

    def on_gain_focus(self):
        """
        called when this tab gains the focus.
        """
        self._color_state = theme.COLOR_TAB_CURRENT

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
        self.key_func['M-/'] = self.last_words_completion
        self.key_func['^M'] = self.on_enter
        self.commands['say'] =  (self.command_say,
                                 _("""Usage: /say <message>\nSay: Just send the message.
                                        Useful if you want your message to begin with a '/'"""), None)

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
            txt = msg.get('txt')
            for char in char_we_dont_want:
                txt = txt.replace(char, ' ')
            for word in txt.split():
                if len(word) >= 4 and word not in words:
                    words.append(word)
        self.input.auto_completion(words, ' ')

    def on_enter(self):
        txt = self.input.key_enter()
        if not self.execute_command(txt):
            if txt.startswith('//'):
                txt = txt[1:]
            self.command_say(txt)

    def send_chat_state(self, state):
        """
        Send an empty chatstate message
        """
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = self.message_type
        msg['chat_state'] = state
        msg.send()

    def send_composing_chat_state(self, empty_before, empty_after):
        """
        Send the "active" or "composing" chatstate, depending
        on the the current status of the input
        """
        if config.get('send_chat_states', 'true') == 'true' and self.remote_wants_chatstates:
            if not empty_before and empty_after:
                self.send_chat_state("active")
            elif empty_before and not empty_after:
                self.send_chat_state("composing")

    def command_say(self, line):
        raise NotImplementedError

class InfoTab(ChatTab):
    """
    The information tab, used to display global informations
    when using a anonymous account
    """
    def __init__(self):
        Tab.__init__(self)
        self.tab_win = windows.GlobalInfoBar()
        self.input = windows.Input()
        self.name = "Info"
        self.color_state = theme.COLOR_TAB_NORMAL
        self.key_func['^M'] = self.on_enter
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
        self.resize()

    def resize(self):
        if not self.visible:
            return
        self.tab_win.resize(1, self.width, self.height-2, 0)
        self.info_win.resize(self.height-2, self.width, 0, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if not self.visible:
            return
        if self.need_resize:
            self.resize()
        self.info_win.refresh(self.core.informations)
        self.tab_win.refresh()
        self.input.refresh()

    def completion(self):
        self.complete_commands(self.input)

    def get_name(self):
        return self.name

    def get_color_state(self):
        return self.color_state

    def set_color_state(self, color):
        return

    def on_input(self, key):
        if key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key)
        return False

    def on_enter(self):
        self.execute_command(self.input.key_enter())

    def on_lose_focus(self):
        self.color_state = theme.COLOR_TAB_NORMAL

    def on_gain_focus(self):
        self.color_state = theme.COLOR_TAB_CURRENT
        curses.curs_set(1)

    def on_scroll_up(self):
        pass

    def on_scroll_down(self):
        pass

    def on_info_win_size_changed(self):
        return

    def just_before_refresh(self):
        return

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
        self.tab_win = windows.GlobalInfoBar()
        self.input = windows.MessageInput()
        self.ignores = []       # set of Users
        # keys
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
        self.key_func['M-u'] = self.scroll_user_list_down
        self.key_func['M-y'] = self.scroll_user_list_up
        # commands
        self.commands['ignore'] = (self.command_ignore, _("Usage: /ignore <nickname> \nIgnore: Ignore a specified nickname."), None)
        self.commands['unignore'] = (self.command_unignore, _("Usage: /unignore <nickname>\nUnignore: Remove the specified nickname from the ignore list."), self.completion_unignore)
        self.commands['kick'] =  (self.command_kick, _("Usage: /kick <nick> [reason]\nKick: Kick the user with the specified nickname. You also can give an optional reason."), None)
        self.commands['topic'] = (self.command_topic, _("Usage: /topic <subject>\nTopic: Change the subject of the room"), self.completion_topic)
        self.commands['query'] = (self.command_query, _('Usage: /query <nick> [message]\nQuery: Open a private conversation with <nick>. This nick has to be present in the room you\'re currently in. If you specified a message after the nickname, it will immediately be sent to this user'), None)
        self.commands['part'] = (self.command_part, _("Usage: /part [message]\n Part: disconnect from a room. You can specify an optional message."), None)
        self.commands['nick'] = (self.command_nick, _("Usage: /nick <nickname>\nNick: Change your nickname in the current room"), None)
        self.commands['recolor'] = (self.command_recolor, _('Usage: /recolor\nRecolor: Re-assign a color to all participants of the current room, based on the last time they talked. Use this if the participants currently talking have too many identical colors.'), None)
        self.commands['cycle'] = (self.command_cycle, _('Usage: /cycle [message]\nCycle: Leaves the current room and rejoin it immediately'), None)
        self.commands['info'] = (self.command_info, _('Usage: /info <nickname>\nInfo: Display some information about the user in the MUC: his/here role, affiliation, status and status message.'), None)
        self.commands['configure'] = (self.command_configure, _('Usage: /configure\nConfigure: Configure the current room, through a form.'), None)
        self.resize()

    def scroll_user_list_up(self):
        self.user_win.scroll_up()
        self.core.refresh_window()

    def scroll_user_list_down(self):
        self.user_win.scroll_down()
        self.core.refresh_window()

    def command_info(self, arg):
        args = common.shell_split(arg)
        if len(args) != 1:
            return self.core.information("Info command takes only 1 argument")
        user = self.get_room().get_user_by_name(args[0])
        if not user:
            return self.core.information("Unknown user: %s" % args[0])
        self.get_room().add_message("%s%s: show: %s, affiliation: %s, role: %s\n%s"% (args[0], ' (%s)'%user.jid if user.jid else '', user.show or 'Available', user.role or 'None', user.affiliation or 'None', user.status))
        self.core.refresh_window()

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

    def command_cycle(self, arg):
        if self.get_room().joined:
            muc.leave_groupchat(self.core.xmpp, self.get_name(), self.get_room().own_nick, arg)
        self.get_room().joined = False
        self.core.command_join('/', "0")

    def command_recolor(self, arg):
        """
        Re-assign color to the participants of the room
        """
        room = self.get_room()
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
            i += 1
        self.text_win.rebuild_everything(self.get_room())
        self.core.refresh_window()

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
        muc.change_nick(self.core.xmpp, room.name, nick)

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
            muc.send_private_message(self.core.xmpp, r.name, msg)
            self.core.add_message_to_text_buffer(r, msg, None, r.own_nick)

    def command_topic(self, arg):
        """
        /topic [new topic]
        """
        if not arg.strip():
            self.core.add_message_to_text_buffer(self.get_room(),
                                                 _("The subject of the room is: %s") % self.get_room().topic)
            return
        subject = arg
        muc.change_subject(self.core.xmpp, self.get_room().name, subject)

    def completion_topic(self, the_input):
        current_topic = self.get_room().topic
        return the_input.auto_completion([current_topic], ' ')

    def command_kick(self, arg):
        """
        /kick <nick> [reason]
        """
        args = common.shell_split(arg)
        if len(args) < 1:
            self.core.command_help('kick')
            return
        nick = args[0]
        if len(args) >= 2:
            reason = ' '.join(args[1:])
        else:
            reason = ''
        if not self.get_room().joined:
            return
        res = muc.eject_user(self.core.xmpp, self.get_name(), nick, reason)
        if res['type'] == 'error':
            self.core.room_error(res, self.get_name())

    def command_say(self, line):
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = 'groupchat'
        msg['body'] = line
        if config.get('send_chat_states', 'true') == 'true' and self.remote_wants_chatstates is not False:
            msg['chat_state'] = 'active'
        msg.send()

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
        text_width = (self.width//10)*9
        self.topic_win.resize(1, self.width, 0, 0)
        self.v_separator.resize(self.height-3, 1, 1, 9*(self.width//10))
        self.text_win.resize(self.height-4-self.core.information_win_size, text_width, 1, 0)
        self.text_win.rebuild_everything(self._room)
        self.user_win.resize(self.height-3-self.core.information_win_size-1, self.width-text_width-1, 1, text_width+1)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0)
        self.tab_win.resize(1, self.width, self.height-2, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if not self.visible:
            return
        if self.need_resize:
            self.resize()
        self.topic_win.refresh(self._room.topic)
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
        empty_before = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.input.do_command(key)
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_before, empty_after)
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
        if ' ' not in self.input.get_text() or (self.input.last_completion and\
                     self.input.get_text()[:-len(after)] == self.input.last_completion):
            add_after = after
        else:
            add_after = ' '
        self.input.auto_completion(word_list, add_after)

    def get_color_state(self):
        return self._room.color_state

    def set_color_state(self, color):
        self._room.set_color_state(color)

    def get_name(self):
        return self._room.name

    def get_text_window(self):
        return self.text_win

    def get_room(self):
        return self._room

    def on_lose_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_NORMAL)
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator()
        if config.get('send_chat_states', 'true') == 'true' and not self.input.get_text():
            self.send_chat_state('inactive')

    def on_gain_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_CURRENT)
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

    def just_before_refresh(self):
        return

    def handle_presence(self, presence):
        from_nick = presence['from'].resource
        from_room = presence['from'].bare
        code = presence.find('{jabber:client}status')
        status_codes = set([s.attrib['code'] for s in presence.findall('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}status')])
        # Check if it's not an error presence.
        if presence['type'] == 'error':
            return self.core.room_error(presence, from_room)
        msg = None
        affiliation = presence['muc']['affiliation']
        show = presence['show']
        status = presence['status']
        role = presence['muc']['role']
        jid = presence['muc']['jid']
        typ = presence['type']
        room = self.get_room()
        if not room.joined:     # user in the room BEFORE us.
            # ignore redondant presence message, see bug #1509
            if from_nick not in [user.nick for user in room.users]:
                new_user = User(from_nick, affiliation, show, status, role, jid)
                room.users.append(new_user)
                if from_nick == room.own_nick:
                    room.joined = True
                    new_user.color = theme.COLOR_OWN_NICK
                    # self.add_message_to_text_buffer(room, _("Your nickname is %s") % (from_nick))
                    room.add_message(_("Your nickname is %s") % (from_nick))
                    if '170' in status_codes:
                        # self.add_message_to_text_buffer(room, 'Warning: this room is publicly logged')
                        room.add_message('Warning: this room is publicly logged')
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
        self.core.refresh_window()
        self.core.doupdate()

    def on_user_join(self, room, from_nick, affiliation, show, status, role, jid):
        """
        When a new user joins the groupchat
        """
        room.users.append(User(from_nick, affiliation,
                               show, status, role, jid))
        hide_exit_join = config.get('hide_exit_join', -1)
        if hide_exit_join != 0:
            if not jid.full:
                room.add_message(_('%(spec)s "[%(nick)s]" joined the room') % {'nick':from_nick.replace('"', '\\"'), 'spec':theme.CHAR_JOIN.replace('"', '\\"')}, colorized=True)
            else:
                room.add_message(_('%(spec)s "[%(nick)s]" "(%(jid)s)" joined the room') % {'spec':theme.CHAR_JOIN.replace('"', '\\"'), 'nick':from_nick.replace('"', '\\"'), 'jid':jid.full}, colorized=True)

    def on_user_nick_change(self, room, presence, user, from_nick, from_room):
        new_nick = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item').attrib['nick']
        if user.nick == room.own_nick:
            room.own_nick = new_nick
            # also change our nick in all private discussion of this room
            for _tab in self.core.tabs:
                if isinstance(_tab, PrivateTab) and JID(_tab.get_name()).bare == room.name:
                    _tab.get_room().own_nick = new_nick
        user.change_nick(new_nick)
        room.add_message(_('"[%(old)s]" is now known as "[%(new)s]"') % {'old':from_nick.replace('"', '\\"'), 'new':new_nick.replace('"', '\\"')}, colorized=True)
        # rename the private tabs if needed
        self.core.rename_private_tabs(room.name, from_nick, new_nick)

    def on_user_banned(self, room, presence, user, from_nick):
        """
        When someone is banned from a muc
        """
        room.users.remove(user)
        by = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item/{http://jabber.org/protocol/muc#user}actor')
        reason = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item/{http://jabber.org/protocol/muc#user}reason')
        by = by.attrib['jid'] if by is not None else None
        if from_nick == room.own_nick: # we are banned
            room.disconnect()
            if by:
                kick_msg = _('%(spec)s [You] have been banned by "[%(by)s]"') % {'spec': theme.CHAR_KICK.replace('"', '\\"'), 'by':by}
            else:
                kick_msg = _('%(spec)s [You] have been banned.') % {'spec':theme.CHAR_KICK.replace('"', '\\"')}
        else:
            if by:
                kick_msg = _('%(spec)s "[%(nick)s]" has been banned by "[%(by)s]"') % {'spec':theme.CHAR_KICK.replace('"', '\\"'), 'nick':from_nick.replace('"', '\\"'), 'by':by.replace('"', '\\"')}
            else:
                kick_msg = _('%(spec)s "[%(nick)s]" has been banned') % {'spec':theme.CHAR_KICK, 'nick':from_nick.replace('"', '\\"')}
        if reason is not None and reason.text:
            kick_msg += _(' Reason: %(reason)s') % {'reason': reason.text}
        room.add_message(kick_msg, colorized=True)

    def on_user_kicked(self, room, presence, user, from_nick):
        """
        When someone is kicked from a muc
        """
        room.users.remove(user)
        by = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item/{http://jabber.org/protocol/muc#user}actor')
        reason = presence.find('{http://jabber.org/protocol/muc#user}x/{http://jabber.org/protocol/muc#user}item/{http://jabber.org/protocol/muc#user}reason')
        by = by.attrib['jid'] if by is not None else None
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
        if reason is not None and reason.text:
            kick_msg += _(' Reason: %(reason)s') % {'reason': reason.text}
        room.add_message(kick_msg, colorized=True)

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
            room.add_message(leave_msg, colorized=True)
        self.core.on_user_left_private_conversation(from_room, from_nick, status)

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
        if show != user.show and show in SHOW_NAME:
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
            room.add_message(msg, colorized=True)
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
        self.tab_win = windows.GlobalInfoBar()
        self.input = windows.MessageInput()
        # keys
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
        # commands
        self.commands['unquery'] = (self.command_unquery, _("Usage: /unquery\nUnquery: close the tab"), None)
        self.commands['part'] = (self.command_unquery, _("Usage: /part\Part: close the tab"), None)
        self.resize()

    def completion(self):
        self.complete_commands(self.input)

    def command_say(self, line):
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = 'chat'
        msg['body'] = line
        if config.get('send_chat_states', 'true') == 'true' and self.remote_wants_chatstates is not False:
            msg['chat_state'] = 'active'
        msg.send()
        self.core.add_message_to_text_buffer(self.get_room(), line, None, self.core.own_nick)
        logger.log_message(JID(self.get_name()).bare, self.core.own_nick, line)

    def command_unquery(self, arg):
        """
        /unquery
        """
        self.core.close_tab()

    def resize(self):
        if not self.visible:
            return
        if self.core.information_win_size >= self.height-3:
            return
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0)
        self.text_win.rebuild_everything(self._room)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0)
        self.tab_win.resize(1, self.width, self.height-2, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if not self.visible:
            return
        if self.need_resize:
            self.resize()
        self.text_win.refresh(self._room)
        self.info_header.refresh(self._room, self.text_win, self.chatstate)
        self.info_win.refresh(self.core.informations)
        self.tab_win.refresh()
        self.input.refresh()

    def get_color_state(self):
        if self._room.color_state == theme.COLOR_TAB_NORMAL or\
                self._room.color_state == theme.COLOR_TAB_CURRENT:
            return self._room.color_state
        return theme.COLOR_TAB_PRIVATE

    def set_color_state(self, color):
        self._room.color_state = color

    def get_name(self):
        return self._room.name

    def on_input(self, key):
        if key in self.key_func:
            self.key_func[key]()
            return False
        empty_before = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.input.do_command(key)
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_before, empty_after)
        return False

    def on_lose_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_NORMAL)
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator()
        if self.get_room().joined and config.get('send_chat_states', 'true') == 'true' and not self.input.get_text():
            self.send_chat_state('inactive')

    def on_gain_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_CURRENT)
        curses.curs_set(1)
        if config.get('send_chat_states', 'true') == 'true' and not self.input.get_text():
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

    def just_before_refresh(self):
        return

    def rename_user(self, old_nick, new_nick):
        """
        The user changed her nick in the corresponding muc: update the tab’s name and
        display a message.
        """
        self.get_room().add_message(_('"[%(old_nick)s]" is now known as "[%(new_nick)s]"') % {'old_nick':old_nick.replace('"', '\\"'), 'new_nick':new_nick.replace('"', '\\"')}, colorized=True)
        new_jid = JID(self.get_room().name).bare+'/'+new_nick
        self.get_room().name = new_jid

    def user_left(self, status_message, from_nick):
        """
        The user left the associated MUC
        """
        if not status_message:
            self.get_room().add_message(_('%(spec)s "[%(nick)s]" has left the room') % {'nick':from_nick.replace('"', '\\"'), 'spec':theme.CHAR_QUIT.replace('"', '\\"')}, colorized=True)
        else:
            self.get_room().add_message(_('%(spec)s "[%(nick)s]" has left the room "(%(status)s)"') % {'nick':from_nick.replace('"', '\\"'), 'spec':theme.CHAR_QUIT, 'status': status_message.replace('"', '\\"')}, colorized=True)

class RosterInfoTab(Tab):
    """
    A tab, splitted in two, containing the roster and infos
    """
    def __init__(self):
        Tab.__init__(self)
        self.name = "Roster"
        self.v_separator = windows.VerticalSeparator()
        self.tab_win = windows.GlobalInfoBar()
        self.information_win = windows.TextWin()
        self.core.information_buffer.add_window(self.information_win)
        self.roster_win = windows.RosterWin()
        self.contact_info_win = windows.ContactInfoWin()
        self.default_help_message = windows.HelpText("Enter commands with “/”. “o”: toggle offline show")
        self.input = self.default_help_message
        self.set_color_state(theme.COLOR_TAB_NORMAL)
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
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
        self.commands['add'] = (self.command_add, _("Usage: /add <jid>\Add: Use this command to add the specified JID to your roster. The reverse authorization will automatically be accepted if the remote JID accepts your subscription, leading to a mutual presence subscription."), None)
        self.commands['remove'] = (self.command_remove, _("Usage: /remove [jid]\Remove: Use this command to remove the specified JID from your roster. This wil unsubscribe you from its presence, cancel its subscription to yours, and remove the item from your roster"), self.completion_remove)
        self.resize()

    def resize(self):
        if not self.visible:
            return
        roster_width = self.width//2
        info_width = self.width-roster_width-1
        self.v_separator.resize(self.height-2, 1, 0, roster_width)
        self.tab_win.resize(1, self.width, self.height-2, 0)
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
            return
        self.core.xmpp.sendPresence(pto=jid, ptype='subscribe')

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

    def completion_remove(self, the_input):
        """
        From with any JID presence in the roster
        """
        jids = [contact.get_bare_jid() for contact in roster.get_contacts()]
        return the_input.auto_completion(jids, '')

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
                self.core.information('No subscription to deny')
                return
        else:
            jid = args[0]
        self.core.xmpp.sendPresence(pto=jid, ptype='subscribed')
        self.core.xmpp.sendPresence(pto=jid, ptype='subscribe')

    def refresh(self):
        if not self.visible:
            return
        if self.need_resize:
            self.resize()
        self.v_separator.refresh()
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
        self.information_win.refresh(self.core.informations)
        self.tab_win.refresh()
        self.input.refresh()

    def get_name(self):
        return self.name

    def get_color_state(self):
        return self._color_state

    def set_color_state(self, color):
        self._color_state = color

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
        curses.curs_set(0)
        self.input = self.default_help_message
        self.core.refresh_window()
        return True

    def execute_slash_command(self, txt):
        if txt.startswith('/'):
            self.execute_command(txt)
        return self.reset_help_message()

    def on_lose_focus(self):
        self._color_state = theme.COLOR_TAB_NORMAL

    def on_gain_focus(self):
        self._color_state = theme.COLOR_TAB_CURRENT
        if isinstance(self.input, windows.HelpText):
            curses.curs_set(0)
        else:
            curses.curs_set(1)

    def add_message(self):
        return False

    def move_cursor_down(self):
        self.roster_win.move_cursor_down()
        return True

    def move_cursor_up(self):
        self.roster_win.move_cursor_up()
        return True

    def move_cursor_to_prev_group(self):
        self.roster_win.move_cursor_up()
        while not isinstance(self.roster_win.get_selected_row(), RosterGroup):
            if not self.roster_win.move_cursor_up():
                break
        self.core.refresh_window()

    def move_cursor_to_next_group(self):
        self.roster_win.move_cursor_down()
        while not isinstance(self.roster_win.get_selected_row(), RosterGroup):
            if not self.roster_win.move_cursor_down():
                break
        self.core.refresh_window()

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

    def just_before_refresh(self):
        return

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
        self.color_state = theme.COLOR_TAB_NORMAL
        self._name = jid        # a conversation tab is linked to one specific full jid OR bare jid
        self.text_win = windows.TextWin()
        txt_buff.add_window(self.text_win)
        self.upper_bar = windows.ConversationStatusMessageWin()
        self.info_header = windows.ConversationInfoWin()
        self.tab_win = windows.GlobalInfoBar()
        self.input = windows.MessageInput()
        # keys
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
        # commands
        self.commands['unquery'] = (self.command_unquery, _("Usage: /unquery\nUnquery: close the tab"), None)
        self.commands['part'] = (self.command_unquery, _("Usage: /part\Part: close the tab"), None)
        self.resize()

    def completion(self):
        self.complete_commands(self.input)

    def command_say(self, line):
        msg = self.core.xmpp.make_message(self.get_name())
        msg['type'] = 'chat'
        msg['body'] = line
        if config.get('send_chat_states', 'true') == 'true' and self.remote_wants_chatstates is not False:
            msg['chat_state'] = 'active'
        msg.send()
        self.core.add_message_to_text_buffer(self.get_room(), line, None, self.core.own_nick)
        logger.log_message(JID(self.get_name()).bare, self.core.own_nick, line)

    def command_unquery(self, arg):
        self.core.close_tab()

    def resize(self):
        if not self.visible:
            return
        if self.core.information_win_size >= self.height-3:
            return
        self.text_win.resize(self.height-4-self.core.information_win_size, self.width, 1, 0)
        self.text_win.rebuild_everything(self._room)
        self.upper_bar.resize(1, self.width, 0, 0)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0)
        self.tab_win.resize(1, self.width, self.height-2, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if not self.visible:
            return
        if self.need_resize:
            self.resize()
        self.text_win.refresh(self._room)
        self.upper_bar.refresh(self.get_name(), roster.get_contact_by_jid(self.get_name()))
        self.info_header.refresh(self.get_name(), roster.get_contact_by_jid(self.get_name()), self._room, self.text_win, self.chatstate)
        self.info_win.refresh(self.core.informations)
        self.tab_win.refresh()
        self.input.refresh()

    def get_color_state(self):
        if self.color_state == theme.COLOR_TAB_NORMAL or\
                self.color_state == theme.COLOR_TAB_CURRENT:
            return self.color_state
        return theme.COLOR_TAB_PRIVATE

    def set_color_state(self, color):
        self.color_state = color

    def get_name(self):
        return self._name

    def on_input(self, key):
        if key in self.key_func:
            self.key_func[key]()
            return False
        empty_before = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.input.do_command(key)
        empty_after = self.input.get_text() == '' or (self.input.get_text().startswith('/') and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_before, empty_after)
        return False

    def on_lose_focus(self):
        self.set_color_state(theme.COLOR_TAB_NORMAL)
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator()
        if config.get('send_chat_states', 'true') == 'true' and not self.input.get_text():
            self.send_chat_state('inactive')

    def on_gain_focus(self):
        self.set_color_state(theme.COLOR_TAB_CURRENT)
        curses.curs_set(1)
        if config.get('send_chat_states', 'true') == 'true' and not self.input.get_text():
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

    def just_before_refresh(self):
        return

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
        self._color_state = theme.COLOR_TAB_NORMAL
        self.name = server
        self.upper_message = windows.Topic()
        self.upper_message.set_message('Chatroom list on server %s (Loading)' % self.name)
        columns = ('node-part','name', 'users')
        self.list_header = windows.ColumnHeaderWin(columns)
        self.listview = windows.ListWin(columns)
        self.tab_win = windows.GlobalInfoBar()
        self.default_help_message = windows.HelpText("“j”: join room.")
        self.input = self.default_help_message
        self.key_func["KEY_DOWN"] = self.listview.move_cursor_down
        self.key_func["KEY_UP"] = self.listview.move_cursor_up
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
        self.key_func["/"] = self.on_slash
        self.key_func['j'] = self.join_selected
        self.key_func['J'] = self.join_selected_no_focus
        self.key_func['^M'] = self.join_selected
        self.commands['close'] = (self.close, _("Usage: /close\nClose: Just close this tab"), None)
        self.resize()

    def refresh(self):
        if not self.visible:
            return
        if self.need_resize:
            self.resize()
        self.upper_message.refresh()
        self.list_header.refresh()
        self.listview.refresh()
        self.tab_win.refresh()
        self.input.refresh()

    def resize(self):
        if not self.visible:
            return
        self.upper_message.resize(1, self.width, 0, 0)
        column_size = {'node-part': (self.width-5)//4,
                       'name': (self.width-5)//4*3,
                       'users': 5}
        self.list_header.resize_columns(column_size)
        self.list_header.resize(1, self.width, 1, 0)
        self.listview.resize_columns(column_size)
        self.listview.resize(self.height-4, self.width, 2, 0)
        self.tab_win.resize(1, self.width, self.height-2, 0)
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
        self._color_state = theme.COLOR_TAB_NORMAL

    def on_gain_focus(self):
        self._color_state = theme.COLOR_TAB_CURRENT
        curses.curs_set(0)

    def get_color_state(self):
        return self._color_state

class SimpleTextTab(Tab):
    """
    A very simple tab, with just a text displaying some
    information or whatever.
    For example used to display tracebacks
    """
    def __init__(self, text):
        Tab.__init__(self)
        self._color_state = theme.COLOR_TAB_NORMAL
        self.text_win = windows.SimpleTextWin(text)
        self.tab_win = windows.GlobalInfoBar()
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
        self.text_win.resize(self.height-2, self.width, 0, 0)
        self.tab_win.resize(1, self.width, self.height-2, 0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if not self.visible:
            return
        if self.need_resize:
            self.resize()
        self.text_win.refresh()
        self.tab_win.refresh()
        self.input.refresh()

    def on_lose_focus(self):
        self._color_state = theme.COLOR_TAB_NORMAL

    def on_gain_focus(self):
        self._color_state = theme.COLOR_TAB_CURRENT
        curses.curs_set(0)

    def get_color_state(self):
        return self._color_state

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
    ratio = 0.7
    if not txt:
        return True             # Everything matches when search is empty
    user = JID(contact.get_bare_jid()).user
    if diffmatch(txt, user):
        return True
    if contact.get_name() and diffmatch(txt, contact.get_name()):
        return True
    return False
