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

def add_line(text_buffer: TextBuffer, text: str, str_time: str, nick: str, top: bool):
    """Adds a textual entry in the TextBuffer"""

    time = datetime.strftime(str_time, '%Y-%m-%d %H:%M:%S')
    time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
    time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)
    time = time.replace(tzinfo=None)
    if nick is 'MAM':
        color = get_theme().COLOR_ME_MESSAGE
    else:
        color = get_theme().COLOR_OWN_NICK
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

async def query(tab, remote_jid, top, start=None, end=None, before=None):
    tab.remote_jid = remote_jid
    tab.start_date = start
    tab.end_date = end
    text_buffer = tab._text_buffer
    try:
        iq = await tab.core.xmpp.plugin['xep_0030'].get_info(jid=remote_jid)
    except (IqError, IqTimeout):
        return tab.information('Failed to retrieve messages', 'Error')
    if 'urn:xmpp:mam:2' not in iq['disco_info'].get_features():
        return tab.core.information("This MUC doesn't support MAM.", "Error")
    if top:
        if isinstance(tab, tabs.MucTab):
            try:
                if before:
                    results = tab.core.xmpp['xep_0313'].retrieve(jid=tab.remote_jid,
                    iterator=True, reverse=top, before=before)
                else:
                    results = tab.core.xmpp['xep_0313'].retrieve(jid=tab.remote_jid,
                    iterator=True, reverse=top, end=tab.end_date)
            except (IqError, IqTimeout):
                return tab.core.information('Failed to retrieve messages', 'Error')
        else:
            try:
                if before:
                    results = tab.core.xmpp['xep_0313'].retrieve(with_jid=tab.remote_jid,
                    iterator=True, reverse=top, before=before)
                else:
                    results = tab.core.xmpp['xep_0313'].retrieve(with_jid=tab.remote_jid,
                    iterator=True, reverse=top, end=tab.end_date)
            except (IqError, IqTimeout):
                return tab.core.information('Failed to retrieve messages', 'Error')
    else:
        if 'conference' in list(iq['disco_info']['identities'])[0]:
            try:
                results = tab.core.xmpp['xep_0313'].retrieve(jid=tab.remote_jid,
                iterator=True, reverse=top, start=tab.start_date, end=tab.end_date)
            except (IqError, IqTimeout):
                return tab.core.information('Failed to retrieve messages', 'Error')
        else:
            try:
                results = tab.core.xmpp['xep_0313'].retrieve(with_jid=tab.remote_jid,
                iterator=True, reverse=top, start=tab.start_date, end=tab.end_date)
            except (IqError, IqTimeout):
                return tab.core.information('Failed to retrieve messages', 'Error')
    msg_count = 0
    msgs = []
    async for rsm in results:
        if top:
            for msg in rsm['mam']['results']:
                if msg['mam_result']['forwarded']['stanza'].xml.find(
                    '{%s}%s' % ('jabber:client', 'body')) is not None:
                    msgs.append(msg)
                if msg_count == 10:
                    tab.query_id = 0
                    tab.core.refresh_window()
                    return
                msg_count += 1
            msgs.reverse()
            for msg in msgs:
                if msg is msgs[0]:
                    timestamp = msg['mam_result']['forwarded']['delay']['stamp']
                    add_line(text_buffer, 'Start of MAM query: ', timestamp, 'MAM', top)
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                tab.stanza_id = msg['mam_result']['id']
                nick = str(message['from'])
                if isinstance(tab, tabs.MucTab):
                    nick = nick.split('/')[1]
                else:
                    nick = nick.split('/')[0]
                add_line(text_buffer, message['body'], timestamp, nick, top)
                if msg is msgs[len(msgs)-1]:
                    timestamp = msg['mam_result']['forwarded']['delay']['stamp']
                    add_line(text_buffer, 'End of MAM query: ', timestamp, 'MAM', top)
                tab.text_win.scroll_up(len(tab.text_win.built_lines))
        else:
            for msg in rsm['mam']['results']:
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                nick = str(message['from'])
                if 'conference' in list(iq['disco_info']['identities'])[0]:
                    nick = nick.split('/')[1]
                else:
                    nick = nick.split('/')[0]
                add_line(text_buffer, message['body'], timestamp, nick, top)
                tab.core.refresh_window()
    if len(msgs) == 0:
        return tab.core.information('No more messages left to retrieve', 'Info')
    tab.query_id = 0

def mam_scroll(tab):
    remote_jid = tab.jid
    text_buffer = tab._text_buffer
    try:
        before = tab.stanza_id
    except:
        before = False
        end = datetime.now()
    end = end.replace(tzinfo=tzone).astimezone(tz=timezone.utc)
    end = end.replace(tzinfo=None)
    end = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')
    start = False
    top = True
    pos = tab.text_win.pos
    tab.text_win.pos += tab.text_win.height - 1
    if tab.text_win.pos + tab.text_win.height > len(tab.text_win.built_lines):
        asyncio.ensure_future(query(tab, remote_jid, top, start, end, before))
        tab.query_id = 1
        tab.text_win.pos = len(tab.text_win.built_lines) - tab.text_win.height
        if tab.text_win.pos < 0:
            tab.text_win.pos = 0
    return tab.text_win.pos != pos
