# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Define the user class.
An user is a MUC participant, not a roster contact (see contact.py)
"""

from random import choice
from datetime import timedelta, datetime
from hashlib import md5
from poezio import xhtml

from poezio.theming import get_theme

import logging
log = logging.getLogger(__name__)

ROLE_DICT = {
    '':0,
    'none':0,
    'visitor':1,
    'participant':2,
    'moderator':3
    }

class User(object):
    """
    keep trace of an user in a Room
    """
    __slots__ = ('last_talked', 'jid', 'chatstate', 'affiliation', 'show', 'status', 'role', 'nick', 'color')

    def __init__(self, nick, affiliation, show, status, role, jid, deterministic=True, color=''):
        self.last_talked = datetime(1, 1, 1) # The oldest possible time
        self.update(affiliation, show, status, role)
        self.change_nick(nick)
        if color != '':
            self.change_color(color, deterministic)
        else:
            if deterministic:
                self.set_deterministic_color()
            else:
                self.color = choice(get_theme().LIST_COLOR_NICKNAMES)
        self.jid = jid
        self.chatstate = None

    def set_deterministic_color(self):
        theme = get_theme()
        mod = len(theme.LIST_COLOR_NICKNAMES)
        nick_pos = int(md5(self.nick.encode('utf-8')).hexdigest(), 16) % mod
        self.color = theme.LIST_COLOR_NICKNAMES[nick_pos]

    def update(self, affiliation, show, status, role):
        self.affiliation = affiliation
        self.show = show
        self.status = status
        if role not in ROLE_DICT: # avoid unvalid roles
            role = ''
        self.role = role

    def change_nick(self, nick):
        self.nick = nick

    def change_color(self, color_name, deterministic=False):
        color = xhtml.colors.get(color_name)
        if color == None:
            log.error('Unknown color "%s"' % color_name)
            if deterministic:
                self.set_deterministic_color()
            else:
                self.color = choice(get_theme().LIST_COLOR_NICKNAMES)
        else:
            self.color = (color, -1)

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
        return self.role == b.role and self.nick == b.nick

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
