#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

from datetime import datetime, timezone
from poezio.theming import get_theme
from poezio.text_buffer import Message, TextBuffer

async def MAM(self, remote_jid, start, end):
    self.remote_jid = remote_jid
    self.start_date = start
    self.end_date = end
    text_buffer = self._text_buffer
    results = self.core.xmpp.plugin['xep_0313'].retrieve(jid=self.remote_jid,
    iterator=True, start=self.start_date, end=self.end_date)
    async for rsm in results:
        for msg in rsm['mam']['results']:
            forwarded = msg['mam_result']['forwarded']
            timestamp = forwarded['delay']['stamp']
            message = forwarded['stanza']
            text = str(message['body'])
            time = datetime.strftime(timestamp, '%Y-%m-%d %H:%M:%S')
            time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
            time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)
            nick = str(message['from']).split('/')[1]
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
            self.core.refresh_window()
