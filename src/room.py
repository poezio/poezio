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

class Room(object):
    """
    """
    def __init__(self, name, nick, number):
        self.name = name
        self.own_nick = nick
        self.color_state = 11   # color used in RoomInfo
        self.nb = number       # number used in RoomInfo
        self.joined = False     # false until self presence is received
        self.users = []
        self.lines = []         # (time, nick, msg) or (time, info)
        self.topic = ''

    def disconnect(self):
        self.joined = False

    def add_message(self, nick, msg, date=None):
        if not date:
            date = datetime.now()
        color = None
        self.set_color_state(12)
        if nick != self.own_nick and self.joined: # do the highlight thing
            if self.own_nick in msg:
                self.set_color_state(13)
                color = 3
            else:
                highlight_words = config.get('highlight_on', '').split(':')
                for word in highlight_words:
                    if word.lower() in msg.lower() and word != '':
                        self.set_color_state(13)
                        color = 3
                        break
        if not msg:
            logger.info('msg is None..., %s' % (nick))
            return
        self.lines.append((date, nick.encode('utf-8'),
                          msg.encode('utf-8'), color))
        user = self.get_user_by_name(nick)
        if user:
            user.set_last_talked(date)
        if self.joined:         # log only NEW messages, not the history received on join
            logger.message(self.name, nick.encode('utf-8'), msg.encode('utf-8'))
        return color

    def add_info(self, info, date=None):
        """ info, like join/quit/status messages"""
        if not date:
            date = datetime.now()
        try:
            self.lines.append((date, info.encode('utf-8')))
            return info.encode('utf-8')
        except:
            self.lines.append((date, info))
            return info

    def get_user_by_name(self, nick):
        for user in self.users:
            if user.nick == nick.encode('utf-8'):
                return user
        return None

    def set_color_state(self, color):
        if self.color_state < color or color == 11:
            self.color_state = color
