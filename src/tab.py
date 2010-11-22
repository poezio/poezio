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

"""
a Tab object is a way to organize various Windows (see windows.py)
around the screen at once.
A tab is then composed of multiple Buffer.
Each Tab object has different refresh() and resize() methods, defining how its
Buffer are displayed, resized, etc
"""

MIN_WIDTH = 50
MIN_HEIGHT = 16

import logging
log = logging.getLogger(__name__)

import windows
import theme
import curses
import difflib

from sleekxmpp.xmlstream.stanzabase import JID
from config import config
from roster import RosterGroup, roster
from contact import Contact, Resource

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

    def refresh(self, tabs, informations, roster):
        """
        Called on each screen refresh (when something has changed)
        """
        raise NotImplementedError

    def resize(self):
        self.size = (self.height, self.width) = self.core.stdscr.getmaxyx()
        if self.height < MIN_HEIGHT or self.width < MIN_WIDTH:
            self.visible = False
        else:
            self.visible = True

    def get_color_state(self):
        """
        returns the color that should be used in the GlobalInfoBar
        """
        raise NotImplementedError

    def set_color_state(self, color):
        """
        set the color state
        """
        raise NotImplementedError

    def get_name(self):
        """
        get the name of the tab
        """
        raise NotImplementedError

    def on_input(self, key):
        raise NotImplementedError

    def on_lose_focus(self):
        """
        called when this tab loses the focus.
        """
        raise NotImplementedError

    def on_gain_focus(self):
        """
        called when this tab gains the focus.
        """
        raise NotImplementedError

    def add_message(self):
        """
        Adds a message in the tab.
        If the tab cannot add a message in itself (for example
        FormTab, where text is not intented to be appened), it returns False.
        If the tab can, it returns True
        """
        raise NotImplementedError

    def on_scroll_down(self):
        """
        Defines what happens when we scrol down
        """
        raise NotImplementedError

    def on_scroll_up(self):
        """
        Defines what happens when we scrol down
        """
        raise NotImplementedError

    def on_info_win_size_changed(self):
        """
        Called when the window with the informations is resized
        """
        raise NotImplementedError

    def just_before_refresh(self):
        """
        Method called just before the screen refresh.
        Particularly useful to move the cursor at the
        correct position.
        """
        raise NotImplementedError

    def on_close(self):
        """
        Called when the tab is to be closed
        """
        raise NotImplementedError

class InfoTab(Tab):
    """
    The information tab, used to display global informations
    when using a anonymous account
    """
    def __init__(self, core, name):
        Tab.__init__(self, core)
        self.tab_win = windows.GlobalInfoBar()
        self.text_win = windows.TextWin()
        self.input = windows.Input()
        self.name = name
        self.color_state = theme.COLOR_TAB_NORMAL
        self.resize()

    def resize(self):
        Tab.resize(self)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr, self.visible)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr, self.visible)
        self.text_win.resize(self.height-2, self.width, 0, 0, self.core.stdscr, self.visible)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr, self.visible)

    def refresh(self, tabs, informations, _):
        self.text_win.refresh(informations)
        self.tab_win.refresh(tabs, tabs[0])
        self.input.refresh()

    def get_name(self):
        return self.name

    def get_color_state(self):
        return self.color_state

    def set_color_state(self, color):
        return

    def on_input(self, key):
        return self.input.do_command(key)

    def on_lose_focus(self):
        self.color_state = theme.COLOR_TAB_NORMAL

    def on_gain_focus(self):
        self.color_state = theme.COLOR_TAB_CURRENT
        curses.curs_set(0)

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

class ChatTab(Tab):
    """
    A tab containing a chat of any type.
    Just use this class instead of Tab if the tab needs a recent-words completion
    Also, \n, ^J and ^M are already bound to on_enter
    """
    def __init__(self, core, room):
        Tab.__init__(self, core)
        self._room = room
        self.key_func['M-/'] = self.last_words_completion
        self.key_func['^J'] = self.on_enter
        self.key_func['^M'] = self.on_enter
        self.key_func['\n'] = self.on_enter

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
            for char in char_we_dont_want:
                msg.txt = msg.txt.replace(char, ' ')
            for word in msg.txt.split():
                if len(word) >= 4 and word not in words:
                    words.append(word)
        self.input.auto_completion(words, False)

    def on_enter(self):
        raise NotImplementedError

class MucTab(ChatTab):
    """
    The tab containing a multi-user-chat room.
    It contains an userlist, an input, a topic, an information and a chat zone
    """
    def __init__(self, core, room):
        ChatTab.__init__(self, core, room)
        self.topic_win = windows.Topic()
        self.text_win = windows.TextWin()
        self.v_separator = windows.VerticalSeparator()
        self.user_win = windows.UserList()
        self.info_header = windows.MucInfoWin()
        self.info_win = windows.TextWin()
        self.tab_win = windows.GlobalInfoBar()
        self.input = windows.MessageInput()
        self.key_func['^I'] = self.completion
        self.key_func['M-i'] = self.completion
        self.resize()

    def resize(self):
        """
        Resize the whole window. i.e. all its sub-windows
        """
        Tab.resize(self)
        text_width = (self.width//10)*9
        self.topic_win.resize(1, self.width, 0, 0, self.core.stdscr, self.visible)
        self.text_win.resize(self.height-4-self.core.information_win_size, text_width, 1, 0, self.core.stdscr, self.visible)
        self.v_separator.resize(self.height-3, 1, 1, 9*(self.width//10), self.core.stdscr, self.visible)
        self.user_win.resize(self.height-3, self.width-text_width-1, 1, text_width+1, self.core.stdscr, self.visible)
        self.info_header.resize(1, (self.width//10)*9, self.height-3-self.core.information_win_size, 0, self.core.stdscr, self.visible)
        self.info_win.resize(self.core.information_win_size, (self.width//10)*9, self.height-2-self.core.information_win_size, 0, self.core.stdscr, self.visible)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr, self.visible)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr, self.visible)

    def refresh(self, tabs, informations, _):
        self.topic_win.refresh(self._room.topic)
        self.text_win.refresh(self._room)
        self.v_separator.refresh()
        self.user_win.refresh(self._room.users)
        self.info_header.refresh(self._room)
        self.info_win.refresh(informations)
        self.tab_win.refresh(tabs, tabs[0])
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
        compare_users = lambda x: x.last_talked
        self.input.auto_completion([user.nick for user in sorted(self._room.users, key=compare_users, reverse=True)])

    def on_enter(self):
        """
        When enter is pressed, send the message to the Muc
        """
        self.core.execute(self.input.key_enter())

    def get_color_state(self):
        return self._room.color_state

    def set_color_state(self, color):
        self._room.set_color_state(color)

    def get_name(self):
        return self._room.name

    def get_room(self):
        return self._room

    def on_lose_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_NORMAL)
        self._room.remove_line_separator()
        self._room.add_line_separator()

    def on_gain_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_CURRENT)
        curses.curs_set(1)

    def on_scroll_up(self):
        self._room.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self._room.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self):
        text_width = (self.width//10)*9
        self.text_win.resize(self.height-4-self.core.information_win_size, text_width, 1, 0, self.core.stdscr, self.visible)
        self.info_header.resize(1, (self.width//10)*9, self.height-3-self.core.information_win_size, 0, self.core.stdscr, self.visible)
        self.info_win.resize(self.core.information_win_size, (self.width//10)*9, self.height-2-self.core.information_win_size, 0, self.core.stdscr, self.visible)

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
        self.info_header = windows.PrivateInfoWin()
        self.info_win = windows.TextWin()
        self.tab_win = windows.GlobalInfoBar()
        self.input = windows.MessageInput()
        self.resize()

    def resize(self):
        Tab.resize(self)
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0, self.core.stdscr, self.visible)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0, self.core.stdscr, self.visible)
        self.info_win.resize(self.core.information_win_size, self.width, self.height-2-self.core.information_win_size, 0, self.core.stdscr, self.visible)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr, self.visible)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr, self.visible)

    def refresh(self, tabs, informations, _):
        self.text_win.refresh(self._room)
        self.info_header.refresh(self._room)
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
        return self.input.do_command(key)

    def on_enter(self):
        """
        When enter is pressed, send the message to the Muc
        """
        self.core.execute(self.input.key_enter())

    def on_lose_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_NORMAL)
        self._room.remove_line_separator()
        self._room.add_line_separator()

    def on_gain_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_CURRENT)
        curses.curs_set(1)

    def on_scroll_up(self):
        self._room.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self._room.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self):
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0, self.core.stdscr, self.visible)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0, self.core.stdscr, self.visible)
        self.info_win.resize(self.core.information_win_size, self.width, self.height-2-self.core.information_win_size, 0, self.core.stdscr, self.visible)

    def get_room(self):
        return self._room

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
        self.roster_win = windows.RosterWin()
        self.contact_info_win = windows.ContactInfoWin()
        self.default_help_message = windows.HelpText("Enter commands with “/”. “o”: toggle offline show")
        self.input = self.default_help_message
        self.set_color_state(theme.COLOR_TAB_NORMAL)
        self.resize()

    def resize(self):
        Tab.resize(self)
        roster_width = self.width//2
        info_width = self.width-roster_width-1
        self.v_separator.resize(self.height-2, 1, 0, roster_width, self.core.stdscr, self.visible)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr, self.visible)
        self.info_win.resize(self.height-2, info_width, 0, roster_width+1, self.core.stdscr, self.visible)
        self.roster_win.resize(self.height-2-3, roster_width, 0, 0, self.core.stdscr, self.visible)
        self.contact_info_win.resize(3, roster_width, self.height-2-3, 0, self.core.stdscr, self.visible)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr, self.visible)

    def refresh(self, tabs, informations, roster):
        self.v_separator.refresh()
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
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
        key_commands = {
            "^J": self.on_enter,
            "^M": self.on_enter,
            "\n": self.on_enter,
            ' ': self.on_space,
            "/": self.on_slash,
            "KEY_UP": self.move_cursor_up,
            "KEY_DOWN": self.move_cursor_down,
            "o": self.toggle_offline_show,
            "^F": self.start_search,
            }
        res = self.input.do_command(key)
        if res:
            return False
        if key in key_commands:
            return key_commands[key]()

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
        self.input = windows.CommandInput(1, self.width, self.height-1, 0, self.default_help_message, self.visible, "", self.reset_help_message, self.execute_slash_command)
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
        curses.curs_set(0)

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
        self.input = windows.CommandInput(1, self.width, self.height-1, 0, self.default_help_message, self.visible, "[Search]", self.on_search_terminate, self.on_search_terminate, self.set_roster_filter)
        return True

    def set_roster_filter(self, txt):
        roster._contact_filter = (jid_and_name_match, txt)

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
    The tab containg a normal conversation (someone from our roster)
    """
    def __init__(self, core, text_buffer, jid):
        ChatTab.__init__(self, core, text_buffer)
        self.color_state = theme.COLOR_TAB_NORMAL
        self._name = jid        # a conversation tab is linked to one specific full jid OR bare jid
        self.text_win = windows.TextWin()
        self.upper_bar = windows.ConversationStatusMessageWin()
        self.info_header = windows.ConversationInfoWin()
        self.info_win = windows.TextWin()
        self.tab_win = windows.GlobalInfoBar()
        self.input = windows.MessageInput()
        self.resize()

    def resize(self):
        Tab.resize(self)
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0, self.core.stdscr, self.visible)
        self.upper_bar.resize(1, self.width, 0, 0, self.core.stdscr, self.visible)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0, self.core.stdscr, self.visible)
        self.info_win.resize(self.core.information_win_size, self.width, self.height-2-self.core.information_win_size, 0, self.core.stdscr, self.visible)
        self.tab_win.resize(1, self.width, self.height-2, 0, self.core.stdscr, self.visible)
        self.input.resize(1, self.width, self.height-1, 0, self.core.stdscr, self.visible)

    def refresh(self, tabs, informations, roster):
        self.text_win.refresh(self._room)
        self.upper_bar.refresh(self.get_name(), roster.get_contact_by_jid(self.get_name()))
        self.info_header.refresh(self.get_name(), roster.get_contact_by_jid(self.get_name()), self._room)
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
        return True

    def on_enter(self):
        """
        When enter is pressed, send the message to the Muc
        """
        self.core.execute(self.input.key_enter())

    def on_lose_focus(self):
        self.set_color_state(theme.COLOR_TAB_NORMAL)
        self._room.remove_line_separator()
        self._room.add_line_separator()

    def on_gain_focus(self):
        self.set_color_state(theme.COLOR_TAB_CURRENT)
        curses.curs_set(1)

    def on_scroll_up(self):
        self._room.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self._room.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self):
        self.text_win.resize(self.height-3-self.core.information_win_size, self.width, 0, 0, self.core.stdscr, self.visible)
        self.info_header.resize(1, self.width, self.height-3-self.core.information_win_size, 0, self.core.stdscr, self.visible)
        self.info_win.resize(self.core.information_win_size, self.width, self.height-2-self.core.information_win_size, 0, self.core.stdscr, self.visible)

    def get_room(self):
        return self._room

    def just_before_refresh(self):
        return

    def on_close(self):
        return

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
