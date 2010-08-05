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

from random import randrange
from config import config
from datetime import timedelta, datetime
import curses

class User(object):
    """
    keep trace of an user in a Room
    """
    def __init__(self, nick, affiliation, show, status, role):
        self.last_talked = None
        self.update(affiliation, show, status, role)
        self.change_nick(nick)
        self.color = randrange(3, 10) # assign a random color

    def update(self, affiliation, show, status, role):
        self.affiliation = affiliation
        self.show = show
        self.status = status
        self.role = role

    def change_nick(self, nick):
        self.nick = nick.encode('utf-8')

    def set_last_talked(self, time):
        """
        time: datetime object
        """
        self.last_talked = time

    def has_talked_since(self, t):
        """
        t: int
        Return True if the user talked since the last s seconds
        """
        if self.last_talked is None:
            return False
        delta = timedelta(0, t)
        if datetime.now() - delta > self.last_talked:
            return False
        return True

    def __repr__(self):
        return "<user.User object nick:%s show:%s(%s) status:%s affiliation:%s>"\
            % (self.nick, self.show, type(self.show), self.status, self.affiliation)
