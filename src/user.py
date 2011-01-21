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

"""
Define the user class.
An user is a MUC participant, not a roster contact (see contact.py)
"""

from random import randrange, choice
from config import config
from datetime import timedelta, datetime
import curses
import theme

ROLE_DICT = {
    'none':0,
    'visitor':1,
    'participant':2,
    'moderator':3
    }

class User(object):
    """
    keep trace of an user in a Room
    """
    def __init__(self, nick, affiliation, show, status, role, jid):
        self.last_talked = datetime(1, 1, 1) # The oldest possible time
        self.update(affiliation, show, status, role)
        self.change_nick(nick)
        self.color = choice(theme.LIST_COLOR_NICKNAMES)
        self.jid = jid

    def update(self, affiliation, show, status, role):
        self.affiliation = affiliation
        self.show = show
        self.status = status
        self.role = role

    def change_nick(self, nick):
        self.nick = nick

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
        return ">%s<" % (self.nick)

    def __eq__(self, b):
        return self.role == b.role and self.nick.lower() == b.nick.lower()

    def __gt__(self, b):
        if ROLE_DICT[self.role] == ROLE_DICT[b.role]:
            return self.nick.lower() > b.nick.lower()
        return ROLE_DICT[self.role] < ROLE_DICT[b.role]

    def __ge__(self, b):
        if ROLE_DICT[self.role] == ROLE_DICT[b.role]:
            return self.nick.lower() >= b.nick.lower()
        return ROLE_DICT[self.role] <= ROLE_DICT[b.role]

    def __lt__(self, b):
        if ROLE_DICT[self.role] == ROLE_DICT[b.role]:
            return self.nick.lower() < b.nick.lower()
        return ROLE_DICT[self.role] > ROLE_DICT[b.role]

    def __le__(self, b):
        if ROLE_DICT[self.role] == ROLE_DICT[b.role]:
            return self.nick.lower() <= b.nick.lower()
        return ROLE_DICT[self.role] >= ROLE_DICT[b.role]
