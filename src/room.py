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

from datetime import datetime
from random import randrange
from config import config
from logging import logger
from message import Message

class Room(object):
    """
    """
    number = 0
    def __init__(self, name, nick, window):
        self.name = name
        self.own_nick = nick
        self.color_state = 11   # color used in RoomInfo
        self.nb = Room.number        # number used in RoomInfo
        Room.number += 1
        self.joined = False     # false until self presence is received
        self.users = []         # User objects
        self.messages = []         # Message objects
        self.topic = ''
        self.window = window
        self.pos = 0            # offset

    def scroll_up(self, y_x):
        y, x = y_x
        if len(self.messages) <= y:
            return
        self.pos += 14
        from common import debug
        debug(str(y_x))
        if self.pos + y >= len(self.messages):
            self.pos = len(self.messages) - y+3

    def scroll_down(self):
        self.pos -= 14
        if self.pos <= 0:
            self.pos = 0

    def disconnect(self):
        self.joined = False

    def add_message(self, txt, time=None, nickname=None):
        """
        Note that user can be None even if nickname is not None. It happens
        when we receive an history message said by someone who is not
        in the room anymore
        """
        user = self.get_user_by_name(nickname) if nickname is not None else None
        time = time if time is not None else datetime.now()
        color = None
        if nickname is not None:
            self.set_color_state(12)
        else:
            color = 8
        if nickname != self.own_nick and self.joined and nickname is not None: # do the highlight
            try:
                if self.own_nick.encode('utf-8') in txt:
                    self.set_color_state(13)
                    color = 3
            except UnicodeDecodeError:
                try:
                    if self.own_nick in txt:
                        self.set_color_state(13)
                        color = 3
                except:
                    pass
            else:
                highlight_words = config.get('highlight_on', '').split(':')
                for word in highlight_words:
                    if word.lower() in txt.lower() and word != '':
                        self.set_color_state(13)
                        color = 3
                        break
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
        if self.color_state < color or color == 11:
            self.color_state = color
