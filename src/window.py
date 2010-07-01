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

from gettext import (bindtextdomain, textdomain, bind_textdomain_codeset,
                     gettext as _)
from os.path import isfile

import locale
locale.setlocale(locale.LC_ALL, '')

import curses
from config import config

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

    def refresh(self):
        self.win.noutrefresh()

class UserList(Win):
    def __init__(self, height, width, y, x, parent_win, visible):
        Win.__init__(self, height, width, y, x, parent_win)
        self.visible = visible
        self.color_role = {'moderator': 2,
                           'participant':3,
                           'visitor':4
                           }
        self.color_show = {'xa':12,
                           'None':8,
                           'dnd':13,
                           'away':14,
                           'chat':15
                           }

    def refresh(self, users):
        def compare_user(a, b):
            try:
                arole = self.color_role[a.role]
            except KeyError:
                arole = 1
            try:
                brole = self.color_role[b.role]
            except KeyError:
                brole = 1
            if arole == brole:
                if a.nick.lower() < b.nick.lower():
                    return -1
                return 1
            return arole - brole
        if not self.visible:
            return
        self.win.erase()
        y = 0
        for user in sorted(users, compare_user):
            try:
                role_col = self.color_role[user.role]
            except KeyError:
                role_col = 1
            try:
                show_col = self.color_show[user.show]
            except KeyError:
                show_col = 8
            self.win.attron(curses.color_pair(show_col))
            self.win.addnstr(y, 0, " ", 1)
            self.win.attroff(curses.color_pair(show_col))
            self.win.attron(curses.color_pair(role_col))
            self.win.addnstr(y, 1, user.nick, self.width-1)
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

    def refresh(self, topic, jid=None):
        if not self.visible:
            return
        self.win.erase()
        if not jid:
            try:
                self.win.addnstr(0, 0, topic + " "*(self.width-len(topic)), self.width
                                 , curses.color_pair(1))
            except:
                pass
        elif jid:
            room = jid.split('/')[0]
            nick = '/'.join(jid.split('/')[1:])
            topic = _('%(nick)s from room %(room)s' % {'nick': nick, 'room':room})
            self.win.addnstr(0, 0, topic.encode('utf-8') + " "*(self.width-len(topic)), self.width-1
                             , curses.color_pair(15))

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
        self.win.addnstr(0, 0, "[", self.width
                         ,curses.color_pair(1))
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
            self.win.addstr(y, x-1, '] '+ current.name.encode('utf-8'), curses.color_pair(1))
        except:
            pass
        while True:
            try:
                self.win.addstr(' ', curses.color_pair(1))
            except:
                break
        self.win.refresh()

class TextWin(Win):
    """
    Just keep ONE single window for the text area and rewrite EVERYTHING
    on each change. (thanks weechat :o)
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
            if message.nickname and len(message.nickname) >= 30:
                nick = message.nickname[:30]+u'…'
            else:
                nick = message.nickname
            if nick:
                offset += len(nick) + 2 # + nick + spaces length
            first = True
            this_line_was_broken_by_space = False
            while txt != '':
                if txt[:self.width-offset].find('\n') != -1:
                    limit = txt[:self.width-offset].find('\n')
                else:
                    # break between words if possible
                    if len(txt) >= self.width-offset:
                        limit = txt[:self.width-offset].rfind(' ')
                        this_line_was_broken_by_space = True
                        if limit <= 0:
                            limit = self.width-offset-1
                            this_line_was_broken_by_space = False
                    else:
                        limit = self.width-offset-1
                        this_line_was_broken_by_space = False
                color = message.user.color if message.user else None
                if not first:
                    nick = None
                l = Line(nick, color,
                         message.time,
                         txt[:limit], message.color,
                         offset)
                lines.append(l)
                if this_line_was_broken_by_space:
                    txt = txt[limit+1:] # jump the space at the start of the line
                else:
                    txt = txt[limit:]
                if txt.startswith('\n'):
                    txt = txt[1:]
                first = False
        return lines[-len(messages):]# return only the needed number of lines

    def refresh(self, room):
        """
        Build the Line objects from the messages, and then write
        them in the text area
        """
        if not self.visible:
            return
        self.win.erase()
        if room.pos != 0:
            messages = room.messages[-self.height - room.pos : -room.pos]
        else:
            messages = room.messages[-self.height:]
        lines = self.build_lines_from_messages(messages)
        y = 0
        for line in lines:
            self.win.move(y, 0)
            if line.time is not None:
                self.write_time(line.time)
            if line.nickname is not None:
                self.write_nickname(line.nickname.encode('utf-8'), line.nickname_color)
            self.write_text(y, line.text_offset, line.text, line.text_color)
            y += 1
        self.win.refresh()

    def write_text(self, y, x, txt, color):
        """
        return the number of line written, -1
        """
        txt = txt.encode('utf-8')
        if color:
            self.win.attron(curses.color_pair(color))
        self.win.addstr(y, x, txt)
        if color:
            self.win.attroff(curses.color_pair(color))

    def write_nickname(self, nickname, color):
        """
        Write the nickname, using the user's color
        and return the number of written characters
        """
        if color:
            self.win.attron(curses.color_pair(color))
        self.win.addstr(nickname)
        if color:
            self.win.attroff(curses.color_pair(color))
        self.win.addnstr("> ", 2)

    def write_time(self, time):
        """
        Write the date on the yth line of the window
        """
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

class Input(Win):
    """
    """
    def __init__(self, height, width, y, x, stdscr, visible):
        Win.__init__(self, height, width, y, x, stdscr)
        curses.curs_set(1)
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
        self.win.erase()
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
        self.win.erase()
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
        try:
            self.win.move(y, x)
        except:
            pass
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
            stdscr.attron(curses.color_pair(3))
            stdscr.vline(1, 9*(self.width/10), curses.ACS_VLINE, self.height-2)
            stdscr.attroff(curses.color_pair(3))
        self.user_win = UserList(self.height-3, (self.width/10)-1, 1, 9*(self.width/10)+1, stdscr, visible)
        self.topic_win = Topic(1, self.width, 0, 0, stdscr, visible)
        self.info_win = RoomInfo(1, self.width, self.height-2, 0, stdscr, visible)
        self.text_win = TextWin(self.height-3, (self.width/10)*9, 1, 0, stdscr, visible)
        self.input = Input(1, self.width, self.height-1, 0, stdscr, visible)

    def resize(self, stdscr):
        """
        Resize the whole window. i.e. all its sub-windows
        """
        self.size = (self.height, self.width) = stdscr.getmaxyx()
        if self.height < 10 or self.width < 50:
            visible = False
        else:
            visible = True
        if visible:
            stdscr.attron(curses.color_pair(3))
            stdscr.vline(1, 9*(self.width/10), curses.ACS_VLINE, self.height-2)
            stdscr.attroff(curses.color_pair(3))
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
        self.text_win.refresh(room)
        self.user_win.refresh(room.users)
        self.topic_win.refresh(room.topic, room.jid)
        self.info_win.refresh(rooms, room)
        self.input.refresh()

    def do_command(self, key):
        self.input.do_command(key)
        self.input.refresh()
