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
Define all the windows.
A window is a little part of the screen, for example the input window,
the text window, the roster window, etc.
A Tab (see tab.py) is composed of multiple Windows
"""

from gettext import (bindtextdomain, textdomain, bind_textdomain_codeset,
                     gettext as _)
from os.path import isfile

import logging
log = logging.getLogger(__name__)

import locale
locale.setlocale(locale.LC_ALL, '')

import shlex
import curses
from config import config

from threading import Lock

from contact import Contact, Resource
from roster import RosterGroup, roster

from message import Line
from tabs import MIN_WIDTH, MIN_HEIGHT

from sleekxmpp.xmlstream.stanzabase import JID

import theme

g_lock = Lock()

LINES_NB_LIMIT = 16384

class Win(object):
    def __init__(self):
        pass

    def _resize(self, height, width, y, x, parent_win):
        self.height, self.width, self.x, self.y = height, width, x, y
        self._win = curses.newwin(height, width, y, x)

    def _refresh(self):
        self._win.noutrefresh()

    def addnstr(self, *args):
        """
        Safe call to addnstr
        """
        try:
            self._win.addnstr(*args)
        except:
            pass

    def addstr(self, *args):
        """
        Safe call to addstr
        """
        try:
            self._win.addstr(*args)
        except:
            pass

    def finish_line(self, color):
        """
        Write colored spaces until the end of line
        """
        (y, x) = self._win.getyx()
        size = self.width-x
        self.addnstr(' '*size, size, curses.color_pair(color))

class UserList(Win):
    def __init__(self):
        Win.__init__(self)
        self.color_role = {'moderator': theme.COLOR_USER_MODERATOR,
                           'participant':theme.COLOR_USER_PARTICIPANT,
                           'visitor':theme.COLOR_USER_VISITOR,
                           'none':theme.COLOR_USER_NONE,
                           '':theme.COLOR_USER_NONE
                           }
        self.color_show = {'xa':theme.COLOR_STATUS_XA,
                           'none':theme.COLOR_STATUS_NONE,
                           '':theme.COLOR_STATUS_NONE,
                           'dnd':theme.COLOR_STATUS_DND,
                           'away':theme.COLOR_STATUS_AWAY,
                           'chat':theme.COLOR_STATUS_CHAT
                           }

    def refresh(self, users):
        with g_lock:
            self._win.erase()
            y = 0
            for user in sorted(users):
                if not user.role in self.color_role:
                    role_col = theme.COLOR_USER_NONE
                else:
                    role_col = self.color_role[user.role]
                if not user.show in self.color_show:
                    show_col = theme.COLOR_STATUS_NONE
                else:
                    show_col = self.color_show[user.show]
                self.addstr(y, 0, theme.CHAR_STATUS, curses.color_pair(show_col))
                self.addnstr(y, 1, user.nick, self.width-1, curses.color_pair(role_col))
                y += 1
                if y == self.height:
                    break
            self._refresh()

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)
        self._win.attron(curses.color_pair(theme.COLOR_VERTICAL_SEPARATOR))
        self._win.vline(0, 0, curses.ACS_VLINE, self.height)
        self._win.attroff(curses.color_pair(theme.COLOR_VERTICAL_SEPARATOR))

class Topic(Win):
    def __init__(self):
        Win.__init__(self)

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self, topic):
        with g_lock:
            self._win.erase()
            self.addstr(0, 0, topic[:self.width-1], curses.color_pair(theme.COLOR_TOPIC_BAR))
            (y, x) = self._win.getyx()
            remaining_size = self.width - x
            if remaining_size:
                self.addnstr(' '*remaining_size, remaining_size,
                             curses.color_pair(theme.COLOR_INFORMATION_BAR))
            self._refresh()

class GlobalInfoBar(Win):
    def __init__(self):
        Win.__init__(self)

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self, tabs, current):
        def compare_room(a):
            # return a.nb - b.nb
            return a.nb
        comp = lambda x: x.nb
        with g_lock:
            self._win.erase()
            self.addstr(0, 0, "[", curses.color_pair(theme.COLOR_INFORMATION_BAR))
            sorted_tabs = sorted(tabs, key=comp)
            for tab in sorted_tabs:
                color = tab.get_color_state()
                try:
                    self.addstr("%s" % str(tab.nb), curses.color_pair(color))
                    self.addstr("|", curses.color_pair(theme.COLOR_INFORMATION_BAR))
                except:             # end of line
                    break
            (y, x) = self._win.getyx()
            self.addstr(y, x-1, '] ', curses.color_pair(theme.COLOR_INFORMATION_BAR))
            (y, x) = self._win.getyx()
            remaining_size = self.width - x
            self.addnstr(' '*remaining_size, remaining_size,
                         curses.color_pair(theme.COLOR_INFORMATION_BAR))
            self._refresh()

class InfoWin(Win):
    """
    Base class for all the *InfoWin, used in various tabs. For example
    MucInfoWin, etc. Provides some useful methods.
    """
    def __init__(self):
        Win.__init__(self)

    def print_scroll_position(self, window):
        """
        Print, link in Weechat, a -PLUS(n)- where n
        is the number of available lines to scroll
        down
        """
        if window.pos > 0:
            plus = ' -PLUS(%s)-' % window.pos
            self.addstr(plus, curses.color_pair(theme.COLOR_SCROLLABLE_NUMBER) | curses.A_BOLD)

class PrivateInfoWin(InfoWin):
    """
    The live above the information window, displaying informations
    about the MUC user we are talking to
    """
    def __init__(self):
        InfoWin.__init__(self)

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self, room, window):

        with g_lock:
            self._win.erase()
            self.write_room_name(room)
            self.print_scroll_position(window)
            self.finish_line(theme.COLOR_INFORMATION_BAR)
            self._refresh()

    def write_room_name(self, room):
        jid = JID(room.name)
        room_name, nick = jid.bare, jid.resource
        self.addstr(nick, curses.color_pair(13))
        txt = ' from room %s' % room_name
        self.addstr(txt, curses.color_pair(theme.COLOR_INFORMATION_BAR))

class ConversationInfoWin(InfoWin):
    """
    The line above the information window, displaying informations
    about the user we are talking to
    """
    color_show = {'xa':theme.COLOR_STATUS_XA,
                  'none':theme.COLOR_STATUS_ONLINE,
                  '':theme.COLOR_STATUS_ONLINE,
                  'available':theme.COLOR_STATUS_ONLINE,
                  'dnd':theme.COLOR_STATUS_DND,
                  'away':theme.COLOR_STATUS_AWAY,
                  'chat':theme.COLOR_STATUS_CHAT,
                  'unavailable':theme.COLOR_STATUS_UNAVAILABLE
                  }

    def __init__(self):
        InfoWin.__init__(self)

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self, jid, contact, text_buffer, window):
        # contact can be None, if we receive a message
        # from someone not in our roster. In this case, we display
        # only the maximum information from the message we can get.
        jid = JID(jid)
        if contact:
            if jid.resource:
                resource = contact.get_resource_by_fulljid(jid.full)
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        # if contact is None, then resource is None too: user is not in the roster
        # so we don't know almost anything about it
        # If contact is a Contact, then
        # resource can now be a Resource: user is in the roster and online
        # or resource is None: user is in the roster but offline
        with g_lock:
            self._win.erase()
            self.write_contact_jid(jid)
            self.write_contact_informations(contact)
            self.write_resource_information(resource)
            self.print_scroll_position(window)
            self.finish_line(theme.COLOR_INFORMATION_BAR)
            self._refresh()

    def write_resource_information(self, resource):
        """
        Write the informations about the resource
        """
        if not resource:
            presence = "unavailable"
        else:
            presence = resource.get_presence()
        color = RosterWin.color_show[presence]
        self.addstr('[', curses.color_pair(theme.COLOR_INFORMATION_BAR))
        self.addstr(" ", curses.color_pair(color))
        self.addstr(']', curses.color_pair(theme.COLOR_INFORMATION_BAR))

    def write_contact_informations(self, contact):
        """
        Write the informations about the contact
        """
        if not contact:
            self.addstr("(contact not in roster)", curses.color_pair(theme.COLOR_INFORMATION_BAR))
            return
        display_name = contact.get_name() or contact.get_bare_jid()
        self.addstr('%s '%(display_name), curses.color_pair(theme.COLOR_INFORMATION_BAR))

    def write_contact_jid(self, jid):
        """
        Just write the jid that we are talking to
        """
        self.addstr('[', curses.color_pair(theme.COLOR_INFORMATION_BAR))
        self.addstr(jid.full, curses.color_pair(10))
        self.addstr('] ', curses.color_pair(theme.COLOR_INFORMATION_BAR))

class ConversationStatusMessageWin(InfoWin):
    """
    The upper bar displaying the status message of the contact
    """
    def __init__(self):
        InfoWin.__init__(self)

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self, jid, contact):
        jid = JID(jid)
        if contact:
            if jid.resource:
                resource = contact.get_resource_by_fulljid(jid.full)
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        with g_lock:
            self._win.erase()
            if resource:
                self.write_status_message(resource)
            self.finish_line(theme.COLOR_INFORMATION_BAR)
            self._refresh()

    def write_status_message(self, resource):
        self.addstr(resource.get_status(), curses.color_pair(theme.COLOR_INFORMATION_BAR))

class MucInfoWin(InfoWin):
    """
    The line just above the information window, displaying informations
    about the MUC we are viewing
    """
    def __init__(self):
        InfoWin.__init__(self)

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self, room, window=None):
        with g_lock:
            self._win.erase()
            self.write_room_name(room)
            self.write_own_nick(room)
            self.write_disconnected(room)
            self.write_role(room)
            if window:
                self.print_scroll_position(window)
            self.finish_line(theme.COLOR_INFORMATION_BAR)
            self._refresh()

    def write_room_name(self, room):
        """
        """
        self.addstr('[', curses.color_pair(theme.COLOR_INFORMATION_BAR))
        self.addnstr(room.name, len(room.name), curses.color_pair(13))
        self.addstr('] ', curses.color_pair(theme.COLOR_INFORMATION_BAR))

    def write_disconnected(self, room):
        """
        Shows a message if the room is not joined
        """
        if not room.joined:
            self.addstr(' -!- Not connected ', curses.color_pair(theme.COLOR_INFORMATION_BAR))

    def write_own_nick(self, room):
        """
        Write our own nick in the info bar
        """
        nick = room.own_nick
        if not nick:
            return
        if len(nick) > 13:
            nick = nick[:13]+'…'
        self.addstr(nick, curses.color_pair(theme.COLOR_INFORMATION_BAR))

    def write_role(self, room):
        """
        Write our own role and affiliation
        """
        own_user = None
        for user in room.users:
            if user.nick == room.own_nick:
                own_user = user
                break
        if not own_user:
            return
        txt = ' ('
        if own_user.affiliation != 'none':
            txt += own_user.affiliation+', '
        txt += own_user.role+')'
        self.addstr(txt, curses.color_pair(theme.COLOR_INFORMATION_BAR))

class TextWin(Win):
    def __init__(self):
        Win.__init__(self)
        self.pos = 0
        self.built_lines = []   # Each new message is built and kept here.
        # on resize, we rebuild all the messages

    def scroll_up(self, dist=14):
        self.pos += dist
        if self.pos + self.height > len(self.built_lines):
            self.pos = len(self.built_lines) - self.height
            if self.pos < 0:
                self.pos = 0

    def scroll_down(self, dist=14):
        self.pos -= dist
        if self.pos <= 0:
            self.pos = 0

    def remove_line_separator(self):
        """
        Remove the line separator
        """
        if None in self.built_lines:
            self.built_lines.remove(None)

    def add_line_separator(self):
        """
        add a line separator at the end of messages list
        """
        if None not in self.built_lines:
            self.built_lines.append(None)

    def build_new_message(self, message):
        """
        Take one message, build it and add it to the list
        Return the number of lines that are built for the given
        message.
        """
        if message == None:  # line separator
            self.built_lines.append(None)
            return 0
        txt = message.txt
        if not txt:
            return 0
            # length of the time
        offset = 9+len(theme.CHAR_TIME_LEFT[:1])+len(theme.CHAR_TIME_RIGHT[:1])
        if message.nickname and len(message.nickname) >= 30:
            nick = message.nickname[:30]+'…'
        else:
            nick = message.nickname
        if nick:
            offset += len(nick) + 2 # + nick + spaces length
        first = True
        this_line_was_broken_by_space = False
        nb = 0
        while txt != '':
            if txt[:self.width-offset].find('\n') != -1:
                limit = txt[:self.width-offset].find('\n')
            else:
                # break between words if possible
                if len(txt) >= self.width-offset:
                    limit = txt[:self.width-offset].rfind(' ')
                    this_line_was_broken_by_space = True
                    if limit <= 0:
                        limit = self.width-offset
                        this_line_was_broken_by_space = False
                else:
                    limit = self.width-offset-1
                    this_line_was_broken_by_space = False
            color = message.user.color if message.user else None
            if not first:
                nick = None
                time = None
            else:               # strftime is VERY slow, improve performance
                                # by calling it only one time here, and
                                # not at each refresh
                time = {'hour': '%s'%(message.time.strftime("%H"),),
                        'minute': '%s'%(message.time.strftime("%M"),),
                        'second': '%s'%(message.time.strftime("%S"),),
                        }
            l = Line(nick, color,
                     time,
                     txt[:limit], message.color,
                     offset,
                     message.colorized)
            self.built_lines.append(l)
            nb += 1
            if this_line_was_broken_by_space:
                txt = txt[limit+1:] # jump the space at the start of the line
            else:
                txt = txt[limit:]
            if txt.startswith('\n'):
                txt = txt[1:]
            first = False
        while len(self.built_lines) > LINES_NB_LIMIT:
            self.built_lines.pop(0)
        return nb

    def refresh(self, room):
        """
        Build the Line objects from the messages, and then write
        them in the text area
        """
        if self.height <= 0:
            return
        if self.pos != 0:
            lines = self.built_lines[-self.height-self.pos:-self.pos]
        else:
            lines = self.built_lines[-self.height:]
        self._win.move(0, 0)
        with g_lock:
            self._win.erase()
            for y, line in enumerate(lines):
                if line is None:
                    self.write_line_separator()
                    continue
                if line.time:
                    self.write_time(line.time)
                if line.nickname:
                    self.write_nickname(line.nickname, line.nickname_color)
                self.write_text(y, line.text_offset, line.text, line.text_color, line.colorized)
                if y != self.height - 1:
                    self.addstr('\n')
            self._refresh()

    def write_line_separator(self):
        """
        """
        self._win.attron(curses.color_pair(theme.COLOR_NEW_TEXT_SEPARATOR))
        self.addnstr('- '*(self.width//2), self.width)
        self._win.attroff(curses.color_pair(theme.COLOR_NEW_TEXT_SEPARATOR))
        self.addstr('\n')

    def write_text(self, y, x, txt, color, colorized):
        """
        write the text of a line.
        """
        txt = txt
        if not colorized:
            if color:
                self._win.attron(curses.color_pair(color))
            self.addstr(y, x, txt)
            if color:
                self._win.attroff(curses.color_pair(color))

        else:                   # Special messages like join or quit
            special_words = {
                theme.CHAR_JOIN: theme.COLOR_JOIN_CHAR,
                theme.CHAR_QUIT: theme.COLOR_QUIT_CHAR,
                theme.CHAR_KICK: theme.COLOR_KICK_CHAR,
                }
            try:
                splitted = shlex.split(txt)
            except ValueError:
                # FIXME colors are disabled on too long words
                txt = txt.replace('"[', '').replace(']"', '')\
                    .replace('"{', '').replace('}"', '')\
                    .replace('"(', '').replace(')"', '')
                splitted = txt.split()
            for word in splitted:
                if word in list(special_words.keys()):
                    self.addstr(word, curses.color_pair(special_words[word]))
                elif word.startswith('(') and word.endswith(')'):
                    self.addstr('(', curses.color_pair(color))
                    self.addstr(word[1:-1], curses.color_pair(theme.COLOR_CURLYBRACKETED_WORD))
                    self.addstr(')', curses.color_pair(color))
                elif word.startswith('{') and word.endswith('}'):
                    self.addstr(word[1:-1], curses.color_pair(theme.COLOR_ACCOLADE_WORD))
                elif word.startswith('[') and word.endswith(']'):
                    self.addstr(word[1:-1], curses.color_pair(theme.COLOR_BRACKETED_WORD))
                else:
                    self.addstr(word, curses.color_pair(color))
                self._win.addch(' ')

    def write_nickname(self, nickname, color):
        """
        Write the nickname, using the user's color
        and return the number of written characters
        """
        if color:
            self._win.attron(curses.color_pair(color))
        self.addstr(nickname)
        if color:
            self._win.attroff(curses.color_pair(color))
        self.addstr("> ")

    def write_time(self, time):
        """
        Write the date on the yth line of the window
        """
        self.addstr(theme.CHAR_TIME_LEFT, curses.color_pair(theme.COLOR_TIME_LIMITER))
        self.addstr(time['hour'], curses.color_pair(theme.COLOR_TIME_NUMBERS))
        self.addstr(':', curses.color_pair(theme.COLOR_TIME_SEPARATOR))
        self.addstr(time['minute'], curses.color_pair(theme.COLOR_TIME_NUMBERS))
        self.addstr(':', curses.color_pair(theme.COLOR_TIME_SEPARATOR))
        self.addstr(time['second'], curses.color_pair(theme.COLOR_TIME_NUMBERS))
        self.addstr(theme.CHAR_TIME_RIGHT, curses.color_pair(theme.COLOR_TIME_LIMITER))
        self.addstr(' ')

    def resize(self, height, width, y, x, stdscr, room=None):
        self._resize(height, width, y, x, stdscr)
        if room:
            self.rebuild_everything(room)

    def rebuild_everything(self, room):
        self.built_lines = []
        for message in room.messages:
            self.build_new_message(message)

class HelpText(Win):
    """
    A Window just displaying a read-only message.
    Usually used to replace an Input when the tab is in
    command mode.
    """
    def __init__(self, text=''):
        Win.__init__(self)
        self.txt = text

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self):
        with g_lock:
            self._win.erase()
            self.addstr(0, 0, self.txt[:self.width-1], curses.color_pair(theme.COLOR_INFORMATION_BAR))
            self.finish_line(theme.COLOR_INFORMATION_BAR)
            self._refresh()

    def do_command(self, key):
        return False

class Input(Win):
    """
    The simplest Input possible, provides just a way to edit a single line
    of text. It also has a clipboard, common to all Inputs.
    Doesn't have any history.
    It doesn't do anything when enter is pressed either.
    This should be herited for all kinds of Inputs, for example MessageInput
    or the little inputs in dataforms, etc, adding specific features (completion etc)
    It features two kinds of completion, but they have to be called from outside (the Tab),
    passing the list of items that can be used to complete. The completion can be used
    in a very flexible way.
    """
    clipboard = '' # A common clipboard for all the inputs, this makes
    # it easy cut and paste text between various input
    def __init__(self):
        self.key_func = {
            "KEY_LEFT": self.key_left,
            "M-D": self.key_left,
            "KEY_RIGHT": self.key_right,
            "M-C": self.key_right,
            "KEY_END": self.key_end,
            "KEY_HOME": self.key_home,
            "KEY_DC": self.key_dc,
            '^D': self.key_dc,
            'M-b': self.jump_word_left,
            '^W': self.delete_word,
            '^K': self.delete_end_of_line,
            '^U': self.delete_begining_of_line,
            '^Y': self.paste_clipboard,
            '^A': self.key_home,
            '^E': self.key_end,
            'M-f': self.jump_word_right,
            "KEY_BACKSPACE": self.key_backspace,
            '^?': self.key_backspace,
            }

        Win.__init__(self)
        self.text = ''
        self.pos = 0            # cursor position
        self.line_pos = 0 # position (in self.text) of

    def is_empty(self):
        return len(self.text) == 0

    def resize(self, height, width, y, x, stdscr):

        self._resize(height, width, y, x, stdscr)
        self._win.erase()
        self.addnstr(0, 0, self.text, self.width-1)

    def jump_word_left(self):
        """
        Move the cursor one word to the left
        """
        if not len(self.text) or self.pos == 0:
            return
        previous_space = self.text[:self.pos+self.line_pos].rfind(' ')
        if previous_space == -1:
            previous_space = 0
        diff = self.pos+self.line_pos-previous_space
        for i in range(diff):
            self.key_left()
        return True

    def jump_word_right(self):
        """
        Move the cursor one word to the right
        """
        if len(self.text) == self.pos+self.line_pos or not len(self.text):
            return
        next_space = self.text.find(' ', self.pos+self.line_pos+1)
        if next_space == -1:
            next_space = len(self.text)
        diff = next_space - (self.pos+self.line_pos)
        for i in range(diff):
            self.key_right()
        return True

    def delete_word(self):
        """
        Delete the word just before the cursor
        """
        if not len(self.text) or self.pos == 0:
            return
        previous_space = self.text[:self.pos+self.line_pos].rfind(' ')
        if previous_space == -1:
            previous_space = 0
        diff = self.pos+self.line_pos-previous_space
        for i in range(diff):
            self.key_backspace(False)
        self.rewrite_text()
        return True

    def delete_end_of_line(self):
        """
        Cut the text from cursor to the end of line
        """
        if len(self.text) == self.pos+self.line_pos:
            return              # nothing to cut
        Input.clipboard = self.text[self.pos+self.line_pos:]
        self.text = self.text[:self.pos+self.line_pos]
        self.key_end()
        return True

    def delete_begining_of_line(self):
        """
        Cut the text from cursor to the begining of line
        """
        if self.pos+self.line_pos == 0:
            return
        Input.clipboard = self.text[:self.pos+self.line_pos]
        self.text = self.text[self.pos+self.line_pos:]
        self.key_home()
        return True

    def paste_clipboard(self):
        """
        Insert what is in the clipboard at the cursor position
        """
        if not Input.clipboard or len(Input.clipboard) == 0:
            return
        for letter in Input.clipboard:
            self.do_command(letter)
        return True

    def key_dc(self):
        """
        delete char just after the cursor
        """
        self.reset_completion()
        if self.pos + self.line_pos == len(self.text):
            return              # end of line, nothing to delete
        self.text = self.text[:self.pos+self.line_pos]+self.text[self.pos+self.line_pos+1:]
        self.rewrite_text()
        return True

    def key_home(self):
        """
        Go to the begining of line
        """
        self.reset_completion()
        self.pos = 0
        self.line_pos = 0
        self.rewrite_text()
        return True

    def key_end(self, reset=False):
        """
        Go to the end of line
        """
        if reset:
            self.reset_completion()
        if len(self.text) >= self.width-1:
            self.pos = self.width-1
            self.line_pos = len(self.text)-self.pos
        else:
            self.pos = len(self.text)
            self.line_pos = 0
        self.rewrite_text()
        return True

    def key_left(self):
        """
        Move the cursor one char to the left
        """
        self.reset_completion()
        (y, x) = self._win.getyx()
        if self.pos == self.width-1 and self.line_pos > 0:
            self.line_pos -= 1
        elif self.pos >= 1:
            self.pos -= 1
        self.rewrite_text()
        return True

    def key_right(self):
        """
        Move the cursor one char to the right
        """
        self.reset_completion()
        (y, x) = self._win.getyx()
        if self.pos == self.width-1:
            if self.line_pos + self.width-1 < len(self.text):
                self.line_pos += 1
        elif self.pos < len(self.text):
            self.pos += 1
        self.rewrite_text()
        return True

    def key_backspace(self, reset=True):
        """
        Delete the char just before the cursor
        """
        self.reset_completion()
        (y, x) = self._win.getyx()
        if self.pos == 0:
            return
        self.text = self.text[:self.pos+self.line_pos-1]+self.text[self.pos+self.line_pos:]
        self.key_left()
        if reset:
            self.rewrite_text()
        return True

    def auto_completion(self, word_list, add_after):
        """
        Complete the input, from a list of words
        if add_after is None, we use the value defined in completion
        plus a space, after the completion. If it's a string, we use it after the
        completion (with no additional space)
        """
        if self.pos+self.line_pos != len(self.text): # or len(self.text) == 0
            return # we don't complete if cursor is not at the end of line
        completion_type = config.get('completion', 'normal')
        if completion_type == 'shell' and self.text != '':
            self.shell_completion(word_list, add_after)
        else:
            self.normal_completion(word_list, add_after)
        return True

    def reset_completion(self):
        """
        Reset the completion list (called on ALL keys except tab)
        """
        self.hit_list = []
        self.last_completion = None

    def normal_completion(self, word_list, after):
        """
        Normal completion
        """
        (y, x) = self._win.getyx()
        if not self.last_completion:
            # begin is the begining of the word we want to complete
            if self.text.strip() and not self.text.endswith(' '):
                begin = self.text.split()[-1].lower()
            else:
                begin = ''
            hit_list = []       # list of matching nicks
            for word in word_list:
                if word.lower().startswith(begin):
                    hit_list.append(word)
            if len(hit_list) == 0:
                return
            self.hit_list = hit_list
            end = len(begin)
        else:
            if after:
                begin = self.text[-len(after)-len(self.last_completion):-len(after)]
            else:
                begin = self.last_completion
            self.hit_list.append(self.hit_list.pop(0)) # rotate list
            end = len(begin) + len(after)
        if end:
            self.text = self.text[:-end]
        nick = self.hit_list[0] # take the first hit
        self.last_completion = nick
        self.text += nick +after
        self.key_end(False)

    def shell_completion(self, word_list, after):
        """
        Shell-like completion
        """
        if " " in self.text.strip() or add_after is not None:
            after = " " # don't put the "," if it's not the begining of the sentence
        else:
            after = config.get('after_completion', ',')+" "
        (y, x) = self._win.getyx()
        if self.text != '':
            begin = self.text.split()[-1].lower()
        else:
            begin = ''
        hit_list = []       # list of matching nicks
        for user in word_list:
            if user.lower().startswith(begin):
                hit_list.append(user)
        if len(hit_list) == 0:
            return
        end = False
        nick = ''
        last_completion = self.last_completion
        self.last_completion = True
        if len(hit_list) == 1:
            nick = hit_list[0] + after
            self.last_completion = False
        elif last_completion:
            for n in hit_list:
                if begin.lower() == n.lower():
                    nick = n+after # user DO want this completion (tabbed twice on it)
                    self.last_completion = False
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
        self.text = self.text[:-len(begin)]
        self.text += nick
        self.key_end(False)

    def do_command(self, key, reset=True):
        if key in self.key_func:
            return self.key_func[key]()
        if not key or len(key) > 1:
            return False   # ignore non-handled keyboard shortcuts
        self.reset_completion()
        self.text = self.text[:self.pos+self.line_pos]+key+self.text[self.pos+self.line_pos:]
        (y, x) = self._win.getyx()
        if x == self.width-1:
            self.line_pos += len(key)
        else:
            self.pos += len(key)
        if reset:
            self.rewrite_text()
        return True

    def get_text(self):
        """
        Clear the input and return the text entered so far
        """
        return self.text

    def rewrite_text(self):
        """
        Refresh the line onscreen, from the pos and pos_line
        """
        with g_lock:
            self._win.erase()
            self.addstr(self.text[self.line_pos:self.line_pos+self.width-1])
            self.addstr(0, self.pos, '') # WTF, this works but .move() doesn't…
            self._refresh()

    def refresh(self):
        self.rewrite_text()

    def clear_text(self):
        self.text = ''
        self.pos = 0
        self.line_pos = 0
        self.rewrite_text()

class MessageInput(Input):
    """
    The input featuring history and that is being used in
    Conversation, Muc and Private tabs
    """
    history = list()            # The history is common to all MessageInput

    def __init__(self):
        Input.__init__(self)
        self.last_completion = None
        self.histo_pos = 0
        self.key_func["KEY_UP"] = self.key_up
        self.key_func["M-A"] =  self.key_up
        self.key_func["KEY_DOWN"] = self.key_down
        self.key_func["M-B"] = self.key_down

    def key_up(self):
        """
        Get the previous line in the history
        """
        if not len(MessageInput.history):
            return
        self.reset_completion()
        self._win.erase()
        if self.histo_pos >= 0:
            self.histo_pos -= 1
        self.text = MessageInput.history[self.histo_pos+1]
        self.key_end()

    def key_down(self):
        """
        Get the next line in the history
        """
        if not len(MessageInput.history):
            return
        self.reset_completion()
        if self.histo_pos < len(MessageInput.history)-1:
            self.histo_pos += 1
            self.text = self.history[self.histo_pos]
            self.key_end()
        else:
            self.histo_pos = len(MessageInput.history)-1
            self.text = ''
            self.pos = 0
            self.line_pos = 0
            self.rewrite_text()

    def key_enter(self):
        txt = self.get_text()
        if len(txt) != 0:
            self.history.append(txt)
            self.histo_pos = len(self.history)-1
        self.clear_text()
        return txt

class CommandInput(Input):
    """
    An input with an help message in the left, with three given callbacks:
    one when when successfully 'execute' the command and when we abort it.
    The last callback is optional and is called on any input key
    This input is used, for example, in the RosterTab when, to replace the
    HelpMessage when a command is started
    The on_input callback
    """
    def __init__(self, help_message, on_abort, on_success, on_input=None):
        Input.__init__(self)
        self.on_abort = on_abort
        self.on_success = on_success
        self.on_input = on_input
        self.help_message = help_message
        self.key_func['^J'] = self.success
        self.key_func['^M'] = self.success
        self.key_func['\n'] = self.success
        self.key_func['^G'] = self.abort

    def do_command(self, key):
        res = Input.do_command(self, key)
        if self.on_input:
            self.on_input(self.get_text())
        return res

    def success(self):
        """
        call the success callback, passing the text as argument
        """
        self.on_input = None
        res = self.on_success(self.get_text())
        return  res

    def abort(self):
        """
        Call the abort callback, passing the text as argument
        """
        self.on_input = None
        return self.on_abort(self.get_text())

    def rewrite_text(self):
        """
        Rewrite the text just like a normal input, but with the instruction
        on the left
        """
        with g_lock:
            self._win.erase()
            self.addstr(self.help_message, curses.color_pair(theme.COLOR_INFORMATION_BAR))
            cursor_pos = self.pos + len(self.help_message)
            if len(self.help_message):
                self.addstr(' ')
                cursor_pos += 1
            self.addstr(self.text[self.line_pos:self.line_pos+self.width-1])
            self.addstr(0, cursor_pos, '') # WTF, this works but .move() doesn't…
            self._refresh()

class VerticalSeparator(Win):
    """
    Just a one-column window, with just a line in it, that is
    refreshed only on resize, but never on refresh, for efficiency
    """
    def __init__(self):
        Win.__init__(self)

    def rewrite_line(self):
        with g_lock:
            self._win.vline(0, 0, curses.ACS_VLINE, self.height, curses.color_pair(theme.COLOR_VERTICAL_SEPARATOR))
            self._refresh()

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self):
        self.rewrite_line()

class RosterWin(Win):
    color_show = {'xa':theme.COLOR_STATUS_XA,
                  'none':theme.COLOR_STATUS_ONLINE,
                  '':theme.COLOR_STATUS_ONLINE,
                  'available':theme.COLOR_STATUS_ONLINE,
                  'dnd':theme.COLOR_STATUS_DND,
                  'away':theme.COLOR_STATUS_AWAY,
                  'chat':theme.COLOR_STATUS_CHAT,
                  'unavailable':theme.COLOR_STATUS_UNAVAILABLE
                  }

    def __init__(self):
        Win.__init__(self)
        self.pos = 0            # cursor position in the contact list
        self.start_pos = 1      # position of the start of the display
        self.roster_len = 0
        self.selected_row = None

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def move_cursor_down(self):
        if self.pos < self.roster_len-1:
            self.pos += 1
        if self.pos == self.start_pos-1 + self.height-1:
            self.scroll_down()

    def move_cursor_up(self):
        if self.pos > 0:
            self.pos -= 1
        if self.pos == self.start_pos-2:
            self.scroll_up()

    def scroll_down(self):
        self.start_pos += 8

    def scroll_up(self):
        self.start_pos -= 8

    def refresh(self, roster):
        """
        We get the roster object
        """
        with g_lock:
            self.roster_len = len(roster)
            while self.roster_len and self.pos >= self.roster_len:
                self.move_cursor_up()
            self._win.erase()
            self.draw_roster_information(roster)
            y = 1
            for group in roster.get_groups():
                if group.get_nb_connected_contacts() == 0:
                    continue    # Ignore empty groups
                # This loop is really REALLY ugly :^)
                if y-1 == self.pos:
                    self.selected_row = group
                if y >= self.start_pos:
                    self.draw_group(y-self.start_pos+1, group, y-1==self.pos)
                y += 1
                if group.folded:
                    continue
                for contact in group.get_contacts(roster._contact_filter):
                    if config.get('roster_show_offline', 'false') == 'false' and\
                            contact.get_nb_resources() == 0:
                        continue
                    if y-1 == self.pos:
                        self.selected_row = contact
                    if y-self.start_pos+1 == self.height:
                        break
                    if y >= self.start_pos:
                        self.draw_contact_line(y-self.start_pos+1, contact, y-1==self.pos)
                    y += 1
                    if not contact._folded:
                        for resource in contact.get_resources():
                            if y-1 == self.pos:
                                self.selected_row = resource
                            if y-self.start_pos+1 == self.height:
                                break
                            if y >= self.start_pos:
                                self.draw_resource_line(y-self.start_pos+1, resource, y-1==self.pos)
                            y += 1
                if y-self.start_pos+1 == self.height:
                    break
            if self.start_pos > 1:
                self.draw_plus(1)
            if self.start_pos + self.height-2 < self.roster_len:
                self.draw_plus(self.height-1)
            self._refresh()

    def draw_plus(self, y):
        """
        Draw the indicator that shows that
        the list is longer than what is displayed
        """
        self.addstr(y, self.width-5, '++++', curses.color_pair(42))

    def draw_roster_information(self, roster):
        """
        """
        self.addstr('%s contacts' % roster.get_contact_len(), curses.color_pair(12))
        self.finish_line(12)

    def draw_group(self, y, group, colored):
        """
        Draw a groupname on a line
        """
        if colored:
            self._win.attron(curses.color_pair(14))
        if group.folded:
            self.addstr(y, 0, '[+] ')
        else:
            self.addstr(y, 0, '[-] ')
        self.addstr(y, 4, group.name)
        if colored:
            self._win.attroff(curses.color_pair(14))

    def draw_contact_line(self, y, contact, colored):
        """
        Draw on a line all informations about one contact.
        This is basically the highest priority resource's informations
        Use 'color' to draw the jid/display_name to show what is
        the currently selected contact in the list
        """
        resource = contact.get_highest_priority_resource()
        if not resource:
            # There's no online resource
            presence = 'unavailable'
            folder = '   '
            nb = ''
        else:
            presence = resource.get_presence()
            folder = '[+]' if contact._folded else '[-]'
            nb = '(%s)' % (contact.get_nb_resources(),)
        color = RosterWin.color_show[presence]
        if contact.get_name():
            display_name = '%s (%s) %s' % (contact.get_name(),
                                        contact.get_bare_jid(), nb,)
        else:
            display_name = '%s %s' % (contact.get_bare_jid(), nb,)
        self.addstr(y, 1, " ", curses.color_pair(color))
        if resource:
            self.addstr(y, 2, ' [+]' if contact._folded else ' [-]')
        self.addstr(' ')
        if colored:
            self.addstr(display_name, curses.color_pair(14))
        else:
            self.addstr(display_name)

    def draw_resource_line(self, y, resource, colored):
        """
        Draw a specific resource line
        """
        color = RosterWin.color_show[resource.get_presence()]
        self.addstr(y, 4, " ", curses.color_pair(color))
        if colored:
            self.addstr(y, 6, resource.get_jid().full, curses.color_pair(14))
        else:
            self.addstr(y, 6, resource.get_jid().full)

    def get_selected_row(self):
        return self.selected_row

class ContactInfoWin(Win):
    def __init__(self):
        Win.__init__(self)

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def draw_contact_info(self, resource, jid=None):
        """
        draw the contact information
        """
        jid = jid or resource.get_jid().full
        if resource:
            presence = resource.get_presence()
        else:
            presence = 'unavailable'
        self.addstr(0, 0, jid, curses.color_pair(theme.COLOR_INFORMATION_BAR))
        self.addstr(' (%s)'%(presence,), curses.color_pair(theme.COLOR_INFORMATION_BAR))
        self.finish_line(theme.COLOR_INFORMATION_BAR)

    def draw_group_info(self, group):
        """
        draw the group information
        """
        self.addstr(0, 0, group.name, curses.color_pair(theme.COLOR_INFORMATION_BAR))
        self.finish_line(theme.COLOR_INFORMATION_BAR)

    def refresh(self, selected_row):
        with g_lock:
            self._win.erase()
            if isinstance(selected_row, RosterGroup):
                self.draw_group_info(selected_row)
            elif isinstance(selected_row, Contact):
                self.draw_contact_info(selected_row.get_highest_priority_resource(),
                                       selected_row.get_bare_jid())
            elif isinstance(selected_row, Resource):
                self.draw_contact_info(selected_row)
            self._refresh()

class ListWin(Win):
    """
    A list (with no depth, so not for the roster) that can be
    scrolled up and down, with one selected line at a time
    """
    def __init__(self, columns, with_headers=True):
        self._columns = columns # a tuple with the name of the columns
        self._columns_sizes = {} # a dict {'column_name': size}
        self.sorted_by = (None, None) # for example: ('name', '↑')
        self.lines = []         # a list of dicts
        self._selected_row = 0
        self._starting_pos = 0  # The column number from which we start the refresh

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def resize_columns(self, dic):
        """
        Resize the width of the columns
        """
        self._columns_sizes = dic

    def sort_by_column(self, col_name, asc=True):
        """
        Sort the list by the given column, ascendant or descendant
        """
        pass                    # TODO

    def add_lines(self, lines):
        """
        Append some lines at the end of the list
        """
        if not lines:
            return
        self.lines += lines
        self.refresh()

    def get_selected_row(self):
        """
        Return the tuple representing the selected row
        """
        if self._selected_row is not None:
            return self.lines[self._selected_row]
        return None

    def refresh(self):
        with g_lock:
            self._win.erase()
            lines = self.lines[self._starting_pos:self._starting_pos+self.height]
            for y, line in enumerate(lines):
                x = 0
                for col in self._columns:
                    try:
                        txt = line[col] or ''
                    except (KeyError):
                        txt = ''
                    size = self._columns_sizes[col]
                    txt += ' ' * (size-len(txt))
                    if not txt:
                        continue
                    if line is self.lines[self._selected_row]:
                        self.addstr(y, x, txt[:size], curses.color_pair(theme.COLOR_INFORMATION_BAR))
                    else:
                        self.addstr(y, x, txt[:size])
                    x += size
            self._refresh()

    def move_cursor_down(self):
        """
        Move the cursor Down
        """
        if not self.lines:
            return
        if self._selected_row < len(self.lines) - 1:
            self._selected_row += 1
        while self._selected_row >= self._starting_pos + self.height:
            self._starting_pos += self.height // 2
        if self._starting_pos < 0:
            self._starting_pos = 0
        return True

    def move_cursor_up(self):
        """
        Move the cursor Up
        """
        if not self.lines:
            return
        if self._selected_row > 0:
            self._selected_row -= 1
        while self._selected_row < self._starting_pos:
            self._starting_pos -= self.height // 2
        return True

class ColumnHeaderWin(Win):
    """
    A class displaying the column's names
    """
    def __init__(self, columns):
        self._columns = columns
        self._columns_sizes = {}

    def resize_columns(self, dic):
        self._columns_sizes = dic

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self):
        with g_lock:
            self._win.erase()
            x = 0
            for col in self._columns:
                txt = col
                size = self._columns_sizes[col]
                txt += ' ' * (size-len(txt))
                self.addstr(0, x, txt, curses.color_pair(theme.COLOR_STATUS_UNAVAILABLE))
                x += size
            self._refresh()

# class SimpleTextWin(Win):
#     def __init__(self, text):
#         self._text = text
#         self.built_lines = []

#     def resize(self, height, width, y, x, stdscr):
#         self._resize(height, width, y, x, stdscr)
#         self.rebuild_text()

#     def rebuild_text(self):
        
#     def refresh(self):
#         pass
