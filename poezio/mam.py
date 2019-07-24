#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from poezio.theming import get_theme
from poezio import tabs
from poezio.text_buffer import Message, TextBuffer

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD

def add_line(text_buffer: TextBuffer, text: str, str_time: str, nick: str):
=======
def add_line(text_buffer: TextBuffer, text: str, str_time: str, nick: str, top: bool):
>>>>>>> dcdcc963... Added fuction for infinite scroll, limited number of messages per request to 10.
=======
def add_line(self, text_buffer: TextBuffer, text: str, str_time: str, nick: str, top: bool):
>>>>>>> ef48615c... Added a check for tabs (because there is a different way to query messages for MUC and any other type of tab)
    """Adds a textual entry in the TextBuffer"""

    time = datetime.strftime(str_time, '%Y-%m-%d %H:%M:%S')
    time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
<<<<<<< HEAD
<<<<<<< HEAD
    time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)
    nick = nick.split('/')[1]
    color = get_theme().COLOR_OWN_NICK
=======
    nick = nick.split('/')[1]
    color = get_theme().COLOR_OWN_NICK
=======
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
<<<<<<< HEAD
>>>>>>> e3238d4a... Added messages when the query is starting and ending.
    top = top
>>>>>>> dcdcc963... Added fuction for infinite scroll, limited number of messages per request to 10.
=======
>>>>>>> 0e6ea079... Fixed timestamp
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
    iq = await self.core.xmpp.plugin['xep_0030'].get_info(jid=remote_jid)
    if 'urn:xmpp:mam:2' not in iq['disco_info'].get_features():
        return self.core.information("This MUC doesn't support MAM.", "Error")
    if top:
        if isinstance(self, tabs.MucTab):
            results = self.core.xmpp['xep_0313'].retrieve(jid=self.remote_jid,
            iterator=True, reverse=top, end=self.end_date)
        else:
            results = self.core.xmpp['xep_0313'].retrieve(with_jid=self.remote_jid,
            iterator=True, reverse=top, end=self.end_date)
    else:
        if 'muc' in str(self.remote_jid):
            results = self.core.xmpp['xep_0313'].retrieve(jid=self.remote_jid,
            iterator=True, reverse=top, start=self.start_date, end=self.end_date)
        else:
            results = self.core.xmpp['xep_0313'].retrieve(with_jid=self.remote_jid,
            iterator=True, reverse=top, start=self.start_date, end=self.end_date)

    msg_count = 0
    msgs = []
    timestamp = datetime.now()
    add_line(self, text_buffer, 'Start of MAM query: ', timestamp, 'MAM', top)
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
<<<<<<< HEAD
<<<<<<< HEAD
=======
                add_line(text_buffer, '%s' % message['body'], timestamp, str(message['from']))
                self.tab.core.refresh_window()
>>>>>>> 3de40ea3... Merged changes from mam branchg
                add_line(text_buffer, message['body'], timestamp, str(message['from']), top)
=======
                add_line(self, text_buffer, message['body'], timestamp, str(message['from']), top)
>>>>>>> ef48615c... Added a check for tabs (because there is a different way to query messages for MUC and any other type of tab)
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
<<<<<<< HEAD
<<<<<<< HEAD
    asyncio.ensure_future(MAM(self, remote_jid, start, end, top))
>>>>>>> dcdcc963... Added fuction for infinite scroll, limited number of messages per request to 10.
=======
    asyncio.ensure_future(query(self, remote_jid, start, end, top))
>>>>>>> 96271ed2... Changed the name of MAM function.
=======
    pos = self.text_win.pos
    self.text_win.pos += self.text_win.height - 1
    if self.text_win.pos + self.text_win.height > len(self.text_win.built_lines):
        asyncio.ensure_future(query(self, remote_jid, start, end, top))
        self.query_id = 1
        self.text_win.pos = len(self.text_win.built_lines) - self.text_win.height
        if self.text_win.pos < 0:
            self.text_win.pos = 0
    return self.text_win.pos != pos
>>>>>>> 1e61af98... Fixed scroll up
