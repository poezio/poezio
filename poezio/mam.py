#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from slixmpp.exceptions import IqError, IqTimeout
from poezio.theming import get_theme
from poezio import tabs
from poezio.text_buffer import Message, TextBuffer

def add_line(self, text_buffer: TextBuffer, text: str, str_time: str, nick: str, top: bool):
    """Adds a textual entry in the TextBuffer"""

    time = datetime.strftime(str_time, '%Y-%m-%d %H:%M:%S')
    time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
    if '/' in nick:
        if isinstance(self, tabs.MucTab):
            nick = nick.split('/')[1]
        else:
            nick = nick.split('/')[0]
        color = get_theme().COLOR_OWN_NICK
        time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)
        time = time.replace(tzinfo=None)
    else:
        color = get_theme().COLOR_ME_MESSAGE
    text_buffer.add_message(
        text,
        time,
        nick,
        color,
        True,  # History
        None,  # User
        False,  # Highlight
        top, #Top
        None,  # Identifier
        None,  # str_time
        None,  # Jid
    )

async def query(self, remote_jid, start, end, top):
    self.remote_jid = remote_jid
    self.start_date = start
    self.end_date = end
    text_buffer = self._text_buffer
    try:
        iq = await self.core.xmpp.plugin['xep_0030'].get_info(jid=remote_jid)
    except (IqError, IqTimeout):
        return self.information('Failed to retrieve messages', 'Error')
    if 'urn:xmpp:mam:2' not in iq['disco_info'].get_features():
        return self.core.information("This MUC doesn't support MAM.", "Error")
    if top:
        if isinstance(self, tabs.MucTab):
            try:
                results = self.core.xmpp['xep_0313'].retrieve(jid=self.remote_jid,
                iterator=True, reverse=top, end=self.end_date)
            except (IqError, IqTimeout):
                return self.information('Failed to retrieve messages', 'Error')
        else:
            try:
                results = self.core.xmpp['xep_0313'].retrieve(with_jid=self.remote_jid,
                iterator=True, reverse=top, end=self.end_date)
            except (IqError, IqTimeout):
                return self.information('Failed to retrieve messages', 'Error')
    else:
        if isinstance(self, tabs.MucTab):
            try:
                results = self.core.xmpp['xep_0313'].retrieve(jid=self.remote_jid,
                iterator=True, reverse=top, start=self.start_date, end=self.end_date)
            except (IqError, IqTimeout):
                return self.information('Failed to retrieve messages', 'Error')
        else:
            try:
                results = self.core.xmpp['xep_0313'].retrieve(with_jid=self.remote_jid,
                iterator=True, reverse=top, start=self.start_date, end=self.end_date)
            except (IqError, IqTimeout):
                return self.information('Failed to retrieve messages', 'Error')
    msg_count = 0
    msgs = []
    timestamp = datetime.now()
    add_line(self, text_buffer, 'Start of MAM query: ', timestamp, 'MAM', top)
    async for rsm in results:
        if top:
            for msg in rsm['mam']['results']:
                if msg['mam_result']['forwarded']['stanza']['body'] is not '':
                    msgs.append(msg)
                if msg_count == 10:
                    self.query_id = 0
                    timestamp = datetime.now()
                    add_line(self, text_buffer, 'End of MAM query: ', timestamp, 'MAM', top)
                    self.core.refresh_window()
                    return
                msg_count += 1
            msgs.reverse()
            for msg in msgs:
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                add_line(self, text_buffer, message['body'], timestamp, str(message['from']), top)
                self.text_win.scroll_up(len(self.text_win.built_lines))
        else:
            for msg in rsm['mam']['results']:
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                add_line(self, text_buffer, message['body'], timestamp, str(message['from']), top)
                self.core.refresh_window()
    self.query_id = 0
    timestamp = datetime.now()
    add_line(self, text_buffer, 'End of MAM query: ', timestamp, 'MAM', top)


def mam_scroll(self):
    remote_jid = self.jid
    text_buffer = self._text_buffer
    end = datetime.now()
    for message in text_buffer.messages:
        time = message.time
        if time < end:
            end = time
    end = end + timedelta(seconds=-1)
    tzone = datetime.now().astimezone().tzinfo
    end = end.replace(tzinfo=tzone).astimezone(tz=timezone.utc)
    end = end.replace(tzinfo=None)
    end = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')
    start = False
    top = True
    pos = self.text_win.pos
    self.text_win.pos += self.text_win.height - 1
    if self.text_win.pos + self.text_win.height > len(self.text_win.built_lines):
        asyncio.ensure_future(query(self, remote_jid, start, end, top))
        self.query_id = 1
        self.text_win.pos = len(self.text_win.built_lines) - self.text_win.height
        if self.text_win.pos < 0:
            self.text_win.pos = 0
    return self.text_win.pos != pos
