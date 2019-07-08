#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from poezio.theming import get_theme
from poezio.text_buffer import Message, TextBuffer

<<<<<<< HEAD
<<<<<<< HEAD

def add_line(text_buffer: TextBuffer, text: str, str_time: str, nick: str):
=======
def add_line(text_buffer: TextBuffer, text: str, str_time: str, nick: str, top: bool):
>>>>>>> dcdcc963... Added fuction for infinite scroll, limited number of messages per request to 10.
    """Adds a textual entry in the TextBuffer"""

    time = datetime.strftime(str_time, '%Y-%m-%d %H:%M:%S')
    time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
<<<<<<< HEAD
    time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)
    nick = nick.split('/')[1]
    color = get_theme().COLOR_OWN_NICK
=======
    nick = nick.split('/')[1]
    color = get_theme().COLOR_OWN_NICK
    top = top
>>>>>>> dcdcc963... Added fuction for infinite scroll, limited number of messages per request to 10.
    text_buffer.add_message(
        text,
        time,
        nick,
        color,
        True,  # History
        None,  # User
        False,  # Highlight
<<<<<<< HEAD
=======
        top, #Top
>>>>>>> dcdcc963... Added fuction for infinite scroll, limited number of messages per request to 10.
        None,  # Identifier
        None,  # str_time
        None,  # Jid
    )

<<<<<<< HEAD
<<<<<<< HEAD

class MAM:
    """
    A basic client fetching mam archive messages
    """

    def __init__(self, remote_jid, start, end, tab):
        self.remote_jid = remote_jid
        self.start_date = start
        self.end_date = end
        self.tab = tab
        asyncio.ensure_future(self.start())

    async def start(self):
        text_buffer = self.tab._text_buffer
        results = self.tab.core.xmpp.plugin['xep_0313'].retrieve(jid=self.remote_jid,
        iterator=True, start=self.start_date, end=self.end_date)
        async for rsm in results:
            for msg in rsm['mam']['results']:
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                add_line(text_buffer, '%s' % message['body'], timestamp, str(message['from']))
                self.tab.core.refresh_window()

        self.tab.text_win.pos = 0
        self.tab.core.refresh_window()
=======
async def MAM(self, remote_jid, start, end):
=======
async def MAM(self, remote_jid, start, end, top):
>>>>>>> dcdcc963... Added fuction for infinite scroll, limited number of messages per request to 10.
=======
async def query(self, remote_jid, start, end, top):
>>>>>>> 96271ed2... Changed the name of MAM function.
    self.remote_jid = remote_jid
    self.start_date = start
    self.end_date = end
    text_buffer = self._text_buffer
    results = self.core.xmpp['xep_0313'].retrieve(jid=self.remote_jid,
    iterator=True, reverse=top, start=self.start_date, end=self.end_date)
    msg_count = 0
    msgs = []
    async for rsm in results:
<<<<<<< HEAD
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
>>>>>>> 208c814d... Removed MAM class and changed it into function.
=======
        if top:
            for msg in rsm['mam']['results']:
                msgs.append(msg)
                if msg_count == 10:
                    return
                msg_count += 1
            msgs.reverse()
            for msg in msgs:
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                add_line(text_buffer, message['body'], timestamp, str(message['from']), top)
                self.text_win.scroll_up(len(self.text_win.built_lines))
                self.core.refresh_window()
        else:
            for msg in rsm['mam']['results']:
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                add_line(text_buffer, message['body'], timestamp, str(message['from']), top)
                self.core.refresh_window()


def mam_scroll(self):
    remote_jid = self.jid
    text_buffer = self._text_buffer
    end = datetime.now()
    for message in text_buffer.messages:
        time = message.time
        if time < end:
            end = time
    end = end + timedelta(seconds=-1)
    end = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')
    start = datetime.strptime(end, '%Y-%m-%dT%H:%M:%SZ')
    start = start + timedelta(days=-10)
    start = datetime.strftime(start, '%Y-%m-%dT%H:%M:%SZ')
    top = True
<<<<<<< HEAD
    asyncio.ensure_future(MAM(self, remote_jid, start, end, top))
>>>>>>> dcdcc963... Added fuction for infinite scroll, limited number of messages per request to 10.
=======
    asyncio.ensure_future(query(self, remote_jid, start, end, top))
>>>>>>> 96271ed2... Changed the name of MAM function.
