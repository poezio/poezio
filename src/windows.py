# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Define all the windows.
A window is a little part of the screen, for example the input window,
the text window, the roster window, etc.
A Tab (see tab.py) is composed of multiple Windows
"""

from gettext import (bindtextdomain, textdomain, bind_textdomain_codeset,
                     gettext as _)

import logging
log = logging.getLogger(__name__)

import curses
import string
from math import ceil, log10
from config import config

from threading import RLock

from contact import Contact
from roster import RosterGroup
from poopt import cut_text

from sleekxmpp import JID
from common import safeJID

import core
import wcwidth
import singleton
import collections

from theming import get_theme, to_curses_attr

allowed_color_digits = ('0', '1', '2', '3', '4', '5', '6', '7')
# msg is a reference to the corresponding Message tuple. text_start and text_end are the position
# delimiting the text in this line.
# first is a bool telling if this is the first line of the message.
Line = collections.namedtuple('Line', 'msg start_pos end_pos')

g_lock = RLock()

LINES_NB_LIMIT = 4096

def truncate_nick(nick, size=None):
    size = size or config.get('max_nick_length', 25)
    if size < 1:
        size = 1
    if nick and len(nick) > size:
        return nick[:size]+'…'
    return nick


class Win(object):
    _win_core = None
    _tab_win = None
    def __init__(self):
        self._win = None

    def _resize(self, height, width, y, x):
        if height == 0 or width == 0:
            self.height, self.width = height, width
            return
        self.height, self.width, self.x, self.y = height, width, x, y
        try:
            self._win = Win._tab_win.derwin(height, width, y, x)
        except:
            log.debug('DEBUG: mvwin returned ERR. Please investigate')

        # If this ever fail, uncomment that ^

    def resize(self, height, width, y, x):
        """
        Override if something has to be done on resize
        """
        with g_lock:
            self._resize(height, width, y, x)

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

    def move(self, y, x):
        try:
            self._win.move(y, x)
        except:
            self._win.move(0, 0)

    def addstr_colored(self, text, y=None, x=None):
        """
        Write a string on the window, setting the
        attributes as they are in the string.
        For example:
        \x19bhello → hello in bold
        \x191}Bonj\x192}our → 'Bonj' in red and 'our' in green
        next_attr_char is the \x19 delimiter
        attr_char is the char following it, it can be
        one of 'u', 'b', 'c[0-9]'
        """
        if y is not None and x is not None:
            self.move(y, x)
        next_attr_char = text.find('\x19')
        while next_attr_char != -1 and text:
            if next_attr_char + 1 < len(text):
                attr_char = text[next_attr_char+1].lower()
            else:
                attr_char = str()
            if next_attr_char != 0:
                self.addstr(text[:next_attr_char])
            if attr_char == 'o':
                self._win.attrset(0)
            elif attr_char == 'u':
                self._win.attron(curses.A_UNDERLINE)
            elif attr_char == 'b':
                self._win.attron(curses.A_BOLD)
            if attr_char in string.digits and attr_char != '':
                color_str = text[next_attr_char+1:text.find('}', next_attr_char)]
                if color_str:
                    self._win.attron(to_curses_attr((int(color_str), -1)))
                text = text[next_attr_char+len(color_str)+2:]
            else:
                text = text[next_attr_char+2:]
            next_attr_char = text.find('\x19')
        self.addstr(text)

    def addstr_colored_lite(self, text, y=None, x=None):
        """
        Just like addstr_colored, but only handles colors with one digit.
        \x193 is the 3rd color. We do not use any } char in this version
        """
        if y is not None and x is not None:
            self.move(y, x)
        next_attr_char = text.find('\x19')
        while next_attr_char != -1:
            if next_attr_char + 1 < len(text):
                attr_char = text[next_attr_char+1].lower()
            else:
                attr_char = str()
            if next_attr_char != 0:
                self.addstr(text[:next_attr_char])
            text = text[next_attr_char+2:]
            if attr_char == 'o':
                self._win.attrset(0)
            elif attr_char == 'u':
                self._win.attron(curses.A_UNDERLINE)
            elif attr_char == 'b':
                self._win.attron(curses.A_BOLD)
            elif attr_char in string.digits and attr_char != '':
                self._win.attron(to_curses_attr((int(attr_char), -1)))
            next_attr_char = text.find('\x19')
        self.addstr(text)

    def finish_line(self, color=None):
        """
        Write colored spaces until the end of line
        """
        (y, x) = self._win.getyx()
        size = self.width-x
        if color:
            self.addnstr(' '*size, size, to_curses_attr(color))
        else:
            self.addnstr(' '*size, size)

    @property
    def core(self):
        if not Win._win_core:
            Win._win_core = singleton.Singleton(core.Core)
        return Win._win_core

class UserList(Win):
    def __init__(self):
        Win.__init__(self)
        self.pos = 0
        self.color_role = {'moderator': lambda: get_theme().COLOR_USER_MODERATOR,
                'participant': lambda: get_theme().COLOR_USER_PARTICIPANT,
                'visitor': lambda: get_theme().COLOR_USER_VISITOR,
                'none': lambda: get_theme().COLOR_USER_NONE,
                '': lambda: get_theme().COLOR_USER_NONE
               }
        self.symbol_affiliation = {'owner': lambda: get_theme().CHAR_AFFILIATION_OWNER,
                'admin': lambda: get_theme().CHAR_AFFILIATION_ADMIN,
                'member': lambda: get_theme().CHAR_AFFILIATION_MEMBER,
                'none': lambda: get_theme().CHAR_AFFILIATION_NONE, }
        self.color_show = {'xa': lambda: get_theme().COLOR_STATUS_XA,
                'none': lambda: get_theme().COLOR_STATUS_NONE,
                '': lambda: get_theme().COLOR_STATUS_NONE,
                'dnd': lambda: get_theme().COLOR_STATUS_DND,
                'away': lambda: get_theme().COLOR_STATUS_AWAY,
                'chat': lambda: get_theme().COLOR_STATUS_CHAT
               }
    def scroll_up(self):
        self.pos += self.height-1
        return True

    def scroll_down(self):
        pos = self.pos
        self.pos -= self.height-1
        if self.pos < 0:
            self.pos = 0
        return self.pos != pos

    def draw_plus(self, y):
        self.addstr(y, self.width-2, '++', to_curses_attr(get_theme().COLOR_MORE_INDICATOR))

    def refresh(self, users):
        log.debug('Refresh: %s',self.__class__.__name__)
        if config.get("hide_user_list", "false") == "true":
            return # do not refresh if this win is hidden.
        with g_lock:
            self._win.erase()
            if config.get('user_list_sort', 'desc').lower() == 'asc':
                y, x = self._win.getmaxyx()
                y -= 1
                users = sorted(users, reverse=True)
            else:
                y = 0
                users = sorted(users)

            if len(users) < self.height:
                self.pos = 0
            elif self.pos >= len(users) - self.height and self.pos != 0:
                self.pos = len(users) - self.height
            for user in users[self.pos:]:
                self.draw_role_affiliation(y, user)
                self.draw_status_chatstate(y, user)
                self.addstr(y, 2, user.nick[:self.width-2], to_curses_attr(user.color))
                if config.get('user_list_sort', 'desc').lower() == 'asc':
                    y -= 1
                else:
                    y += 1
                if y == self.height:
                    break
            # draw indicators of position in the list
            if self.pos > 0:
                if config.get('user_list_sort', 'desc').lower() == 'asc':
                    self.draw_plus(self.height-1)
                else:
                    self.draw_plus(0)
            if self.pos + self.height < len(users):
                if config.get('user_list_sort', 'desc').lower() == 'asc':
                    self.draw_plus(0)
                else:
                    self.draw_plus(self.height-1)
            self._refresh()

    def draw_role_affiliation(self, y, user):
        if not user.role in self.color_role:
            color = get_theme().COLOR_USER_NONE
        else:
            color = self.color_role[user.role]()
        symbol = self.symbol_affiliation.get(user.affiliation, lambda: '-')()
        self.addstr(y, 1, symbol, to_curses_attr(color))

    def draw_status_chatstate(self, y, user):
        if not user.show in self.color_show:
            show_col = get_theme().COLOR_STATUS_NONE
        else:
            show_col = self.color_show[user.show]()
        if user.chatstate == 'composing':
            char = get_theme().CHAR_CHATSTATE_COMPOSING
        elif user.chatstate == 'active':
            char = get_theme().CHAR_CHATSTATE_ACTIVE
        elif user.chatstate == 'paused':
            char = get_theme().CHAR_CHATSTATE_PAUSED
        else:
            char = get_theme().CHAR_STATUS
        self.addstr(y, 0, char, to_curses_attr(show_col))

    def resize(self, height, width, y, x):
        with g_lock:
            self._resize(height, width, y, x)
            self._win.attron(to_curses_attr(get_theme().COLOR_VERTICAL_SEPARATOR))
            self._win.vline(0, 0, curses.ACS_VLINE, self.height)
            self._win.attroff(to_curses_attr(get_theme().COLOR_VERTICAL_SEPARATOR))

class Topic(Win):
    def __init__(self):
        Win.__init__(self)
        self._message = ''

    def refresh(self, topic=None):
        log.debug('Refresh: %s',self.__class__.__name__)
        with g_lock:
            self._win.erase()
            if topic:
                msg = topic[:self.width-1]
            else:
                msg = self._message[:self.width-1]
            self.addstr(0, 0, msg, to_curses_attr(get_theme().COLOR_TOPIC_BAR))
            (y, x) = self._win.getyx()
            remaining_size = self.width - x
            if remaining_size:
                self.addnstr(' '*remaining_size, remaining_size,
                             to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
            self._refresh()

    def set_message(self, message):
        self._message = message

class GlobalInfoBar(Win):
    def __init__(self):
        Win.__init__(self)

    def refresh(self):
        log.debug('Refresh: %s',self.__class__.__name__)
        with g_lock:
            self._win.erase()
            self.addstr(0, 0, "[", to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

            create_gaps = config.getl('create_gaps', 'false') == 'true'
            show_names = config.getl('show_tab_names', 'false') == 'true'
            show_nums = config.getl('show_tab_numbers', 'true') != 'false'
            use_nicks = config.getl('use_tab_nicks', 'true') != 'false'
            # ignore any remaining gap tabs if the feature is not enabled
            sorted_tabs = [tab for tab in self.core.tabs if tab] if not create_gaps else self.core.tabs[:]
            for nb, tab in enumerate(sorted_tabs):
                if not tab: continue
                color = tab.color
                if config.get('show_inactive_tabs', 'true') == 'false' and\
                        color is get_theme().COLOR_TAB_NORMAL:
                    continue
                try:
                    if show_nums or not show_names:
                        self.addstr("%s" % str(nb), to_curses_attr(color))
                        if show_names:
                            self.addstr(' ', to_curses_attr(color))
                    if show_names:
                        if use_nicks:
                            self.addstr("%s" % str(tab.get_nick()), to_curses_attr(color))
                        else:
                            self.addstr("%s" % str(tab.get_name()), to_curses_attr(color))
                    self.addstr("|", to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
                except:             # end of line
                    break
            (y, x) = self._win.getyx()
            self.addstr(y, x-1, '] ', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
            (y, x) = self._win.getyx()
            remaining_size = self.width - x
            self.addnstr(' '*remaining_size, remaining_size,
                         to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
            self._refresh()

class VerticalGlobalInfoBar(Win):
    def __init__(self, scr):
        Win.__init__(self)
        self._win = scr

    def refresh(self):
        with g_lock:
            height, width = self._win.getmaxyx()
            self._win.erase()
            sorted_tabs = [tab for tab in self.core.tabs if tab]
            if config.get('show_inactive_tabs', 'true') == 'false':
                sorted_tabs = [tab for tab in sorted_tabs if\
                                   tab.vertical_color != get_theme().COLOR_VERTICAL_TAB_NORMAL]
            nb_tabs = len(sorted_tabs)
            use_nicks = config.getl('use_tab_nicks', 'true') != 'false'
            if nb_tabs >= height:
                for y, tab in enumerate(sorted_tabs):
                    if tab.vertical_color == get_theme().COLOR_VERTICAL_TAB_CURRENT:
                        pos = y
                        break
                # center the current tab as much as possible
                if pos < height//2:
                    sorted_tabs = sorted_tabs[:height]
                elif nb_tabs - pos <= height//2:
                    sorted_tabs = sorted_tabs[-height:]
                else:
                    sorted_tabs = sorted_tabs[pos-height//2 : pos+height//2]
            for y, tab in enumerate(sorted_tabs):
                color = tab.vertical_color
                self.addstr(y if config.get('vertical_tab_list_sort', 'desc') != 'asc' else height - y - 1, 0, "%2d" % tab.nb, to_curses_attr(get_theme().COLOR_VERTICAL_TAB_NUMBER))
                self.addstr('.')
                if use_nicks:
                    self.addnstr("%s" % tab.get_nick(), width - 4, to_curses_attr(color))
                else:
                    self.addnstr("%s" % tab.get_name(), width - 4, to_curses_attr(color))
            self._win.attron(to_curses_attr(get_theme().COLOR_VERTICAL_SEPARATOR))
            self._win.vline(0, width-1, curses.ACS_VLINE, height)
            self._win.attroff(to_curses_attr(get_theme().COLOR_VERTICAL_SEPARATOR))
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
        Print, link in Weechat, a -MORE(n)- where n
        is the number of available lines to scroll
        down
        """
        if window.pos > 0:
            plus = ' -MORE(%s)-' % window.pos
            self.addstr(plus, to_curses_attr(get_theme().COLOR_SCROLLABLE_NUMBER))

class PrivateInfoWin(InfoWin):
    """
    The live above the information window, displaying informations
    about the MUC user we are talking to
    """
    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, name, window, chatstate):
        log.debug('Refresh: %s',self.__class__.__name__)
        with g_lock:
            self._win.erase()
            self.write_room_name(name)
            self.print_scroll_position(window)
            self.write_chatstate(chatstate)
            self.finish_line(get_theme().COLOR_INFORMATION_BAR)
            self._refresh()

    def write_room_name(self, name):
        jid = safeJID(name)
        room_name, nick = jid.bare, jid.resource
        self.addstr(nick, to_curses_attr(get_theme().COLOR_PRIVATE_NAME))
        txt = ' from room %s' % room_name
        self.addstr(txt, to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_chatstate(self, state):
        if state:
            self.addstr(' %s' % (state,), to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

class ConversationInfoWin(InfoWin):
    """
    The line above the information window, displaying informations
    about the user we are talking to
    """
    color_show = {'xa': lambda: get_theme().COLOR_STATUS_XA,
                  'none': lambda: get_theme().COLOR_STATUS_ONLINE,
                  '': lambda: get_theme().COLOR_STATUS_ONLINE,
                  'available': lambda: get_theme().COLOR_STATUS_ONLINE,
                  'dnd': lambda: get_theme().COLOR_STATUS_DND,
                  'away': lambda: get_theme().COLOR_STATUS_AWAY,
                  'chat': lambda: get_theme().COLOR_STATUS_CHAT,
                  'unavailable': lambda: get_theme().COLOR_STATUS_UNAVAILABLE
                  }

    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, jid, contact, window, chatstate, informations):
        # contact can be None, if we receive a message
        # from someone not in our roster. In this case, we display
        # only the maximum information from the message we can get.
        log.debug('Refresh: %s',self.__class__.__name__)
        jid = safeJID(jid)
        if contact:
            if jid.resource:
                resource = contact[jid.full]
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
            self.write_chatstate(chatstate)
            self.write_additional_informations(informations, jid)
            self.finish_line(get_theme().COLOR_INFORMATION_BAR)
            self._refresh()

    def write_additional_informations(self, informations, jid):
        """
        Write all informations added by plugins by getting the
        value returned by the callbacks.
        """
        for key in informations:
            self.addstr(informations[key](jid), to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_resource_information(self, resource):
        """
        Write the informations about the resource
        """
        if not resource:
            presence = "unavailable"
        else:
            presence = resource.presence
        color = RosterWin.color_show[presence]()
        self.addstr('[', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.addstr(get_theme().CHAR_STATUS, to_curses_attr(color))
        self.addstr(']', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_contact_informations(self, contact):
        """
        Write the informations about the contact
        """
        if not contact:
            self.addstr("(contact not in roster)", to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
            return
        display_name = contact.name or contact.bare_jid
        self.addstr('%s '%(display_name), to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_contact_jid(self, jid):
        """
        Just write the jid that we are talking to
        """
        self.addstr('[', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.addstr(jid.full, to_curses_attr(get_theme().COLOR_CONVERSATION_NAME))
        self.addstr('] ', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_chatstate(self, state):
        if state:
            self.addstr(' %s' % (state,), to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

class ConversationStatusMessageWin(InfoWin):
    """
    The upper bar displaying the status message of the contact
    """
    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, jid, contact):
        log.debug('Refresh: %s',self.__class__.__name__)
        jid = safeJID(jid)
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        with g_lock:
            self._win.erase()
            if resource:
                self.write_status_message(resource)
            self.finish_line(get_theme().COLOR_INFORMATION_BAR)
            self._refresh()

    def write_status_message(self, resource):
        self.addstr(resource.status, to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

class MucInfoWin(InfoWin):
    """
    The line just above the information window, displaying informations
    about the MUC we are viewing
    """
    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, room, window=None):
        log.debug('Refresh: %s',self.__class__.__name__)
        with g_lock:
            self._win.erase()
            self.write_room_name(room)
            self.write_own_nick(room)
            self.write_disconnected(room)
            self.write_role(room)
            if window:
                self.print_scroll_position(window)
            self.finish_line(get_theme().COLOR_INFORMATION_BAR)
            self._refresh()

    def write_room_name(self, room):
        self.addstr('[', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.addstr(room.name, to_curses_attr(get_theme().COLOR_GROUPCHAT_NAME))
        self.addstr('] ', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_disconnected(self, room):
        """
        Shows a message if the room is not joined
        """
        if not room.joined:
            self.addstr(' -!- Not connected ', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_own_nick(self, room):
        """
        Write our own nick in the info bar
        """
        nick = room.own_nick
        if not nick:
            return
        self.addstr(truncate_nick(nick, 13), to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

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
        self.addstr(txt, to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

class TextWin(Win):
    def __init__(self, lines_nb_limit=config.get('max_lines_in_memory', 2048)):
        Win.__init__(self)
        self.lines_nb_limit = lines_nb_limit
        self.pos = 0
        self.built_lines = []   # Each new message is built and kept here.
        # on resize, we rebuild all the messages

        self.lock = False
        self.lock_buffer = []

        # the Lines of the highlights in that buffer
        self.highlights = []
        # the current HL position in that list
        self.hl_pos = -1

        self.separator_after = None

    def toggle_lock(self):
        if self.lock:
            self.release_lock()
        else:
            self.acquire_lock()

    def acquire_lock(self):
        self.lock = True

    def release_lock(self):
        for line in self.lock_buffer:
            self.built_lines.append(line)
        self.lock = False

    def next_highlight(self):
        """
        Go to the next highlight in the buffer.
        (depending on which highlight was selected before)
        if the buffer is already positionned on the last, of if there are no
        highlights, scroll to the end of the buffer.
        """
        log.debug('Going to the next highlight…')
        if not self.highlights or self.hl_pos == -1 or \
                self.hl_pos == len(self.highlights)-1:
            self.hl_pos = -1
            self.pos = 0
            return
        hl_size = len(self.highlights) - 1
        if self.hl_pos < hl_size:
            self.hl_pos += 1
        else:
            self.hl_pos = hl_size

        hl = self.highlights[self.hl_pos]
        pos = None
        while not pos:
            try:
                pos = self.built_lines.index(hl)
            except ValueError:
                self.highlights = self.highlights[self.hl_pos+1:]
                if not self.highlights:
                    self.hl_pos = -1
                    self.pos = 0
                    return
                hl = self.highlights[0]
        self.pos =  len(self.built_lines) - pos - self.height
        if self.pos < 0 or self.pos >= len(self.built_lines):
            self.pos = 0

    def previous_highlight(self):
        """
        Go to the previous highlight in the buffer.
        (depending on which highlight was selected before)
        if the buffer is already positionned on the first, or if there are no
        highlights, scroll to the end of the buffer.
        """
        log.debug('Going to the previous highlight…')
        if not self.highlights or self.hl_pos == 0:
            self.hl_pos = -1
            self.pos =  0
            return
        if self.hl_pos < 0:
            self.hl_pos = len(self.highlights) - 1
        elif self.hl_pos > 0:
            self.hl_pos -= 1

        hl = self.highlights[self.hl_pos]
        pos = None
        while not pos:
            try:
                pos = self.built_lines.index(hl)
            except ValueError:
                self.highlights = self.highlights[self.hl_pos+1:]
                if not self.highlights:
                    self.hl_pos = -1
                    self.pos = 0
                    return
                hl = self.highlights[0]
        self.pos = len(self.built_lines) - pos - self.height
        if self.pos < 0 or self.pos >= len(self.built_lines):
            self.pos = 0

    def scroll_up(self, dist=14):
        pos = self.pos
        self.pos += dist
        if self.pos + self.height > len(self.built_lines):
            self.pos = len(self.built_lines) - self.height
            if self.pos < 0:
                self.pos = 0
        return self.pos != pos

    def scroll_down(self, dist=14):
        pos = self.pos
        self.pos -= dist
        if self.pos <= 0:
            self.pos = 0
        return self.pos != pos

    def scroll_to_separator(self):
        """
        Scroll until separator is centered. If no separator is
        present, scroll at the top of the window
        """
        if None in self.built_lines:
            self.pos = len(self.built_lines) - self.built_lines.index(None) - self.height + 1
            if self.pos < 0:
                self.pos = 0
            # Chose a proper position (not too high)
            self.scroll_up(0)

    def remove_line_separator(self):
        """
        Remove the line separator
        """
        log.debug('remove_line_separator')
        if None in self.built_lines:
            self.built_lines.remove(None)
            self.separator_after = None

    def add_line_separator(self, room=None):
        """
        add a line separator at the end of messages list
        room is a textbuffer that is needed to get the previous message
        (in case of resize)
        """
        if None not in self.built_lines:
            self.built_lines.append(None)
            if room and room.messages:
                self.separator_after = room.messages[-1]

    def build_new_message(self, message, history=None, clean=True, highlight=False, timestamp=False):
        """
        Take one message, build it and add it to the list
        Return the number of lines that are built for the given
        message.
        """
        lines = self.build_message(message, timestamp=timestamp)
        if self.lock:
            self.lock_buffer.extend(lines)
        else:
            self.built_lines.extend(lines)
        if not lines or not lines[0]:
            return 0
        if highlight:
            self.highlights.append(lines[0])
        if clean:
            while len(self.built_lines) > self.lines_nb_limit:
                self.built_lines.pop(0)
        return len(lines)

    def build_message(self, message, timestamp=False):
        """
        Build a list of lines from a message, without adding it
        to a list
        """
        if message is None:  # line separator
            return [None]
        txt = message.txt
        if not txt:
            return []
        ret = []
        nick = truncate_nick(message.nickname)
        offset = 0
        if nick:
            offset += wcwidth.wcswidth(nick) + 2 # + nick + '> ' length
        if message.revisions > 0:
            offset += ceil(log10(message.revisions + 1))
        if message.me:
            offset += 1 # '* ' before and ' ' after
        if timestamp:
            if message.str_time:
                offset += 1 + len(message.str_time)
            if get_theme().CHAR_TIME_LEFT and message.str_time:
                offset += 1
            if get_theme().CHAR_TIME_RIGHT and message.str_time:
                offset += 1
        lines = cut_text(txt, self.width-offset)
        for line in lines:
            saved = Line(msg=message, start_pos=line[0], end_pos=line[1])
            ret.append(saved)
        return ret

    def refresh(self):
        log.debug('Refresh: %s', self.__class__.__name__)
        if self.height <= 0:
            return
        if self.pos == 0:
            lines = self.built_lines[-self.height:]
        else:
            lines = self.built_lines[-self.height-self.pos:-self.pos]
        with_timestamps = config.get("show_timestamps", 'true') != 'false'
        with g_lock:
            self._win.move(0, 0)
            self._win.erase()
            for y, line in enumerate(lines):
                if line:
                    msg = line.msg
                    if line.start_pos == 0:
                        if msg.nick_color:
                            color = msg.nick_color
                        elif msg.user:
                            color = msg.user.color
                        else:
                            color = None
                        if with_timestamps:
                            self.write_time(msg.str_time)
                        if msg.me:
                            self._win.attron(to_curses_attr(get_theme().COLOR_ME_MESSAGE))
                            self.addstr('* ')
                            self.write_nickname(msg.nickname, color, msg.highlight)
                            if msg.revisions:
                                self._win.attron(to_curses_attr(get_theme().COLOR_REVISIONS_MESSAGE))
                                self.addstr('%d' % msg.revisions)
                                self._win.attrset(0)
                            self.addstr(' ')
                        else:
                            self.write_nickname(msg.nickname, color, msg.highlight)
                            if msg.revisions:
                                self._win.attron(to_curses_attr(get_theme().COLOR_REVISIONS_MESSAGE))
                                self.addstr('%d' % msg.revisions)
                                self._win.attrset(0)
                            self.addstr('> ')
                if y != self.height-1:
                    self.addstr('\n')
            self._win.attrset(0)
            for y, line in enumerate(lines):
                if not line:
                    self.write_line_separator(y)
                else:
                    self.write_text(y,
                                    # Offset for the timestamp (if any) plus a space after it
                                    (0 if not with_timestamps else (len(line.msg.str_time) + 1)) +
                                    # Offset for the nickname (if any) plus a space and a > after it
                                    (0 if not line.msg.nickname else (len(truncate_nick(line.msg.nickname)) + (3 if line.msg.me else 2) + ceil(log10(line.msg.revisions + 1)))),
                            line.msg.txt[line.start_pos:line.end_pos])
                if y != self.height-1:
                    self.addstr('\n')
            self._win.attrset(0)
            self._refresh()

    def write_line_separator(self, y):
        self.addnstr(y, 0, '- '*(self.width//2-1)+'-', self.width, to_curses_attr(get_theme().COLOR_NEW_TEXT_SEPARATOR))

    def write_text(self, y, x, txt):
        """
        write the text of a line.
        """
        self.addstr_colored(txt, y, x)

    def write_nickname(self, nickname, color, highlight=False):
        """
        Write the nickname, using the user's color
        and return the number of written characters
        """
        if not nickname:
            return
        if highlight:
            hl_color = get_theme().COLOR_HIGHLIGHT_NICK
            if hl_color == "reverse":
                self._win.attron(curses.A_REVERSE)
            else:
                color = hl_color
        if color:
            self._win.attron(to_curses_attr(color))
        self.addstr(truncate_nick(nickname))
        if color:
            self._win.attroff(to_curses_attr(color))
        if highlight and hl_color == "reverse":
            self._win.attroff(curses.A_REVERSE)

    def write_time(self, time):
        """
        Write the date on the yth line of the window
        """
        if time:
            self.addstr(time)
            self.addstr(' ')

    def resize(self, height, width, y, x, room=None):
        with g_lock:
            self._resize(height, width, y, x)
            if room:
                self.rebuild_everything(room)

    def rebuild_everything(self, room):
        self.built_lines = []
        with_timestamps = config.get("show_timestamps", 'true') != 'false'
        for message in room.messages:
            self.build_new_message(message, clean=False, timestamp=with_timestamps)
            if self.separator_after is message:
                self.build_new_message(None)
        while len(self.built_lines) > self.lines_nb_limit:
            self.built_lines.pop(0)

    def modify_message(self, old_id, message):
        """
        Find a message, and replace it with a new one
        (instead of rebuilding everything in order to correct a message)
        """
        with_timestamps = config.get("show_timestamps", 'true') != 'false'
        for i in range(len(self.built_lines)-1, -1, -1):
            if self.built_lines[i] and self.built_lines[i].msg.identifier == old_id:
                index = i
                while index >= 0 and self.built_lines[index].msg.identifier == old_id:
                    self.built_lines.pop(index)
                    index -= 1
                index += 1
                lines = self.build_message(message, timestamp=with_timestamps)
                for line in lines:
                    self.built_lines.insert(index, line)
                    index +=1
                break

    def __del__(self):
        log.debug('** TextWin: deleting %s built lines', (len(self.built_lines)))
        del self.built_lines

class HelpText(Win):
    """
    A Window just displaying a read-only message.
    Usually used to replace an Input when the tab is in
    command mode.
    """
    def __init__(self, text=''):
        Win.__init__(self)
        self.txt = text

    def refresh(self, txt=None):
        log.debug('Refresh: %s',self.__class__.__name__)
        if txt:
            self.txt = txt
        with g_lock:
            self._win.erase()
            self.addstr(0, 0, self.txt[:self.width-1], to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
            self.finish_line(get_theme().COLOR_INFORMATION_BAR)
            self._refresh()

    def do_command(self, key, raw=False):
        return False

class YesNoInput(Win):
    """
    A Window just displaying a Yes/No input
    Used to ask a confirmation
    """
    def __init__(self, text=''):
        Win.__init__(self)
        self.key_func = {
                'y' : self.on_yes,
                'n' : self.on_no,
        }
        self.txt = text
        self.value = None

    def on_yes(self):
        self.value = True

    def on_no(self):
        self.value = False

    def refresh(self, txt=None):
        log.debug('Refresh: %s',self.__class__.__name__)
        if txt:
            self.txt = txt
        with g_lock:
            self._win.erase()
            self.addstr(0, 0, self.txt[:self.width-1], to_curses_attr(get_theme().COLOR_WARNING_PROMPT))
            self.finish_line(get_theme().COLOR_WARNING_PROMPT)
            self._refresh()

    def do_command(self, key, raw=False):
        if key.lower() in self.key_func:
            self.key_func[key]()

    def prompt(self):
        """Monopolizes the input while waiting for a recognized keypress"""
        cl = []
        while self.value is None:
            if len(cl) == 1 and cl[0] in self.key_func:
                self.key_func[cl[0]]()
            cl = self.core.read_keyboard()

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
            "M-[1;5D": self.jump_word_left,
            '^W': self.delete_word,
            '^K': self.delete_end_of_line,
            '^U': self.delete_begining_of_line,
            '^Y': self.paste_clipboard,
            '^A': self.key_home,
            '^E': self.key_end,
            'M-f': self.jump_word_right,
            "M-[1;5C": self.jump_word_right,
            "KEY_BACKSPACE": self.key_backspace,
            "M-KEY_BACKSPACE": self.delete_word,
            '^?': self.key_backspace,
            # '^J': self.add_line_break,
            }
        Win.__init__(self)
        self.text = ''
        self.pos = 0            # cursor position
        self.line_pos = 0 # position (in self.text) of
        self.on_input = None    # callback called on any key pressed
        self.color = None       # use this color on addstr

    def on_delete(self):
        """
        Remove all references kept to a tab, so that the tab
        can be garbage collected
        """
        del self.key_func

    def set_color(self, color):
        self.color = color
        self.rewrite_text()

    def is_empty(self):
        return len(self.text) == 0

    def jump_word_left(self):
        """
        Move the cursor one word to the left
        """
        if not len(self.text) or self.pos == 0:
            return
        separators = string.punctuation+' '
        while self.pos > 0 and self.text[self.pos+self.line_pos-1] in separators:
            self.key_left()
        while self.pos > 0 and self.text[self.pos+self.line_pos-1] not in separators:
            self.key_left()
        return True

    def jump_word_right(self):
        """
        Move the cursor one word to the right
        """
        if len(self.text) == self.pos+self.line_pos or not len(self.text):
            return
        separators = string.punctuation+' '
        while len(self.text) != self.pos+self.line_pos and self.text[self.pos+self.line_pos] in separators:
            self.key_right()
        while len(self.text) != self.pos+self.line_pos and self.text[self.pos+self.line_pos] not in separators:
            self.key_right()
        return True

    def delete_word(self):
        """
        Delete the word just before the cursor
        """
        if not len(self.text) or self.pos == 0:
            return
        separators = string.punctuation+' '
        while self.pos <= len(self.text) and self.pos > 0 and self.text[self.pos+self.line_pos-1] in separators:
            self.key_backspace()
        while self.pos <= len(self.text) and self.pos > 0 and self.text[self.pos+self.line_pos-1] not in separators:
            self.key_backspace()

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
            self.do_command(letter, False)
        self.rewrite_text()
        return True

    def key_dc(self):
        """
        delete char just after the cursor
        """
        self.reset_completion()
        if self.pos + self.line_pos == len(self.text):
            return              # end of line, nothing to delete
        if self.text[self.pos+self.line_pos] == '\x19':
            self.text = self.text[:self.pos+self.line_pos]+self.text[self.pos+self.line_pos+1:]
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

    def key_left(self, jump=True, reset=True):
        """
        Move the cursor one char to the left
        """
        if reset:
            self.reset_completion()
        if self.pos == self.width-1 and self.line_pos > 0:
            self.line_pos -= 1
        elif self.pos >= 1:
            self.pos -= 1
        if jump and self.pos+self.line_pos >= 1 and self.text[self.pos+self.line_pos-1] == '\x19':
            self.key_left()
        elif reset:
            self.rewrite_text()
        return True

    def key_right(self, jump=True, reset=True):
        """
        Move the cursor one char to the right
        """
        if reset:
            self.reset_completion()
        if self.pos == self.width-1:
            if self.line_pos + self.width-1 < len(self.text):
                self.line_pos += 1
        elif self.pos < len(self.text):
            self.pos += 1
        if jump and self.pos+self.line_pos < len(self.text) and self.text[self.pos+self.line_pos-1] == '\x19':
            self.key_right()
        elif reset:
            self.rewrite_text()
        return True

    def key_backspace(self, reset=True):
        """
        Delete the char just before the cursor
        """
        self.reset_completion()
        if self.pos == 0:
            return
        self.text = self.text[:self.pos+self.line_pos-1]+self.text[self.pos+self.line_pos:]
        self.key_left(False)
        if self.pos+self.line_pos >= 1 and self.text[self.pos+self.line_pos-1] == '\x19':
            self.text = self.text[:self.pos+self.line_pos-1]+self.text[self.pos+self.line_pos:]
        if reset:
            self.rewrite_text()
        return True

    def auto_completion(self, word_list, add_after='', quotify=True):
        """
        Complete the input, from a list of words
        if add_after is None, we use the value defined in completion
        plus a space, after the completion. If it's a string, we use it after the
        completion (with no additional space)
        """
        if quotify:
            for i, word in enumerate(word_list[:]):
                word_list[i] = '"' + word + '"'
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
        pos = self.pos + self.line_pos
        if pos < len(self.text) and after.endswith(' ') and self.text[pos] == ' ':
            after = after[:-1]  # remove the last space if we are already on a space
        if not self.last_completion:
            space_before_cursor = self.text.rfind(' ', 0, pos)
            if space_before_cursor != -1:
                begin = self.text[space_before_cursor+1:pos]
            else:
                begin = self.text[:pos]
            hit_list = []       # list of matching hits
            for word in word_list:
                if word.lower().startswith(begin.lower()):
                    hit_list.append(word)
                elif word.startswith('"') and word.lower()[1:].startswith(begin.lower()):
                    hit_list.append(word)
            if len(hit_list) == 0:
                return
            self.hit_list = hit_list
            end = len(begin)
        else:
            begin = self.last_completion
            end = len(begin) + len(after)
            self.hit_list.append(self.hit_list.pop(0)) # rotate list

        self.text = self.text[:pos-end] + self.text[pos:]
        pos -= end
        hit = self.hit_list[0] # take the first hit
        self.text = self.text[:pos] + hit + after + self.text[pos:]
        for i in range(end):
            try:
                self.key_left(reset=False)
            except:
                pass
        for i in range(len(hit + after)):
            self.key_right(reset=False)

        self.rewrite_text()
        self.last_completion = hit

    def do_command(self, key, reset=True, raw=False):
        if key in self.key_func:
            res = self.key_func[key]()
            if not raw and self.on_input:
                self.on_input(self.get_text())
            return res
        if not raw and (not key or len(key) > 1):
            return False   # ignore non-handled keyboard shortcuts
        if reset:
            self.reset_completion()
        self.text = self.text[:self.pos+self.line_pos]+key+self.text[self.pos+self.line_pos:]
        (y, x) = self._win.getyx()
        for i in range(len(key)):
            if x == self.width-1:
                self.line_pos += 1 # wcwidth.wcswidth(key)
            else:
                self.pos += 1 # wcwidth.wcswidth(key)
        if reset:
            self.rewrite_text()
        if self.on_input:
            self.on_input(self.get_text())
        return True

    def add_line_break(self):
        """
        Add a (real) \n to the line
        """
        self.do_command('\n')

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
            text = self.text.replace('\n', '|')
            self._win.erase()
            if self.color:
                self._win.attron(to_curses_attr(self.color))
            displayed_text = text[self.line_pos:self.line_pos+self.width-1]
            self.addstr(displayed_text)
            if self.color:
                (y, x) = self._win.getyx()
                size = self.width-x
                self.addnstr(' '*size, size, to_curses_attr(self.color))
            self.addstr(0, wcwidth.wcswidth(displayed_text[:self.pos]), '')
            if self.color:
                self._win.attroff(to_curses_attr(self.color))
            self._refresh()

    def refresh(self):
        log.debug('Refresh: %s',self.__class__.__name__)
        self.rewrite_text()

    def clear_text(self):
        self.text = ''
        self.pos = 0
        self.line_pos = 0
        self.rewrite_text()

    def key_enter(self):
        txt = self.get_text()
        self.clear_text()
        return txt

class MessageInput(Input):
    """
    The input featuring history and that is being used in
    Conversation, Muc and Private tabs
    Also letting the user enter colors or other text markups
    """
    history = list()            # The history is common to all MessageInput
    text_attributes = set(('b', 'o', 'u'))

    def __init__(self):
        Input.__init__(self)
        self.last_completion = None
        self.histo_pos = -1
        self.key_func["KEY_UP"] = self.key_up
        self.key_func["M-A"] =  self.key_up
        self.key_func["KEY_DOWN"] = self.key_down
        self.key_func["M-B"] = self.key_down
        self.key_func['^C'] = self.enter_attrib

    def key_up(self):
        """
        Get the previous line in the history
        """
        self.reset_completion()
        if self.histo_pos == -1 and self.get_text():
            if not MessageInput.history or MessageInput.history[0] != self.get_text():
                # add the message to history, we do not want to lose it
                MessageInput.history.insert(0, self.get_text())
                self.histo_pos += 1
        if self.histo_pos < len(MessageInput.history) - 1:
            self.histo_pos += 1
            self.text = MessageInput.history[self.histo_pos]
        self.key_end()

    def enter_attrib(self):
        """
        Read one more char (c) and add \x19c to the string
        """
        attr_char = self.core.read_keyboard()[0]
        if attr_char in self.text_attributes or attr_char in allowed_color_digits:
            self.do_command('\x19', False)
            self.do_command(attr_char)

    def key_down(self):
        """
        Get the next line in the history
        """
        self.reset_completion()
        if self.histo_pos > 0:
            self.histo_pos -= 1
            self.text = MessageInput.history[self.histo_pos]
        elif self.histo_pos <= 0 and self.get_text():
            if not MessageInput.history or MessageInput.history[0] != self.get_text():
                # add the message to history, we do not want to lose it
                MessageInput.history.insert(0, self.get_text())
            self.text = ''
            self.histo_pos = -1
        self.key_end()

    def key_enter(self):
        txt = self.get_text()
        if len(txt) != 0:
            if not MessageInput.history or MessageInput.history[0] != txt:
                # add the message to history, but avoid duplicates
                MessageInput.history.insert(0, txt)
            self.histo_pos = -1
        self.clear_text()
        return txt

    def rewrite_text(self):
        """
        Refresh the line onscreen, from the pos and pos_line, with colors
        """
        with g_lock:
            # Replace \t with ' ' just to make the input easily editable.
            # That's not perfect, because we cannot differenciate a tab and
            # a space. But at least it makes it possible to paste text
            # containing a tab by sending a real tab, not just four spaces
            # while still being able to edit the input in that case.
            text = self.text.replace('\n', '|').replace('\t', ' ')
            self._win.erase()
            if self.color:
                self._win.attron(to_curses_attr(self.color))
            displayed_text = text[self.line_pos:self.line_pos+self.width-1]
            self._win.attrset(0)
            self.addstr_colored_lite(displayed_text)
            self.addstr(0, wcwidth.wcswidth(displayed_text[:self.pos]), '')
            if self.color:
                self._win.attroff(to_curses_attr(self.color))
            self._refresh()

class CommandInput(Input):
    """
    An input with an help message in the left, with three given callbacks:
    one when when successfully 'execute' the command and when we abort it.
    The last callback is optional and is called on any input key
    This input is used, for example, in the RosterTab when, to replace the
    HelpMessage when a command is started
    The on_input callback
    """
    history = list()

    def __init__(self, help_message, on_abort, on_success, on_input=None):
        Input.__init__(self)
        self.on_abort = on_abort
        self.on_success = on_success
        self.on_input = on_input
        self.help_message = help_message
        self.key_func['^M'] = self.success
        self.key_func['^G'] = self.abort
        self.key_func['^C'] = self.abort
        self.key_func["KEY_UP"] = self.key_up
        self.key_func["M-A"] =  self.key_up
        self.key_func["KEY_DOWN"] = self.key_down
        self.key_func["M-B"] = self.key_down
        self.histo_pos = -1

    def do_command(self, key, refresh=True, raw=False):
        res = Input.do_command(self, key, refresh, raw)
        if self.on_input:
            self.on_input(self.get_text())
        return res

    def disable_history(self):
        """
        Disable the history (up/down) keys
        """
        if 'KEY_UP' in self.key_func:
            del self.key_func['KEY_UP']
        if 'KEY_DOWN' in self.key_func:
            del self.key_func['KEY_DOWN']

    @property
    def history_disabled(self):
        return ('KEY_UP' not in self.key_func and 'KEY_DOWN' not in self.key_func)

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
            self.addstr(self.help_message, to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
            cursor_pos = self.pos + len(self.help_message)
            if len(self.help_message):
                self.addstr(' ')
                cursor_pos += 1
            self.addstr(self.text[self.line_pos:self.line_pos+self.width-1])
            self.addstr(0, cursor_pos, '') # WTF, this works but .move() doesn't…
            self._refresh()

    def on_delete(self):
        """
        SERIOUSLY BIG WTF.

        I can do
        self.key_func.clear()

        but not
        del self.key_func
        because that would raise an AttributeError exception. WTF.
        """
        self.on_abort = None
        self.on_success = None
        self.on_input = None
        self.key_func.clear()

    def key_up(self):
        """
        Get the previous line in the history
        """
        self.reset_completion()
        if self.histo_pos == -1 and self.get_text():
            if not self.history or self.history[0] != self.get_text():
                # add the message to history, we do not want to lose it
                self.history.insert(0, self.get_text())
                self.histo_pos += 1
        if self.histo_pos < len(self.history) - 1:
            self.histo_pos += 1
            self.text = self.history[self.histo_pos]
        self.key_end()

    def key_down(self):
        """
        Get the next line in the history
        """
        self.reset_completion()
        if self.histo_pos > 0:
            self.histo_pos -= 1
            self.text = self.history[self.histo_pos]
        elif self.histo_pos <= 0 and self.get_text():
            if not self.history or self.history[0] != self.get_text():
                # add the message to history, we do not want to lose it
                self.history.insert(0, self.get_text())
            self.text = ''
            self.histo_pos = -1
        self.key_end()

    def key_enter(self):
        txt = self.get_text()
        if len(txt) != 0:
            if not self.history or self.history[0] != txt:
                # add the message to history, but avoid duplicates
                self.history.insert(0, txt)
            self.histo_pos = -1


class VerticalSeparator(Win):
    """
    Just a one-column window, with just a line in it, that is
    refreshed only on resize, but never on refresh, for efficiency
    """
    def __init__(self):
        Win.__init__(self)

    def rewrite_line(self):
        with g_lock:
            self._win.vline(0, 0, curses.ACS_VLINE, self.height, to_curses_attr(get_theme().COLOR_VERTICAL_SEPARATOR))
            self._refresh()

    def refresh(self):
        log.debug('Refresh: %s',self.__class__.__name__)
        self.rewrite_line()

class RosterWin(Win):
    color_show = {'xa': lambda: get_theme().COLOR_STATUS_XA,
            'none': lambda: get_theme().COLOR_STATUS_ONLINE,
            '': lambda: get_theme().COLOR_STATUS_ONLINE,
            'available': lambda: get_theme().COLOR_STATUS_ONLINE,
            'dnd':lambda: get_theme().COLOR_STATUS_DND,
            'away': lambda: get_theme().COLOR_STATUS_AWAY,
            'chat': lambda: get_theme().COLOR_STATUS_CHAT,
            'unavailable': lambda: get_theme().COLOR_STATUS_UNAVAILABLE
                  }

    def __init__(self):
        Win.__init__(self)
        self.pos = 0            # cursor position in the contact list
        self.start_pos = 1      # position of the start of the display
        self.roster_len = 0
        self.selected_row = None
        self.roster_cache = [] 

    def move_cursor_down(self, number=1):
        """
        Return True if we scrolled, False otherwise
        """
        pos = self.pos
        if self.pos < self.roster_len-number:
            self.pos += number
        else:
            self.pos = self.roster_len - 1
        if self.pos >= self.start_pos-1 + self.height-1:
            if number == 1:
                self.scroll_down(8)
            else:
                self.scroll_down(self.pos-self.start_pos - self.height // 2)
        return pos != self.pos

    def move_cursor_up(self, number=1):
        """
        Return True if we scrolled, False otherwise
        """
        pos = self.pos
        if self.pos-number >= 0:
            self.pos -= number
        else:
            self.pos = 0
        if self.pos <= self.start_pos:
            if number == 1:
                self.scroll_up(8)
            else:
                self.scroll_up(self.start_pos-self.pos + self.height // 2)
        return pos != self.pos

    def scroll_down(self, number=8):
        pos = self.start_pos
        if self.start_pos + number <= self.roster_len-1:
            self.start_pos += number
        else:
            self.start_pos = self.roster_len-1
        return self.start_pos != pos

    def scroll_up(self, number=8):
        pos = self.start_pos
        if self.start_pos - number > 0:
            self.start_pos -= number
        else:
            self.start_pos = 1
        return self.start_pos != pos

    def refresh(self, roster):
        """
        We get the roster object
        """
        log.debug('Refresh: %s',self.__class__.__name__)
        self.roster_cache = [] 
        with g_lock:
            self.roster_len = len(roster);
            while self.roster_len and self.pos >= self.roster_len:
                self.move_cursor_up()
            self._win.erase()
            self._win.move(0, 0)
            self.draw_roster_information(roster)
            y = 1
            show_offline = config.get('roster_show_offline', 'false') == 'true'
            sort = config.get('roster_sort', 'jid:show') or 'jid:show'
            group_sort = config.get('roster_group_sort', 'name') or 'name'
            for group in roster.get_groups(group_sort):
                contacts_filtered = group.get_contacts(roster.contact_filter)
                if (not show_offline and group.get_nb_connected_contacts() == 0) or not contacts_filtered:
                    continue    # Ignore empty groups
                # This loop is really REALLY ugly :^)
                if y-1 == self.pos:
                    self.selected_row = group
                if y >= self.start_pos:
                    self.draw_group(y-self.start_pos+1, group, y-1==self.pos)
                self.roster_cache.append(group)
                y += 1
                if group.folded:
                    continue
                for contact in group.get_contacts(roster.contact_filter, sort):
                    if not show_offline and len(contact) == 0:
                        continue
                    if y-1 == self.pos:
                        self.selected_row = contact
                    if y-self.start_pos+1 == self.height:
                        break
                    if y >= self.start_pos:
                        self.draw_contact_line(y-self.start_pos+1, contact, y-1==self.pos)
                    log.debug('ammend: %s',contact.bare_jid)
                    self.roster_cache.append(contact)
                    y += 1
                    if not contact.folded:
                        for resource in contact.get_resources():
                            if y-1 == self.pos:
                                self.selected_row = resource
                            if y-self.start_pos+1 == self.height:
                                break
                            if y >= self.start_pos:
                                self.draw_resource_line(y-self.start_pos+1, resource, y-1==self.pos)
                            self.roster_cache.append(resource)
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
        self.addstr(y, self.width-5, '++++', to_curses_attr(get_theme().COLOR_MORE_INDICATOR))

    def draw_roster_information(self, roster):
        """
        The header at the top
        """
        self.addstr('Roster: %s/%s contacts' % (
            roster.get_nb_connected_contacts(),
            len(roster.contacts))
            ,to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)

    def draw_group(self, y, group, colored):
        """
        Draw a groupname on a line
        """
        if colored:
            self._win.attron(to_curses_attr(get_theme().COLOR_SELECTED_ROW))
        if group.folded:
            self.addstr(y, 0, '[+] ')
        else:
            self.addstr(y, 0, '[-] ')
        contacts = " (%s/%s)" % (group.get_nb_connected_contacts(), len(group))
        self.addstr(y, 4, self.truncate_name(group.name, len(contacts)+4) + contacts)
        if colored:
            self._win.attroff(to_curses_attr(get_theme().COLOR_SELECTED_ROW))
        self.finish_line()

    def truncate_name(self, name, added):
        if len(name) + added <= self.width:
            return name
        return name[:self.width - added - 1] + '…'

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
            nb = ''
        else:
            presence = resource.presence
            nb = ' (%s)' % len(contact)
        color = RosterWin.color_show[presence]()
        added =  2 + len(get_theme().CHAR_STATUS) + len(nb)

        self.addstr(y, 0, ' ')
        self.addstr(get_theme().CHAR_STATUS, to_curses_attr(color))

        self.addstr(' ')
        if resource:
            self.addstr('[+] ' if contact.folded else '[-] ')
            added += 4
        if contact.ask:
            added += 1

        if config.getl('show_roster_jids', 'true') == 'false' and contact.name:
            display_name = '%s' % contact.name
        elif contact.name and contact.name != contact.bare_jid:
            display_name = '%s (%s)' % (contact.name, contact.bare_jid)
        else:
            display_name = '%s' % (contact.bare_jid,)
        display_name = self.truncate_name(display_name, added) + nb

        if colored:
            self.addstr(display_name, to_curses_attr(get_theme().COLOR_SELECTED_ROW))
        else:
            self.addstr(display_name)
        if contact.ask:
            self.addstr('?', to_curses_attr(get_theme().COLOR_IMPORTANT_TEXT))
        self.finish_line()

    def draw_resource_line(self, y, resource, colored):
        """
        Draw a specific resource line
        """
        color = RosterWin.color_show[resource.presence]()
        self.addstr(y, 4, get_theme().CHAR_STATUS, to_curses_attr(color))
        if colored:
            self.addstr(y, 6, self.truncate_name(str(resource.jid), 6), to_curses_attr(get_theme().COLOR_SELECTED_ROW))
        else:
            self.addstr(y, 6, self.truncate_name(str(resource.jid), 6))
        self.finish_line()

    def get_selected_row(self):
        if self.pos >= len(self.roster_cache):
            return self.selected_row
        if len(self.roster_cache) > 0:
            self.selected_row = self.roster_cache[self.pos]
            return self.roster_cache[self.pos]
        return None

class ContactInfoWin(Win):
    def __init__(self):
        Win.__init__(self)

    def draw_contact_info(self, contact):
        """
        draw the contact information
        """
        resource = contact.get_highest_priority_resource()
        if contact:
            jid = contact.bare_jid
        elif resource:
            jid = resource.jid
        else:
            jid = 'example@example.com' # should never happen
        if resource:
            presence = resource.presence
        else:
            presence = 'unavailable'
        self.addstr(0, 0, '%s (%s)'%(jid, presence,), to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        self.addstr(1, 0, 'Subscription: %s' % (contact.subscription,))
        if contact.ask:
            self.addstr(' ')
            if contact.ask == 'asked':
                self.addstr('Ask: %s' % (contact.ask,), to_curses_attr(get_theme().COLOR_IMPORTANT_TEXT))
            else:
                self.addstr('Ask: %s' % (contact.ask,))
        self.finish_line()
        if resource:
            self.addstr(2, 0, 'Status: %s' % (resource.status))


    def draw_group_info(self, group):
        """
        draw the group information
        """
        self.addstr(0, 0, group.name, to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)

    def refresh(self, selected_row):
        log.debug('Refresh: %s',self.__class__.__name__)
        with g_lock:
            self._win.erase()
            if isinstance(selected_row, RosterGroup):
                self.draw_group_info(selected_row)
            elif isinstance(selected_row, Contact):
                self.draw_contact_info(selected_row)
            # elif isinstance(selected_row, Resource):
            #     self.draw_contact_info(None, selected_row)
            self._refresh()

class ListWin(Win):
    """
    A list (with no depth, so not for the roster) that can be
    scrolled up and down, with one selected line at a time
    """
    def __init__(self, columns, with_headers=True):
        Win.__init__(self)
        self._columns = columns # a tuple with the name of the columns
        self._columns_sizes = {} # a dict {'column_name': size}
        self.sorted_by = (None, None) # for example: ('name', '↑')
        self.lines = []         # a list of dicts
        self._selected_row = 0
        self._starting_pos = 0  # The column number from which we start the refresh

    def empty(self):
        """
        emtpy the list and reset some important values as well
        """
        self.lines = []
        self._selected_row = 0
        self._starting_pos = 0

    def resize_columns(self, dic):
        """
        Resize the width of the columns
        """
        self._columns_sizes = dic

    def sort_by_column(self, col_name, asc=True):
        """
        Sort the list by the given column, ascendant or descendant
        """
        if not col_name:
            return
        elif asc:
            self.lines.sort(key=lambda x: x[col_name])
        else:
            self.lines.sort(key=lambda x: x[col_name],reverse=True)
        self.refresh()
        curses.doupdate()

    def add_lines(self, lines):
        """
        Append some lines at the end of the list
        """
        if not lines:
            return
        self.lines += lines

    def get_selected_row(self):
        """
        Return the tuple representing the selected row
        """
        if self._selected_row is not None and self.lines:
            return self.lines[self._selected_row]
        return None

    def refresh(self):
        log.debug('Refresh: %s', self.__class__.__name__)
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
                        self.addstr(y, x, txt[:size], to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
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

    def scroll_down(self):
        if not self.lines:
            return
        self._selected_row += self.height
        if self._selected_row > len(self.lines) - 1:
            self._selected_row = len(self.lines) -1
        while self._selected_row >= self._starting_pos + self.height:
            self._starting_pos += self.height // 2
        if self._starting_pos < 0:
            self._starting_pos = 0
        return True

    def scroll_up(self):
        if not self.lines:
            return
        self._selected_row -= self.height + 1
        if self._selected_row < 0:
            self._selected_row = 0
        while self._selected_row < self._starting_pos:
            self._starting_pos -= self.height // 2
        return True

class ColumnHeaderWin(Win):
    """
    A class displaying the column's names
    """
    def __init__(self, columns):
        Win.__init__(self)
        self._columns = columns
        self._columns_sizes = {}
        self._column_sel = ''
        self._column_order = ''
        self._column_order_asc = False

    def resize_columns(self, dic):
        self._columns_sizes = dic

    def get_columns(self):
        return self._columns

    def refresh(self):
        log.debug('Refresh: %s',self.__class__.__name__)
        with g_lock:
            self._win.erase()
            x = 0
            for col in self._columns:
                txt = col
                if col in self._column_order:
                    if self._column_order_asc:
                        txt += get_theme().CHAR_COLUMN_ASC
                    else:
                        txt += get_theme().CHAR_COLUMN_DESC
                #⇓⇑↑↓⇧⇩▲▼
                size = self._columns_sizes[col]
                txt += ' ' * (size-len(txt))
                if col in self._column_sel:
                    self.addstr(0, x, txt, to_curses_attr(get_theme().COLOR_COLUMN_HEADER_SEL))
                else:
                    self.addstr(0, x, txt, to_curses_attr(get_theme().COLOR_COLUMN_HEADER))
                x += size
            self._refresh()

    def sel_column(self,dic):
        self._column_sel = dic

    def get_sel_column(self):
        return self._column_sel

    def set_order(self,order):
        self._column_order = self._column_sel
        self._column_order_asc = order

    def get_order(self):
        if self._column_sel == self._column_order:
            return self._column_order_asc
        else:
            return False

    def sel_column_left(self):
        if self._column_sel in self._columns:
            index = self._columns.index(self._column_sel)
            if index > 1:
                index = index -1
            else:
                index = 0
        else:
            index = 0
        self._column_sel = self._columns[index]
        self.refresh()

    def sel_column_right(self):
        if self._column_sel in self._columns:
            index = self._columns.index(self._column_sel)
            if index < len(self._columns)-2:
                index = index +1
            else:
                index = len(self._columns) -1
        else:
            index = len(self._columns) - 1
        self._column_sel = self._columns[index]
        self.refresh()


class SimpleTextWin(Win):
    def __init__(self, text):
        Win.__init__(self)
        self._text = text
        self.built_lines = []

    def rebuild_text(self):
        """
        Transform the text in lines than can then be
        displayed without any calculation or anything
        at refresh() time
        It is basically called on each resize
        """
        self.built_lines = []
        for line in self._text.split('\n'):
            while len(line) >= self.width:
                limit = line[:self.width].rfind(' ')
                if limit <= 0:
                    limit = self.width
                self.built_lines.append(line[:limit])
                line = line[limit:]
            self.built_lines.append(line)

    def refresh(self):
        log.debug('Refresh: %s',self.__class__.__name__)
        with g_lock:
            self._win.erase()
            for y, line in enumerate(self.built_lines):
                self.addstr_colored(line, y, 0)
            self._refresh()
