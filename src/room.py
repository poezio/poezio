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

from text_buffer import TextBuffer
from datetime import datetime
from random import randrange
from config import config
from logger import logger
from message import Message

import common
import theme

class Room(TextBuffer):
    """
    """
    def __init__(self, name, nick):
        TextBuffer.__init__(self)
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
        self.joined = False

    def log_message(self, txt, time, nickname):
        """
        Log the messages in the archives, if it needs
        to be
        """
        if time == None and self.joined:        # don't log the history messages
            logger.message(self.name, nickname, txt)

    def do_highlight(self, txt, time, nickname):
        """
        Set the tab color and returns the txt color
        """
        color = theme.COLOR_NORMAL_TEXT
        if not time and nickname and nickname != self.own_nick and self.joined: # do the highlight
            try:
                if self.own_nick in txt:
                    self.set_color_state(theme.COLOR_TAB_HIGHLIGHT)
                    color = theme.COLOR_HIGHLIGHT_TEXT
            except UnicodeDecodeError:
                try:
                    if self.own_nick in txt:
                        self.set_color_state(theme.COLOR_TAB_HIGHLIGHT)
                        color = theme.COLOR_HIGHLIGHT_TEXT
                except:
                    pass
            else:
                highlight_words = config.get('highlight_on', '').split(':')
                for word in highlight_words:
                    if word.lower() in txt.lower() and word != '':
                        self.set_color_state(theme.COLOR_TAB_HIGHLIGHT)
                        color = theme.COLOR_HIGHLIGHT_TEXT
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

    def add_message(self, txt, time=None, nickname=None, colorized=False):
        """
        Note that user can be None even if nickname is not None. It happens
        when we receive an history message said by someone who is not
        in the room anymore
        """
        self.log_message(txt, time, nickname)
        if txt.startswith('/me '):
            txt = "* " + nickname + ' ' + txt[4:]
            nickname = None
        user = self.get_user_by_name(nickname) if nickname is not None else None
        if user:
            user.set_last_talked(datetime.now())
        color = theme.COLOR_NORMAL_TEXT
        if not time and nickname and\
                nickname != self.own_nick and\
                self.color_state != theme.COLOR_TAB_CURRENT:
            if self.color_state != theme.COLOR_TAB_HIGHLIGHT:
                self.set_color_state(theme.COLOR_TAB_NEW_MESSAGE)
            # elif self.jid:
            #     self.set_color_state(theme.COLOR_TAB_PRIVATE)
        if not nickname:
            color = theme.COLOR_INFORMATION_TEXT
        else:
            color = self.do_highlight(txt, time, nickname)
        if time:                # History messages are colored to be distinguished
            color = theme.COLOR_INFORMATION_TEXT
        time = time if time is not None else datetime.now()
        if self.pos:            # avoid scrolling of one line when one line is received
            self.pos += 1
        self.messages.append(Message(txt, time, nickname, user, color, colorized))
