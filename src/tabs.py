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
Buffer are displayed, resized, etc
"""

MIN_WIDTH = 50
MIN_HEIGHT = 16

from gettext import (bindtextdomain, textdomain, bind_textdomain_codeset,
                     gettext as _)

import logging
log = logging.getLogger(__name__)

import windows
import theme
import curses
import difflib
import shlex
import text_buffer

from sleekxmpp.xmlstream.stanzabase import JID
from config import config
from roster import RosterGroup, roster
from contact import Contact, Resource
import multiuserchat as muc

class Tab(object):
    number = 0

    def __init__(self, core):
        self.core = core        # a pointer to core, to access its attributes (ugly?)
        self.nb = Tab.number
        Tab.number += 1
        self.size = (self.height, self.width) = self.core.stdscr.getmaxyx()
        if self.height < MIN_HEIGHT or self.width < MIN_WIDTH:
            self.visible = False
        else:
            self.visible = True
        self.key_func = {}      # each tab should add their keys in there
                                # and use them in on_input
        self.commands = {}      # and their own commands

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
                    return False # There's no completion functio
                else:
                    return command[2](the_input)
            else:
                # complete the command's name
                words = ['/%s'%(name) for name in list(self.core.commands.keys())] +\
                    ['/%s'% (name) for name in list(self.commands.keys())]
                the_input.auto_completion(words, '')
                return True
        return False

    def resize(self):
        self.size = (self.height, self.width) = self.core.stdscr.getmaxyx()
        if self.height < MIN_HEIGHT or self.width < MIN_WIDTH:
            self.visible = False
        else:
            self.visible = True

    def refresh(self, tabs, informations, roster):
        """
        Called on each screen refresh (when something has changed)
        """
        raise NotImplementedError

    def get_color_state(self):
        """
        returns the color that should be used in the GlobalInfoBar
        """
        return theme.COLOR_TAB_NORMAL

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
        pass

    def on_gain_focus(self):
        """
        called when this tab gains the focus.
        """
        pass

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
        pass

class ChatTab(Tab):
    """
    A tab containing a chat of any type.
    Just use this class instead of Tab if the tab needs a recent-words completion
    Also, \n, ^J and ^M are already bound to on_enter
    And also, add the /say command
    """
    def __init__(self, core, room):
        Tab.__init__(self, core)
        self._room = room
        self.key_func['M-/'] = self.last_words_completion
        self.key_func['^J'] = self.on_enter
        self.key_func['^M'] = self.on_enter
        self.key_func['\n'] = self.on_enter
        self.commands['say'] =  (self.command_say,
                                 _("""Usage: /say <message>\nSay: Just send the message.
                                        Useful if you want your message to begin with a '/'"""), None)

    def last_words_completion(self):
        """
        Complete the input with words recently said
        """
        # build the list of the recent words
        char_we_dont_want = [',', '(', ')', '.', '"', '\'', ' ', # The last one is nbsp
                             '’', '“', '”', ':', ';', '[', ']', '{', '}']
        words = list()
        for msg in self._room.messages[:-40:-1]:
            if not msg:
                continue
            txt = msg.txt
            for char in char_we_dont_want:
                txt = txt.replace(char, ' ')
            for word in txt.split():
                if len(word) >= 4 and word not in words:
                    words.append(word)
        self.input.auto_completion(words, ' ')

    def on_enter(self):
        txt = self.input.key_enter()
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
        else:
            if txt.startswith('//'):
                txt = txt[1:]
            self.command_say(txt)

    def command_say(self, line):
        raise NotImplementedError

class InfoTab(ChatTab):
    """
    The information tab, used to display global informations
    when using a anonymous account
    """
    def __init__(self, core):
        Tab.__init__(self, core)
        self.tab_win = windows.GlobalInfoBar()
        self.info_win = windows.TextWin()
        self.core.information_buffer.add_window(self.info_win)
        self.input = windows.Input()
        self.name = "Info"
        self.color_state = theme.COLOR_TAB_NORMAL
        self.key_func['^J'] = self.on_enter
        self.key_func['^M'] = self.on_enter
        self.key_func['\n'] = self.on_enter
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
        self.resize()

    def resize(self):
        Tab.resize(self)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr)
        self.info_win.resize(self.height-2, self.width, 0, 0, self.core.stdscr)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)

    def refresh(self, tabs, informations, _):
        if not self.visible:
            return
        self.info_win.refresh(informations)
        self.tab_win.refresh(tabs, tabs[0])
        self.input.refresh()

    def on_enter(self):
        # TODO duplicate
        txt = self.input.get_text()
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

    def on_close(self):
        return

class MucTab(ChatTab):
    """
    The tab containing a multi-user-chat room.
    It contains an userlist, an input, a topic, an information and a chat zone
    """
    def __init__(self, core, room):
        ChatTab.__init__(self, core, room)
        self.topic_win = windows.Topic()
        self.text_win = windows.TextWin()
        room.add_window(self.text_win)
        self.v_separator = windows.VerticalSeparator()
        self.user_win = windows.UserList()
        self.info_header = windows.MucInfoWin()
        self.info_win = windows.TextWin()
        self.core.information_buffer.add_window(self.info_win)
        self.tab_win = windows.GlobalInfoBar()
        self.input = windows.MessageInput()
        self.ignores = []       # set of Users
        # keys
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
        # commands
        self.commands['ignore'] = (self.command_ignore, _("Usage: /ignore <nickname> \nIgnore: Ignore a specified nickname."), None)
        self.commands['unignore'] = (self.command_unignore, _("Usage: /unignore <nickname>\nUnignore: Remove the specified nickname from the ignore list."), None)
        self.commands['kick'] =  (self.command_kick, _("Usage: /kick <nick> [reason]\nKick: Kick the user with the specified nickname. You also can give an optional reason."), None)
        self.commands['topic'] = (self.command_topic, _("Usage: /topic <subject>\nTopic: Change the subject of the room"), None)
        self.commands['query'] = (self.command_query, _('Usage: /query <nick> [message]\nQuery: Open a private conversation with <nick>. This nick has to be present in the room you\'re currently in. If you specified a message after the nickname, it will immediately be sent to this user'), None)
        self.commands['part'] = (self.command_part, _("Usage: /part [message]\n Part: disconnect from a room. You can specify an optional message."), None)
        self.commands['nick'] = (self.command_nick, _("Usage: /nick <nickname>\nNick: Change your nickname in the current room"), None)
        self.commands['recolor'] = (self.command_recolor, _('Usage: /recolor\nRecolor: Re-assign a color to all participants of the current room, based on the last time they talked. Use this if the participants currently talking have too many identical colors.'), None)
        self.resize()

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
            i+= 1
        self.text_win.rebuild_everything(self.get_room())
        self.core.refresh_window()

    def command_nick(self, arg):
        """
        /nick <nickname>
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.core.information(str(error), _("Error"))
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
        reason = None
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
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.core.information(str(error), _("Error"))
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

    def command_kick(self, arg):
        """
        /kick <nick> [reason]
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.core.information(str(error), _("Error"))
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
        muc.send_groupchat_message(self.core.xmpp, self.get_name(), line)

    def command_ignore(self, arg):
        """
        /ignore <nick>
        """
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.core.information(str(error), _("Error"))
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
        try:
            args = shlex.split(arg)
        except ValueError as error:
            return self.core.information(str(error), _("Error"))
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

    def resize(self):
        """
        Resize the whole window. i.e. all its sub-windows
        """
        Tab.resize(self)
        text_width = (self.width//10)*9
        self.topic_win.resize(1, self.width, 0, 0, self.core.stdscr)
        self.text_win.resize(self.height-4-self.core.information_win_size, text_width, 1, 0, self.core.stdscr)
        self.text_win.rebuild_everything(self._room)
        self.v_separator.resize(self.height-3, 1, 1, 9*(self.width//10), self.core.stdscr)
        self.user_win.resize(self.height-3, self.width-text_width-1, 1, text_width+1, self.core.stdscr)
        self.info_header.resize(1, (self.width//10)*9, self.height-3-self.core.information_win_size, 0, self.core.stdscr)
        self.info_win.resize(self.core.information_win_size, (self.width//10)*9, self.height-2-self.core.information_win_size, 0, self.core.stdscr, self.core.information_buffer)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)

    def refresh(self, tabs, informations, _):
        if not self.visible:
            return
        self.topic_win.refresh(self._room.topic)
        self.text_win.refresh(self._room)
        self.v_separator.refresh()
        self.user_win.refresh(self._room.users)
        self.info_header.refresh(self._room, self.text_win)
        self.tab_win.refresh(tabs, tabs[0])
        self.info_win.refresh(informations)
        self.input.refresh()

    def on_input(self, key):
        if key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key)
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

    def on_gain_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_CURRENT)
        curses.curs_set(1)

    def on_scroll_up(self):
        self.text_win.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self.text_win.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self):
        text_width = (self.width//10)*9
        self.text_win.resize(self.height-4-self.core.information_win_size, text_width, 1, 0, self.core.stdscr)
        self.info_header.resize(1, (self.width//10)*9, self.height-3-self.core.information_win_size, 0, self.core.stdscr)
        self.info_win.resize(self.core.information_win_size, (self.width//10)*9, self.height-2-self.core.information_win_size, 0, self.core.stdscr)

    def just_before_refresh(self):
        return

    def on_close(self):
        return

class PrivateTab(ChatTab):
    """
    The tab containg a private conversation (someone from a MUC)
    """
    def __init__(self, core, room):
        ChatTab.__init__(self, core, room)
        self.text_win = windows.TextWin()
        room.add_window(self.text_win)
        self.info_header = windows.PrivateInfoWin()
        self.info_win = windows.TextWin()
        self.core.information_buffer.add_window(self.info_win)
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
        muc.send_private_message(self.core.xmpp, self.get_name(), line)
        self.core.add_message_to_text_buffer(self.get_room(), line, None, self.get_room().own_nick)

    def command_unquery(self, arg):
        """
        /unquery
        """
        self.core.close_tab()

    def resize(self):
        Tab.resize(self)
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0, self.core.stdscr)
        self.text_win.rebuild_everything(self._room)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0, self.core.stdscr)
        self.info_win.resize(self.core.information_win_size, self.width, self.height-2-self.core.information_win_size, 0, self.core.stdscr, self.core.information_buffer)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)

    def refresh(self, tabs, informations, _):
        if not self.visible:
            return
        self.text_win.refresh(self._room)
        self.info_header.refresh(self._room, self.text_win)
        self.info_win.refresh(informations)
        self.tab_win.refresh(tabs, tabs[0])
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
        self.input.do_command(key)
        return False

    def on_lose_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_NORMAL)
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator()

    def on_gain_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_CURRENT)
        curses.curs_set(1)

    def on_scroll_up(self):
        self.text_win.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self.text_win.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self):
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0, self.core.stdscr)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0, self.core.stdscr)
        self.info_win.resize(self.core.information_win_size, self.width, self.height-2-self.core.information_win_size, 0, self.core.stdscr, None)

    def get_room(self):
        return self._room

    def get_text_window(self):
        return self.text_win

    def just_before_refresh(self):
        return

    def on_close(self):
        return

class RosterInfoTab(Tab):
    """
    A tab, splitted in two, containing the roster and infos
    """
    def __init__(self, core):
        Tab.__init__(self, core)
        self.name = "Roster"
        self.v_separator = windows.VerticalSeparator()
        self.tab_win = windows.GlobalInfoBar()
        self.info_win = windows.TextWin()
        self.core.information_buffer.add_window(self.info_win)
        self.roster_win = windows.RosterWin()
        self.contact_info_win = windows.ContactInfoWin()
        self.default_help_message = windows.HelpText("Enter commands with “/”. “o”: toggle offline show")
        self.input = self.default_help_message
        self.set_color_state(theme.COLOR_TAB_NORMAL)
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
        self.key_func["^J"] = self.on_enter
        self.key_func["^M"] = self.on_enter
        self.key_func[' '] = self.on_space
        self.key_func["/"] = self.on_slash
        self.key_func["KEY_UP"] = self.move_cursor_up
        self.key_func["KEY_DOWN"] = self.move_cursor_down
        self.key_func["o"] = self.toggle_offline_show
        self.key_func["^F"] = self.start_search
        self.resize()

    def resize(self):
        Tab.resize(self)
        roster_width = self.width//2
        info_width = self.width-roster_width-1
        self.v_separator.resize(self.height-2, 1, 0, roster_width, self.core.stdscr)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr)
        self.info_win.resize(self.height-2, info_width, 0, roster_width+1, self.core.stdscr, self.core.information_buffer)
        self.roster_win.resize(self.height-2-3, roster_width, 0, 0, self.core.stdscr)
        self.contact_info_win.resize(3, roster_width, self.height-2-3, 0, self.core.stdscr)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)

    def completion(self):
        # Check if we are entering a command (with the '/' key)
        if isinstance(self.input, windows.CommandInput) and\
                not self.input.help_message:
            self.complete_commands(self.input)

    def refresh(self, tabs, informations, roster):
        if not self.visible:
            return
        self.v_separator.refresh()
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
        # self.core.global_information_win.refresh(informations)
        self.info_win.refresh(informations)
        self.tab_win.refresh(tabs, tabs[0])
        self.input.refresh()

    def get_name(self):
        return self.name

    def get_color_state(self):
        return self._color_state

    def set_color_state(self, color):
        self._color_state = color

    def on_input(self, key):
        res = self.input.do_command(key)
        if res:
            return True
        if key in self.key_func:
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
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)
        self.input.do_command("/") # we add the slash

    def reset_help_message(self, _=None):
        curses.curs_set(0)
        self.input = self.default_help_message
        return True

    def execute_slash_command(self, txt):
        if txt.startswith('/'):
            self.core.execute(txt)
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

    def on_scroll_down(self):
        # Scroll info win
        pass

    def on_scroll_up(self):
        # Scroll info down
        pass

    def on_info_win_size_changed(self):
        pass

    def on_space(self):
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, RosterGroup) or\
                isinstance(selected_row, Contact):
            selected_row.toggle_folded()
            return True

    def on_enter(self):
        selected_row = self.roster_win.get_selected_row()
        self.core.on_roster_enter_key(selected_row)
        return selected_row

    def start_search(self):
        """
        Start the search. The input should appear with a short instruction
        in it.
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("[Search]", self.on_search_terminate, self.on_search_terminate, self.set_roster_filter)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)
        return True

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
    def __init__(self, core, jid):
        txt_buff = text_buffer.TextBuffer()
        ChatTab.__init__(self, core, txt_buff)
        self.color_state = theme.COLOR_TAB_NORMAL
        self._name = jid        # a conversation tab is linked to one specific full jid OR bare jid
        self.text_win = windows.TextWin()
        txt_buff.add_window(self.text_win)
        self.upper_bar = windows.ConversationStatusMessageWin()
        self.info_header = windows.ConversationInfoWin()
        self.info_win = windows.TextWin()
        self.core.information_buffer.add_window(self.info_win)
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
        muc.send_private_message(self.core.xmpp, self.get_name(), line)
        self.core.add_message_to_text_buffer(self.get_room(), line, None, self.core.own_nick)

    def command_unquery(self, arg):
        self.core.close_tab()

    def resize(self):
        Tab.resize(self)
        self.text_win.resize(self.height-4-self.core.information_win_size, self.width, 1, 0, self.core.stdscr)
        self.text_win.rebuild_everything(self._room)
        self.upper_bar.resize(1, self.width, 0, 0, self.core.stdscr)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0, self.core.stdscr)
        self.info_win.resize(self.core.information_win_size, self.width, self.height-2-self.core.information_win_size, 0, self.core.stdscr, self.core.information_buffer)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)

    def refresh(self, tabs, informations, roster):
        if not self.visible:
            return
        self.text_win.refresh(self._room)
        self.upper_bar.refresh(self.get_name(), roster.get_contact_by_jid(self.get_name()))
        self.info_header.refresh(self.get_name(), roster.get_contact_by_jid(self.get_name()), self._room, self.text_win)
        self.info_win.refresh(informations)
        self.tab_win.refresh(tabs, tabs[0])
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
        self.input.do_command(key)
        return False

    def on_lose_focus(self):
        self.set_color_state(theme.COLOR_TAB_NORMAL)
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator()

    def on_gain_focus(self):
        self.set_color_state(theme.COLOR_TAB_CURRENT)
        curses.curs_set(1)

    def on_scroll_up(self):
        self.text_win.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self.text_win.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self):
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0, self.core.stdscr)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0, self.core.stdscr)
        self.info_win.resize(self.core.information_win_size, self.width, self.height-2-self.core.information_win_size, 0, self.core.stdscr)

    def get_room(self):
        return self._room

    def get_text_window(self):
        return self.text_win

    def just_before_refresh(self):
        return

    def on_close(self):
        return

class MucListTab(Tab):
    """
    A tab listing rooms from a specific server, displaying various information,
    scrollable, and letting the user join them, etc
    """
    def __init__(self, core, server):
        Tab.__init__(self, core)
        self._color_state = theme.COLOR_TAB_NORMAL
        self.name = server
        self.upper_message = windows.Topic()
        columns = ('node-part','name', 'users')
        self.list_header = windows.ColumnHeaderWin(columns)
        self.listview = windows.ListWin(columns)
        self.tab_win = windows.GlobalInfoBar()
        self.default_help_message = windows.HelpText("“j”: join room.")
        self.input = self.default_help_message
        self.key_func["KEY_DOWN"] = self.listview.move_cursor_down
        self.key_func["KEY_UP"] = self.listview.move_cursor_up
        self.key_func["/"] = self.on_slash
        self.key_func['j'] = self.join_selected
        self.key_func['J'] = self.join_selected_no_focus
        self.key_func['^J'] = self.join_selected
        self.key_func['^M'] = self.join_selected
        self.resize()

    def refresh(self, tabs, informations, roster):
        self.upper_message.refresh('Chatroom list on server %s' % self.name)
        self.list_header.refresh()
        self.listview.refresh()
        self.tab_win.refresh(tabs, tabs[0])
        self.input.refresh()

    def resize(self):
        Tab.resize(self)
        self.upper_message.resize(1, self.width, 0, 0, self.core.stdscr)
        column_size = {'node-part': (self.width-5)//4,
                       'name': (self.width-5)//4*3,
                       'users': 5}
        self.list_header.resize_columns(column_size)
        self.list_header.resize(1, self.width, 1, 0, self.core.stdscr)
        self.listview.resize_columns(column_size)
        self.listview.resize(self.height-4, self.width, 2, 0, self.core.stdscr)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)

    def on_slash(self):
        """
        '/' is pressed, activate the input
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message, self.execute_slash_command)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)
        self.input.do_command("/") # we add the slash

    def join_selected_no_focus(self):
        return

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
            self.core.execute(txt)
        return self.reset_help_message()

    def get_name(self):
        return self.name

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
    def __init__(self, core, text):
        Tab.__init__(self, core)
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
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)
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
        self.text_win.resize(self.height-2, self.width, 0, 0, self.core.stdscr)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr)

    def refresh(self, tabs, information, roster):
        self.text_win.refresh()
        self.tab_win.refresh(tabs, tabs[0])
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
