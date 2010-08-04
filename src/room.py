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

from datetime import datetime
from random import randrange
from config import config
from logging import logger
from message import Message

import common

class Room(object):
    """
    """
    number = 0
    def __init__(self, name, nick, window, jid=None):
        self.jid = jid          # used for a private chat. None if it's a MUC
        self.name = name
        self.own_nick = nick
        self.color_state = common.ROOM_STATE_NONE   # color used in RoomInfo
        self.nb = Room.number        # number used in RoomInfo
        Room.number += 1
        self.joined = False     # false until self presence is received
        self.users = []         # User objects
        self.messages = []         # Message objects
        self.topic = ''
        self.window = window
        self.pos = 0            # offset

    def scroll_up(self, dist=14):
        # The pos can grow a lot over the top of the number of
        # available lines, it will be fixed on the next refresh of the
        # screen anyway
        self.pos += dist

    def scroll_down(self, dist=14):
        self.pos -= dist
        if self.pos <= 0:
            self.pos = 0

    def disconnect(self):
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
        color = None
        if not time and nickname != self.own_nick and self.joined and nickname is not None: # do the highlight
            try:
                if self.own_nick.encode('utf-8') in txt:
                    self.set_color_state(13)
                    color = 2
            except UnicodeDecodeError:
                try:
                    if self.own_nick in txt:
                        self.set_color_state(13)
                        color = 2
                except:
                    pass
            else:
                highlight_words = config.get('highlight_on', '').split(':')
                for word in highlight_words:
                    if word.lower() in txt.lower() and word != '':
                        self.set_color_state(common.ROOM_STATE_HL)
                        color = 2
                        break
        return color

    def add_message(self, txt, time=None, nickname=None):
        """
        Note that user can be None even if nickname is not None. It happens
        when we receive an history message said by someone who is not
        in the room anymore
        """
        self.log_message(txt, time, nickname)
        user = self.get_user_by_name(nickname) if nickname is not None else None
        if user:
            user.set_last_talked(datetime.now())
        color = None
        if not time and nickname is not None and\
                nickname != self.own_nick and\
                self.color_state != common.ROOM_STATE_CURRENT:
            if not self.jid:
                self.set_color_state(common.ROOM_STATE_MESSAGE)
            else:
                self.set_color_state(common.ROOM_STATE_PRIVATE)
        color = self.do_highlight(txt, time, nickname)
        if time:                # History messages are colored to be distinguished
            color = 8
        time = time if time is not None else datetime.now()
        self.messages.append(Message(txt, time, nickname, user, color))

    def get_user_by_name(self, nick):
        for user in self.users:
            if user.nick == nick.encode('utf-8'):
                return user
        return None

    def set_color_state(self, color):
        """
        Set the color that will be used to display the room's
        number in the RoomInfo window
        """
        self.color_state = color
