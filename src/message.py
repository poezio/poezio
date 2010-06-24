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

class Line(object):
    """
    A line, corresponding to ONE row of the text area.
    A message is composed of ONE line or MORE.
    Example:

  Text area limit                                     text area limit
    v                                                     v
    |[12:12:01] nickone has just joined the room named    |
    |           test@kikoo.louiz.org                      |
    |[12:12:23] nickone> hello good morning everyone, I am|
    |                    seeking for informations about   |
    |                    poezio                           |
    |[12:12:35] secondnick> Hello nickone, you can get    |
    |                       informations here :\n         |
    |                       http://blablablabla           |

    To get this result, the three messages should be converted to:

    Line(None, None, Datetime(12, 12, 01), "nickone has just joined the room named", 0, 10)
    Line(None, None, None, "test@kikoo.louiz.org", 0, 10)
    Line("nickone", 1, Datetime(12, 12, 23), "hello good morning everyone, I am", 0, 20)
    Line(None, None, None, "seeking for informations about", 0, 20)
    Line(None, None, None, "poezio", 0, 20)
    Line("secondnick", 2, Datetime(12, 12, 35), "Hello nickone, you can get", 0, 23)
    Line(None, None, None, "informations here:", 0, 23)
    Line(None, None, None, "http://blablablabla", 0, 23)
    """
    def __init__(self, nickname, nickname_color, time, text, text_color, text_offset):
        self.nickname = nickname
        self.nickname_color = nickname_color
        self.time = time
        self.text = text
        self.text_color = text_color
        self.text_offset = text_offset
