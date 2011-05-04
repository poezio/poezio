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

from text_buffer import TextBuffer, Message
from datetime import datetime
from random import randrange
from config import config
from logger import logger

import common
import theme

import logging

log = logging.getLogger(__name__)

class Room(TextBuffer):
    def __init__(self, name, nick, messages_nb_limit=config.get('max_messages_in_memory', 2048)):
        TextBuffer.__init__(self, messages_nb_limit)
        self.name = name
        self.own_nick = nick
        self.color_state = theme.COLOR_TAB_NORMAL   # color used in RoomInfo
        self.joined = False     # false until self presence is receied
        self.users = []         # User objects
        self.topic = ''

    def disconnect(self):
        """
        Set the state of the room as not joined, so
        we can know if we can join it, send messages to it, etc
        """
        self.users = []
        self.joined = False

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
        color = None
        if not time and nickname and nickname != self.own_nick and self.joined:
            if self.own_nick.lower() in txt.lower():
                if self.color_state != theme.COLOR_TAB_CURRENT:
                    self.set_color_state(theme.COLOR_TAB_HIGHLIGHT)
                color = theme.COLOR_HIGHLIGHT_NICK
            else:
                highlight_words = config.get('highlight_on', '').split(':')
                for word in highlight_words:
                    if word and word.lower() in txt.lower():
                        if self.color_state != theme.COLOR_TAB_CURRENT:
                            self.set_color_state(theme.COLOR_TAB_HIGHLIGHT)
                        color = theme.COLOR_HIGHLIGHT_NICK
                        break
        return color

    def get_user_by_name(self, nick):
        for user in self.users:
            if user.nick == nick:
                return user
        return None

    def set_color_state(self, color):
        """
        Set the color that will be used to display the room's
        number in the RoomInfo window
        """
        self.color_state = color

    def add_message(self, txt, time=None, nickname=None, forced_user=None, nick_color=None):
        """
        Note that user can be None even if nickname is not None. It happens
        when we receive an history message said by someone who is not
        in the room anymore
        """
        self.log_message(txt, time, nickname)
        if txt.startswith('/me '):
            txt = "\x192* \x195" + nickname + ' ' + txt[4:]
            nickname = None
        user = self.get_user_by_name(nickname) if nickname is not None else None
        if user:
            user.set_last_talked(datetime.now())
        if not user and forced_user:
            user = forced_user
        if not time and nickname and\
                nickname != self.own_nick and\
                self.color_state != theme.COLOR_TAB_CURRENT:
            if self.color_state != theme.COLOR_TAB_HIGHLIGHT:
                self.set_color_state(theme.COLOR_TAB_NEW_MESSAGE)
        nick_color = nick_color or None
        if not nickname or time:
            txt = '\x195%s' % (txt,)
        else:                   # TODO
            highlight = self.do_highlight(txt, time, nickname)
            if highlight:
                nick_color = highlight
        time = time or datetime.now()
        message = Message(txt='%s\x19o'%(txt,), nick_color=nick_color,
                          time=time, nickname=nickname, user=user)
        while len(self.messages) > self.messages_nb_limit:
            self.messages.pop(0)
        self.messages.append(message)
        for window in self.windows: # make the associated windows
            # build the lines from the new message
            nb = window.build_new_message(message)
            if window.pos != 0:
                window.scroll_up(nb)
        return nb
