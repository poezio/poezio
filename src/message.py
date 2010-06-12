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

from common import debug
from datetime import datetime

class Message(object):
    """
    A message with all the associated data (nickname, time, color, etc)
    """
    def __init__(self, txt, time=None, nickname=None, user=None, color=None):
        """
        time is a datetime object, None means 'now'.
        If no nickname is specified, it's an information.
        user is an User object (used for the color, etc)
        """
        self.txt = txt
        self.nickname = nickname
        self.time = time
        self.user = user
        self.color = color

    def __repr__(self):
        return "<Message txt=%s, nickname=%s, time=%s, user=%s>" % (self.txt, self.nickname, str(self.time), str(self.user))
    def __str__(self):
        return self.__repr__()

