#!/usr/bin/python
# -*- coding:utf-8 -*-
#
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

import curses
from config import config

from common import debug

from message import Line

class Win(object):
    def __init__(self, height, width, y, x, parent_win):
        self._resize(height, width, y, x, parent_win)

    def _resize(self, height, width, y, x, parent_win):
        self.height, self.width, self.x, self.y = height, width, x, y
        try:
            self.win = parent_win.subwin(height, width, y, x)
        except:
            # When resizing in a too little height (less than 3 lines)
            # We don't need to resize the window, since this size
            # just makes no sense
            # Just don't crash when this happens.
            # (°>       also, a penguin
            # //\
            # V_/_
            pass
        self.win.idlok(1)
        self.win.leaveok(1)
        # self.win.syncok(0)

    def refresh(self):
        self.win.noutrefresh()

class UserList(Win):
    def __init__(self, height, width, y, x, parent_win, visible):
        Win.__init__(self, height, width, y, x, parent_win)
        self.visible = visible
        self.win.attron(curses.color_pair(2))
        # self.win.vline(0, 0, curses.ACS_VLINE, self.height)
        self.win.attroff(curses.color_pair(2))
        self.color_role = {'moderator': 3,
                           'participant':2,
                           'visitor':4
                           }
        self.color_show = {'xa':12,
                           'None':8,
                           'dnd':13,
                           'away':14,
                           'chat':15
                           }

    def refresh(self, users):
        if not self.visible:
            return
        self.win.erase()
        y = 0
        for user in users:
            try:
                role_col = self.color_role[user.role]
            except:
                role_col = 1
            try:
                show_col = self.color_show[user.show]
            except:
                show_col = 8
            self.win.attron(curses.color_pair(show_col))
            self.win.addnstr(y, 0, " ", 1)
            self.win.attroff(curses.color_pair(show_col))
            self.win.attron(curses.color_pair(role_col))
            self.win.addnstr(y, 1, user.nick, self.width-2)
            self.win.attroff(curses.color_pair(role_col))
            y += 1
            if y == self.height:
                break
        self.win.refresh()

    def resize(self, height, width, y, x, stdscr, visible):
        self.visible = visible
        if not visible:
            return
        self._resize(height, width, y, x, stdscr)

class Topic(Win):
    def __init__(self, height, width, y, x, parent_win, visible):
        self.visible = visible
        Win.__init__(self, height, width, y, x, parent_win)

    def resize(self, height, width, y, x, stdscr, visible):
        self._resize(height, width, y, x, stdscr)

    def refresh(self, room_name):
        if not self.visible:
            return
        self.win.erase()
        try:
            self.win.addnstr(0, 0, room_name + " "*(self.width-len(room_name)), self.width
                             , curses.color_pair(1))
        except:pass
        self.win.refresh()

class RoomInfo(Win):
    def __init__(self, height, width, y, x, parent_win, visible):
        self.visible = visible
        Win.__init__(self, height, width, y, x, parent_win)

    def resize(self, height, width, y, x, stdscr, visible):
        self._resize(height, width, y, x, stdscr)

    def refresh(self, rooms, current):
        if not self.visible:
            return
        def compare_room(a, b):
            return a.nb - b.nb
        self.win.erase()
        try:
            self.win.addnstr(0, 0, current.name+" [", self.width
                             ,curses.color_pair(1))
        except:
            pass
        sorted_rooms = sorted(rooms, compare_room)
        for room in sorted_rooms:
            if current == room:
                color = 10
            else:
                color = room.color_state
            try:
                self.win.addstr(str(room.nb), curses.color_pair(color))
                self.win.addstr(",", curses.color_pair(1))
            except:             # end of line
                break
        (y, x) = self.win.getyx()
        try:
            self.win.addstr(y, x-1, ']'+(' '*((self.width)-x)), curses.color_pair(1))
        except:
            pass
        self.win.refresh()

class TextWin(Win):
    """
    # keep a dict of {winname: window}
    # when a new message is received in a room, just add
    # the line at the bottom (and scroll if needed)
    # when the current room is changed, just refresh the
    # associated window
    # When the term is resized, rebuild ALL the windows
    # (the complete lines lists are keeped in the Room class)
    Nope, don't do that anymore.
    Weechat is doing it the easy way, and it's working, there's no
    reason poezio can't do it (it's python, but that shouldn't change
    anything)
    Just keep ONE single window for the text area and rewrite EVERYTHING
    on each change.
    """
    def __init__(self, height, width, y, x, parent_win, visible):
        self.visible = visible
        self.height = height
        self.width = width
        self.y = y
        self.x = x
        self.parent_win = parent_win
        Win.__init__(self, height, width, y, x, parent_win)
        self.win.scrollok(1)

    def build_lines_from_messages(self, messages):
        """
        From the n messages (n behing the height of the text area),
        returns the n last lines (Line object).
        """
        lines = []
        for message in messages:
            txt = message.txt
            offset = 11         # length of the time
            if message.nickname:
                offset += len(message.nickname) + 2 # + nick + spaces length
            first = True
            while txt != '':
                # debug(txt)
                if txt[:self.width-offset].find('\n') != -1:
                    limit = txt[:self.width-offset].find('\n')
                    # debug("=================="+str(limit))
                else:
                    limit = self.width-offset-1
                if first and message.user:
                    line = Line(message.nickname, message.user.color,
                                message.time,
                                txt[:limit], message.color,
                                offset)
                else:
                    line = Line(None, None,
                                message.time,
                                txt[:limit], message.color,
                                offset)
                lines.append(line)
                txt = txt[limit+1:]
                first = False
        return lines[-len(messages):]# return only the needed number of lines

    def refresh(self, room):
        """
        Build the Line objects from the messages, and then write
        them in the text area
        """
        from common import debug
        if not self.visible:
            return
        self.win.erase()
        if room.pos != 0:
            messages = room.messages[-self.height - room.pos : -room.pos]
        else:
            messages = room.messages[-self.height:]
        # lines = self.keep_n_lines(messages)
        lines = self.build_lines_from_messages(messages)
        y = 0
        for line in lines:
            self.win.move(y, 0)
            if line.time is not None:
                self.write_time(line.time)
            if line.nickname is not None:
                self.write_nickname(line.nickname.encode('utf-8'), line.nickname_color)
            # else:
            #     self.win.attron(curses.color_pair(8))
            # TODO on information
            self.write_text(y, line.text_offset, line.text, line.text_color)
            y += 1
            # if message.nickname is None:
            #     self.win.attroff(curses.color_pair(8))
        self.win.refresh()

    def write_text(self, y, x, txt, color):
        """
        return the number of line written, -1
        """
        txt = txt.encode('utf-8')
        if color:
            self.win.attron(curses.color_pair(color))
        self.win.addstr(y, x, txt)
        # while txt != '':
        #     # debug(txt)
        #     if txt[:self.width-x].find('\n') != -1:
        #         limit = txt[:self.width-x].find('\n')
        #         # debug("=================="+str(limit))
        #     else:
        #         limit = self.width-x
        #     self.win.addnstr(txt, limit)
        #     txt = txt[limit+1:]
        #     l += 1
        if color:
            self.win.attroff(curses.color_pair(color))
        # return l-1

    def write_nickname(self, nickname, color):
        """
        Write the nickname, using the user's color
        and return the number of written characters
        """
        self.win.attron(curses.color_pair(color))
        self.win.addstr(nickname)
        self.win.attroff(curses.color_pair(color))
        self.win.addnstr("> ", 2)

    def write_time(self, time):
        """
        Write the date on the yth line of the window
        """
        # debug(str(self.win.getmaxyx()))
        # debug(str(y))
        # debug('___________________')
        self.win.addnstr('['+time.strftime("%H"), 3)
        self.win.attron(curses.color_pair(9))
        self.win.addnstr(':', 1)
        self.win.attroff(curses.color_pair(9))
        self.win.addnstr(time.strftime('%M'), 2)
        self.win.attron(curses.color_pair(9))
        self.win.addnstr(':', 1)
        self.win.attroff(curses.color_pair(9))
        self.win.addnstr(time.strftime('%S') + "] ", 4)

    def resize(self, height, width, y, x, stdscr, visible):
        self.visible = visible
        self._resize(height, width, y, x, stdscr)

    # def redraw(self, room):
    #     """
    #     called when the buffer changes or is
    #     resized (a complete redraw is needed)
    #     """
    #     if not self.visible:
    #         return
    #     win = self.wins[room.name].win
    #     win.clear()
    #     win.move(0, 0)
    #     for line in room.lines:
    #         self.add_line(room, line)

    # def refresh(self, winname):
    #     self.
    #     if self.visible:
    #         self.wins[winname].refresh()

    # def add_line(self, room, line):
    #     if not self.visible:
    #         return
    #     win = self.wins[room.name].win
    #     users = room.users
    #     win.addstr('\n['+line[0].strftime("%H"))
    #     win.attron(curses.color_pair(9))
    #     win.addstr(':')
    #     win.attroff(curses.color_pair(9))
    #     win.addstr(line[0].strftime('%M'))
    #     win.attron(curses.color_pair(9))
    #     win.addstr(':')
    #     win.attroff(curses.color_pair(9))
    #     win.addstr(line[0].strftime('%S') + "] ")
    #     if len(line) == 2:
    #         try:
    #             win.attron(curses.color_pair(8))
    #             win.addstr(line[1])
    #             win.attroff(curses.color_pair(8))
    #         except:pass
    #     elif len(line) == 4:
    #         for user in users:
    #             if user.nick == line[1]:
    #                 break
    #         try:
    #             length = len('['+line[0].strftime("%H:%M:%S") + "] <")
    #             if line[1]:
    #                 win.attron(curses.color_pair(user.color))
    #                 win.addstr(line[1])
    #                 win.attroff(curses.color_pair(user.color))
    #             win.addstr("> ")
    #             if line[3]:
    #                 win.attron(curses.color_pair(line[3]))
    #             win.addstr(line[2])
    #             if line[3]:
    #                 win.attroff(curses.color_pair(line[3]))
    #         except:pass

    # def new_win(self, winname):
    #     newwin = Win(self.height, self.width, self.y, self.x, self.parent_win)
    #     newwin.win.idlok(True)
    #     newwin.win.scrollok(True)
    #     newwin.win.leaveok(1)
    #     self.wins[winname] = newwin

    # def resize(self, height, width, y, x, stdscr, visible):
    #     self.visible = visible
    #     if not visible:
    #         return
    #     for winname in self.wins.keys():
    #         self.wins[winname]._resize(height, width, y, x, stdscr)
    #         self.wins[winname].win.idlok(True)
    #         self.wins[winname].win.scrollok(True)
    #         self.wins[winname].win.leaveok(1)

class Input(Win):
    """
    """
    def __init__(self, height, width, y, x, stdscr, visible):
        Win.__init__(self, height, width, y, x, stdscr)
        self.win.leaveok(0)
        self.visible = visible
        self.history = []
        self.text = u''
        self.pos = 0
        self.histo_pos = 0
        self.hit_list = [] # current possible completion (normal)
        self.last_key_tab = False # True if we are cycling through possible completion

    def resize(self, height, width, y, x, stdscr, visible):
        self.visible = visible
        if not visible:
            return
        self._resize(height, width, y, x, stdscr)
        self.win.leaveok(0)
        self.win.clear()
        self.win.addnstr(0, 0, self.text.encode('utf-8'), self.width-1)

    def key_dc(self):
        """delete char"""
        if self.pos == len(self.text):
            return
        self.reset_completion()
        (y, x) = self.win.getyx()
        self.text = self.text[:self.pos]+self.text[self.pos+1:]
        self.win.delch(y, x)
        self.refresh()

    def key_up(self):
        if not len(self.history):
            return
        self.reset_completion()
        self.win.clear()
        if self.histo_pos >= 0:
            self.histo_pos -= 1
        self.text = self.history[self.histo_pos+1]
        if len(self.text) >= self.width-1:
            self.win.addstr(self.history[self.histo_pos+1][:self.width-1].encode('utf-8'))
        else:
            self.win.addstr(self.history[self.histo_pos+1].encode('utf-8'))
        self.pos = len(self.text)
        self.refresh()

    def key_down(self):
        if not len(self.history):
            return
        self.reset_completion()
        self.win.clear()
        if self.histo_pos < len(self.history)-1:
            self.histo_pos += 1
            self.text = self.history[self.histo_pos]
            if len(self.text) >= self.width-1:
                self.win.addstr(self.history[self.histo_pos][:self.width-1].encode('utf-8'))
            else:
                self.win.addstr(self.history[self.histo_pos].encode('utf-8'))
            self.pos = len(self.text)
        else:
            self.histo_pos = len(self.history)-1
            self.text = u''
            self.pos = 0
        self.refresh()

    def key_home(self):
        self.reset_completion()
        self.pos = 0
        if len(self.text) >= self.width-1:
            txt = self.text[:self.width-1]
            self.clear_text()
            self.win.addstr(txt)
        self.win.move(0, 0)
        self.refresh()

    def key_end(self):
        self.reset_completion()
        self.pos = len(self.text)
        if len(self.text) >= self.width-1:
            txt = self.text[-(self.width-1):]
            self.clear_text()
            self.win.addstr(txt)
            self.win.move(0, self.width-1)
        else:
            self.win.move(0, len(self.text))
        self.refresh()

    def key_left(self):
        self.reset_completion()
        (y, x) = self.win.getyx()
        if self.pos > 0:
            self.pos -= 1
            if x == 0:
                txt = self.text[self.pos:self.pos+self.width-1]
                self.clear_text()
                self.win.addstr(txt.encode('utf-8'))
                self.win.move(y, 0)
            else:
                self.win.move(y, x-1)
            self.refresh()

    def key_right(self):
        self.reset_completion()
        (y, x) = self.win.getyx()
        if self.pos < len(self.text):
            self.pos += 1
            if x == self.width-1:
                txt = self.text[self.pos-(self.width-1):self.pos]
                self.clear_text()
                self.win.addstr(txt.encode('utf-8'))
                self.win.move(y, self.width-1)
            else:
                self.win.move(y, x+1)
            self.refresh()

    def key_backspace(self):
        self.reset_completion()
        (y, x) = self.win.getyx()
        if len(self.text) > 0 and self.pos != 0:
            self.text = self.text[:self.pos-1]+self.text[self.pos:]
            self.pos -= 1
            self.win.delch(y, x-1)
            self.refresh()

    def auto_completion(self, user_list):
        if self.pos != len(self.text) or len(self.text) == 0:
            return # we don't complete if cursor is not at the end of line
        completion_type = config.get('completion', 'normal')
        if completion_type == 'shell':
            self.shell_completion(user_list)
        else:
            self.normal_completion(user_list)

    def reset_completion(self):
        self.hit_list = []
        self.last_key_tab = False

    def normal_completion(self, user_list):
        if " " in self.text.strip():
            after = " " # don't put the "," if it's not the begining of the sentence
        else:
            after = config.get('after_completion', ',')+" "
        (y, x) = self.win.getyx()
        if not self.last_key_tab:
            # begin is the begining of the nick we want to complete
            begin = self.text.split()[-1].encode('utf-8').lower()
            hit_list = []       # list of matching nicks
            for user in user_list:
                if user.nick.lower().startswith(begin):
                    hit_list.append(user.nick)
            if len(hit_list) == 0:
                return
            self.last_key_tab = True
            self.hit_list = hit_list
            end = len(begin)
        else:
            begin = self.text[:-len(after)].split()[-1].encode('utf-8').lower()
            self.hit_list.append(self.hit_list.pop(0)) # rotate list
            end = len(begin) + len(after)
        x -= end
        self.win.move(y, x)
        # remove begin from the line
        self.win.clrtoeol()
        self.text = self.text[:-end]
        nick = self.hit_list[0] # take the first hit
        self.text += nick.decode('utf-8') +after
        self.pos = len(self.text)
        self.win.addstr(nick+after)
        self.refresh()

    def shell_completion(self, user_list):
        if " " in self.text.strip():
            after = " " # don't put the "," if it's not the begining of the sentence
        else:
            after = config.get('after_completion', ',')+" "
        (y, x) = self.win.getyx()
        begin = self.text.split()[-1].encode('utf-8').lower()
        hit_list = []       # list of matching nicks
        for user in user_list:
            if user.nick.lower().startswith(begin):
                hit_list.append(user.nick)
        if len(hit_list) == 0:
            return
        end = False
        nick = ''
        last_key_tab = self.last_key_tab
        self.last_key_tab = True
        if len(hit_list) == 1:
            nick = hit_list[0] + after
            self.last_key_tab = False
        elif last_key_tab:
            for n in hit_list:
                if begin.lower() == n.lower():
                    nick = n+after # user DO want this completion (tabbed twice on it)
                    self.last_key_tab = False
        if nick == '':
            while not end and len(nick) < len(hit_list[0]):
                nick = hit_list[0][:len(nick)+1]
                for hit in hit_list:
                    if not hit.lower().startswith(nick.lower()):
                        end = True
                        break
            if end:
                nick = nick[:-1]
        x -= len(begin)
        self.win.move(y, x)
        # remove begin from the line
        self.win.clrtoeol()
        self.text = self.text[:-len(begin)]
        self.text += nick.decode('utf-8')
        self.pos = len(self.text)
        self.win.addstr(nick)
        self.refresh()

    def do_command(self, key):
        self.reset_completion()
        (y, x) = self.win.getyx()
        if x == self.width-1:
            self.win.delch(0, 0)
            self.win.move(y, x-1)
            x -= 1
        try:
            self.text = self.text[:self.pos]+key.decode('utf-8')+self.text[self.pos:]
            self.win.insstr(key)
        except:
            return
        self.win.move(y, x+1)
        self.pos += 1
        self.refresh()

    def get_text(self):
        txt = self.text
        self.text = u''
        self.pos = 0
        self.history.append(txt)
        self.histo_pos = len(self.history)-1
        return txt.encode('utf-8')

    def refresh(self):
        if not self.visible:
            return
        self.win.refresh()

    def clear_text(self):
        self.win.erase()

class Window(object):
    """
    The whole "screen" that can be seen at once in the terminal.
    It contains an userlist, an input zone, a topic zone and a chat zone
    """
    def __init__(self, stdscr):
        """
        name is the name of the Tab, and it's also
        the JID of the chatroom.
        A particular tab is the "Info" tab which has no
        name (None). This info tab should be unique.
        The stdscr should be passed to know the size of the
        terminal
        """
        self.size = (self.height, self.width) = stdscr.getmaxyx()
        if self.height < 10 or self.width < 60:
            visible = False
        else:
            visible = True
        if visible:
            stdscr.attron(curses.color_pair(2))
            stdscr.vline(1, 9*(self.width/10), curses.ACS_VLINE, self.height-2)
            stdscr.attroff(curses.color_pair(2))
        self.user_win = UserList(self.height-3, (self.width/10)-1, 1, 9*(self.width/10)+1, stdscr, visible)
        self.topic_win = Topic(1, self.width, 0, 0, stdscr, visible)
        self.info_win = RoomInfo(1, self.width, self.height-2, 0, stdscr, visible)
        self.text_win = TextWin(self.height-3, (self.width/10)*9, 1, 0, stdscr, visible)
        self.input = Input(1, self.width, self.height-1, 0, stdscr, visible)

    def resize(self, stdscr):
        """
        Resize the whole tabe. i.e. all its sub-windows
        """
        self.size = (self.height, self.width) = stdscr.getmaxyx()
        if self.height < 10 or self.width < 60:
            visible = False
        else:
            visible = True
        if visible:
            stdscr.attron(curses.color_pair(2))
            stdscr.vline(1, 9*(self.width/10), curses.ACS_VLINE, self.height-2)
            stdscr.attroff(curses.color_pair(2))
        text_width = (self.width/10)*9;
        self.topic_win.resize(1, self.width, 0, 0, stdscr, visible)
        self.info_win.resize(1, self.width, self.height-2, 0, stdscr, visible)
        self.text_win.resize(self.height-3, text_width, 1, 0, stdscr, visible)
        self.input.resize(1, self.width, self.height-1, 0, stdscr, visible)
        self.user_win.resize(self.height-3, self.width-text_width-1, 1, text_width+1, stdscr, visible)

    def refresh(self, rooms):
        """
        'room' is the current one
        """
        room = rooms[0]         # get current room
        # self.text_win.redraw(room)
        self.text_win.refresh(room)
        self.user_win.refresh(room.users)
        self.topic_win.refresh(room.topic)
        self.info_win.refresh(rooms, room)
        self.input.refresh()

    def do_command(self, key):
        self.input.do_command(key)
        self.input.refresh()

    # def new_room(self, room):
    #     self.text_win.new_win(room.name)
