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

import logging
from datetime import timedelta, datetime
from hashlib import md5
from random import choice
from typing import Optional, Tuple

from poezio import xhtml, colors
from poezio.theming import get_theme
from slixmpp import JID

log = logging.getLogger(__name__)

ROLE_DICT = {'': 0, 'none': 0, 'visitor': 1, 'participant': 2, 'moderator': 3}


class User:
    """
    keep trace of an user in a Room
    """
    __slots__ = ('last_talked', 'jid', 'chatstate', 'affiliation', 'show',
                 'status', 'role', 'nick', 'color')

    def __init__(self,
                 nick: str,
                 affiliation: str,
                 show: str,
                 status: str,
                 role: str,
                 jid: JID,
                 deterministic=True,
                 color=''):
        # The oldest possible time
        self.last_talked = datetime(1, 1, 1)  # type: datetime
        self.update(affiliation, show, status, role)
        self.change_nick(nick)
        self.jid = jid  # type: JID
        self.chatstate = None  # type: Optional[str]
        self.color = (1, 1)  # type: Tuple[int, int]
        if color != '':
            self.change_color(color, deterministic)
        else:
            if deterministic:
                self.set_deterministic_color()
            else:
                self.color = choice(get_theme().LIST_COLOR_NICKNAMES)

    def set_deterministic_color(self):
        theme = get_theme()
        if theme.ccg_palette:
            # use XEP-0392 CCG
            fg_color = colors.ccg_text_to_color(theme.ccg_palette, self.nick)
            self.color = fg_color, -1
        else:
            mod = len(theme.LIST_COLOR_NICKNAMES)
            nick_pos = int(md5(self.nick.encode('utf-8')).hexdigest(),
                           16) % mod
            self.color = theme.LIST_COLOR_NICKNAMES[nick_pos]

    def update(self, affiliation: str, show: str, status: str, role: str):
        self.affiliation = affiliation
        self.show = show
        self.status = status
        if role not in ROLE_DICT:  # avoid invalid roles
            role = ''
        self.role = role

    def change_nick(self, nick: str):
        self.nick = nick

    def change_color(self, color_name: Optional[str], deterministic=False):
        color = xhtml.colors.get(color_name)
        if color is None:
            log.error('Unknown color "%s"', color_name)
            if deterministic:
                self.set_deterministic_color()
            else:
                self.color = choice(get_theme().LIST_COLOR_NICKNAMES)
        else:
            self.color = (color, -1)

    def set_last_talked(self, time: datetime):
        """
        time: datetime object
        """
        self.last_talked = time

    def has_talked_since(self, t: int) -> bool:
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

    def __repr__(self) -> str:
        return ">%s<" % (self.nick)

    def __eq__(self, b) -> bool:
        return self.role == b.role and self.nick == b.nick

    def __gt__(self, b) -> bool:
        if ROLE_DICT[self.role] == ROLE_DICT[b.role]:
            return self.nick.lower() > b.nick.lower()
        return ROLE_DICT[self.role] < ROLE_DICT[b.role]

    def __ge__(self, b) -> bool:
        if ROLE_DICT[self.role] == ROLE_DICT[b.role]:
            return self.nick.lower() >= b.nick.lower()
        return ROLE_DICT[self.role] <= ROLE_DICT[b.role]

    def __lt__(self, b) -> bool:
        if ROLE_DICT[self.role] == ROLE_DICT[b.role]:
            return self.nick.lower() < b.nick.lower()
        return ROLE_DICT[self.role] > ROLE_DICT[b.role]

    def __le__(self, b) -> bool:
        if ROLE_DICT[self.role] == ROLE_DICT[b.role]:
            return self.nick.lower() <= b.nick.lower()
        return ROLE_DICT[self.role] >= ROLE_DICT[b.role]
