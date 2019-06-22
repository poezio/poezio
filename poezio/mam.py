#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

from getpass import getpass
from argparse import ArgumentParser

import slixmpp
from datetime import datetime, timezone
from poezio.theming import get_theme
from slixmpp.exceptions import XMPPError
from poezio.text_buffer import Message, TextBuffer


def add_line(text_buffer: TextBuffer, text: str, str_time: str, nick: str):
    """Adds a textual entry in the TextBuffer"""

    time = datetime.strftime(str_time, '%Y-%m-%d %H:%M:%S')
    time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
    time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)
    nick = nick.split('/')[1]
    color = get_theme().COLOR_OWN_NICK
    text_buffer.add_message(
        text,
        time,
        nick,
        color,
        True,  # History
        None,  # User
        False,  # Highlight
        None,  # Identifier
        None,  # str_time
        None,  # Jid
    )


class MAM(slixmpp.ClientXMPP):
    """
    A basic client fetching mam archive messages
    """

    def __init__(self, jid, password, remote_jid, start, end, tab):
        slixmpp.ClientXMPP.__init__(self, jid, password)
        self.remote_jid = remote_jid
        self.start_date = start
        self.end_date = end
        self.tab = tab

        self.add_event_handler("session_start", self.start)

    async def start(self, *args):
        """
        Fetches mam results for the specified JID.
        """

        text_buffer = self.tab._text_buffer

        results = self.plugin['xep_0313'].retrieve(jid=self.remote_jid,
        iterator=True, start=self.start_date, end=self.end_date)
        async for rsm in results:
            for msg in rsm['mam']['results']:
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                add_line(text_buffer, '%s' % message['body'], timestamp, str(message['from']))

        self.tab.text_win.pos = 0
        self.tab.core.refresh_window()
        self.disconnect()
