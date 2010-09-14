# Copyright 2010 Le Coz Florent <louizatakk@fedoraproject.org>
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
a Tab object is a way to organize various Window (see window.py)
around the screen at once.
A tab is then composed of multiple Window.
Each Tab object has different refresh() and resize() methods, defining of its
Window are displayed, etc
"""

MIN_WIDTH = 50
MIN_HEIGHT = 16

import window
import theme

from common import debug

class Tab(object):
    """
    """
    number = 0

    def __init__(self, stdscr):
        self.nb = Tab.number
        Tab.number += 1
        self.size = (self.height, self.width) = stdscr.getmaxyx()
        if self.height < MIN_HEIGHT or self.width < MIN_WIDTH:
            self.visible = False
        else:
            self.visible = True

    def refresh(self, tabs, informations):
        """
        Called on each screen refresh (when something has changed)
        """
        raise NotImplementedError

    def resize(self, stdscr):
        self.size = (self.height, self.width) = stdscr.getmaxyx()
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

    def on_info_win_size_changed(self, size, stdscr):
        """
        Called when the window with the informations is resized
        """
        raise NotImplementedError

class InfoTab(Tab):
    """
    The information tab, used to display global informations
    when using a anonymous account
    """
    def __init__(self, stdscr, name):
        Tab.__init__(self, stdscr)
        self.tab_win = window.GlobalInfoBar(1, self.width, self.height-2, 0, stdscr, self.visible)
        self.text_win = window.TextWin(self.height-2, self.width, 0, 0, stdscr, self.visible)
        self.input = window.Input(1, self.width, self.height-1, 0, stdscr, self.visible)
        self.name = name
        self.color_state = theme.COLOR_TAB_NORMAL

    def resize(self, stdscr):
        Tab.resize(self, stdscr)
        self.tab_win.resize(1, self.width, self.height-2, 0, stdscr, self.visible)
        self.text_win.resize(self.height-2, self.width, 0, 0, stdscr, self.visible)
        self.input.resize(1, self.width, self.height-1, 0, stdscr, self.visible)

    def refresh(self, tabs, informations):
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

    def on_scroll_up(self):
        pass

    def on_scroll_down(self):
        pass

    def on_info_win_size_changed(self, size, stdscr):
        return

class MucTab(Tab):
    """
    The tab containing a multi-user-chat room.
    It contains an userlist, an input, a topic, an information and a chat zone
    """
    def __init__(self, stdscr, room, info_win_size):
        """
        room is a Room object
        The stdscr is passed to know the size of the
        terminal
        """
        Tab.__init__(self, stdscr)
        self._room = room
        self.info_win_size = info_win_size
        self.topic_win = window.Topic(1, self.width, 0, 0, stdscr, self.visible)
        self.text_win = window.TextWin(self.height-4-info_win_size, (self.width//10)*9, 1, 0, stdscr, self.visible)
        self.v_separator = window.VerticalSeparator(self.height-3, 1, 1, 9*(self.width//10), stdscr, self.visible)
        self.user_win = window.UserList(self.height-3, (self.width//10), 1, 9*(self.width//10)+1, stdscr, self.visible)
        self.info_header = window.MucInfoWin(1, (self.width//10)*9, self.height-3-self.info_win_size, 0, stdscr, self.visible)
        self.info_win = window.TextWin(info_win_size, (self.width//10)*9, self.height-2-self.info_win_size, 0, stdscr, self.visible)
        self.tab_win = window.GlobalInfoBar(1, self.width, self.height-2, 0, stdscr, self.visible)
        self.input = window.Input(1, self.width, self.height-1, 0, stdscr, self.visible)

    def resize(self, stdscr):
        """
        Resize the whole window. i.e. all its sub-windows
        """
        Tab.resize(self, stdscr)
        text_width = (self.width//10)*9
        self.topic_win.resize(1, self.width, 0, 0, stdscr, self.visible)
        self.text_win.resize(self.height-4-self.info_win_size, text_width, 1, 0, stdscr, self.visible)
        self.v_separator.resize(self.height-3, 1, 1, 9*(self.width//10), stdscr, self.visible)
        self.user_win.resize(self.height-3, self.width-text_width-1, 1, text_width+1, stdscr, self.visible)
        self.info_header.resize(1, (self.width//10)*9, self.height-3-self.info_win_size, 0, stdscr, self.visible)
        self.info_win.resize(self.info_win_size, (self.width//10)*9, self.height-2-self.info_win_size, 0, stdscr, self.visible)
        self.tab_win.resize(1, self.width, self.height-2, 0, stdscr, self.visible)
        self.input.resize(1, self.width, self.height-1, 0, stdscr, self.visible)

    def refresh(self, tabs, informations):
        self.topic_win.refresh(self._room.topic)
        self.text_win.refresh(self._room)
        self.v_separator.refresh()
        self.user_win.refresh(self._room.users)
        self.info_header.refresh(self._room)
        self.info_win.refresh(informations)
        self.tab_win.refresh(tabs, tabs[0])
        self.input.refresh()

    def on_input(self, key):
        self.key_func = {
            "\t": self.completion,
            "^I": self.completion,
            "KEY_BTAB": self.last_words_completion,
            }
        if key in self.key_func:
            return self.key_func[key]()
        return self.input.do_command(key)

    def completion(self):
        """
        Called when Tab is pressed, complete the nickname in the input
        """
        compare_users = lambda x: x.last_talked
        self.input.auto_completion([user.nick for user in sorted(self._room.users, key=compare_users, reverse=True)])

    def last_words_completion(self):
        """
        Complete the input with words recently said
        """
        # build the list of the recent words
        char_we_dont_want = [',', '(', ')', '.']
        words = list()
        for msg in self._room.messages[:-40:-1]:
            if not msg:
                continue
            for char in char_we_dont_want:
                msg.txt.replace(char, ' ')
            for word in msg.txt.split():
                if len(word) > 5:
                    words.append(word)
        self.input.auto_completion(words, False)

    def get_color_state(self):
        """
        """
        return self._room.color_state

    def set_color_state(self, color):
        """
        """
        self._room.set_color_state(color)

    def get_name(self):
        """
        """
        return self._room.name

    def get_room(self):
        return self._room

    def on_lose_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_NORMAL)
        self._room.remove_line_separator()

    def on_gain_focus(self):
        self._room.add_line_separator()
        self._room.set_color_state(theme.COLOR_TAB_CURRENT)

    def on_scroll_up(self):
        self._room.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self._room.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self, size, stdscr):
        self.info_win_size = size
        text_width = (self.width//10)*9
        self.text_win.resize(self.height-4-self.info_win_size, text_width, 1, 0, stdscr, self.visible)
        self.info_header.resize(1, (self.width//10)*9, self.height-3-self.info_win_size, 0, stdscr, self.visible)
        self.info_win.resize(self.info_win_size, (self.width//10)*9, self.height-2-self.info_win_size, 0, stdscr, self.visible)

class PrivateTab(Tab):
    """
    The tab containg a private conversation (someone from a MUC)
    """
    def __init__(self, stdscr, room, info_win_size):
        Tab.__init__(self, stdscr)
        self.info_win_size = info_win_size
        self._room = room
        self.text_win = window.TextWin(self.height-2-self.info_win_size, self.width, 0, 0, stdscr, self.visible)
        self.info_header = window.PrivateInfoWin(1, self.width, self.height-3-self.info_win_size, 0, stdscr, self.visible)
        self.info_win = window.TextWin(self.info_win_size, self.width, self.height-2-self.info_win_size, 0, stdscr, self.visible)
        self.tab_win = window.GlobalInfoBar(1, self.width, self.height-2, 0, stdscr, self.visible)
        self.input = window.Input(1, self.width, self.height-1, 0, stdscr, self.visible)

    def resize(self, stdscr):
        Tab.resize(self, stdscr)
        self.text_win.resize(self.height-2-self.info_win_size, self.width, 0, 0, stdscr, self.visible)
        self.info_header.resize(1, self.width, self.height-3-self.info_win_size, 0, stdscr, self.visible)
        self.info_win.resize(self.info_win_size, self.width, self.height-2-self.info_win_size, 0, stdscr, self.visible)
        self.tab_win.resize(1, self.width, self.height-2, 0, stdscr, self.visible)
        self.input.resize(1, self.width, self.height-1, 0, stdscr, self.visible)

    def refresh(self, tabs, informations):
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
        return self.input.do_command(key)

    def on_lose_focus(self):
        self._room.set_color_state(theme.COLOR_TAB_NORMAL)
        self._room.remove_line_separator()

    def on_gain_focus(self):
        self._room.add_line_separator()
        self._room.set_color_state(theme.COLOR_TAB_CURRENT)

    def on_scroll_up(self):
        self._room.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        self._room.scroll_down(self.text_win.height-1)

    def on_info_win_size_changed(self, size, stdscr):
        self.info_win_size = size
        self.text_win.resize(self.height-2, self.width, 0, 0, stdscr, self.visible)
        self.info_header.resize(1, self.width, self.height-3-self.info_win_size, 0, stdscr, self.visible)
        self.info_win.resize(self.info_win_size, (self.width//10)*9, self.height-2-self.info_win_size, 0, stdscr, self.visible)

        # self.text_win.resize(self.height-4-self.info_win_size, text_width, 1, 0, stdscr, self.visible)
        # self.info_header.resize(1, (self.width//10)*9, self.height-3-self.info_win_size, 0, stdscr, self.visible)
        # self.info_win.resize(self.info_win_size, (self.width//10)*9, self.height-2-self.info_win_size, 0, stdscr, self.visible)

    def get_room(self):
        return self._room
