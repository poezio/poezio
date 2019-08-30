#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from slixmpp.exceptions import IqError, IqTimeout
from poezio.theming import get_theme
from poezio import tabs
from poezio import xhtml, colors
from poezio.config import config
from poezio.text_buffer import Message, TextBuffer

def add_line(tab, text_buffer: TextBuffer, text: str, str_time: str, nick: str, top: bool):
    """Adds a textual entry in the TextBuffer"""

    time = datetime.strftime(str_time, '%Y-%m-%d %H:%M:%S')
    time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
    time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)
    time = time.replace(tzinfo=None)
    deterministic = config.get_by_tabname('deterministic_nick_colors',
                                              tab.jid.bare)
    if isinstance(tab, tabs.MucTab):
        nick = nick.split('/')[1]
        user = tab.get_user_by_name(nick)
        if deterministic:
            if user:
                color = user.color
            else:
                theme = get_theme()
                if theme.ccg_palette:
                    fg_color = colors.ccg_text_to_color(theme.ccg_palette, nick)
                    color = fg_color, -1
                else:
                    mod = len(theme.LIST_COLOR_NICKNAMES)
                    nick_pos = int(md5(nick.encode('utf-8')).hexdigest(),
                                16) % mod
                    color = theme.LIST_COLOR_NICKNAMES[nick_pos]
        else:
            color = random.choice(list(xhtml.colors))
            color = xhtml.colors.get(color)
            color = (color, -1)
    else:
        nick = nick.split('/')[0]
        color = get_theme().COLOR_OWN_NICK
    text_buffer.add_message(
        txt=text,
        time=time,
        nickname=nick,
        nick_color=color,
        history=True,
        user=None,
        highlight=False,
        top=top,
        identifier=None,
        str_time=None,
        jid=None,
    )

async def query(tab, remote_jid, action, amount, top, start=None, end=None, before=None):
    text_buffer = tab._text_buffer
    try:
        iq = await tab.core.xmpp.plugin['xep_0030'].get_info(jid=remote_jid)
    except (IqError, IqTimeout):
        if action is 'scroll':
            return tab.core.information('%s : Failed to retrieve messages' % remote_jid, 'Error')
    if 'urn:xmpp:mam:2' not in iq['disco_info'].get_features() and action is 'scroll':
        return tab.core.information("%s doesn't support MAM." % remote_jid, "Info")
    if top:
        if isinstance(tab, tabs.MucTab):
            try:
                if before is not None:
                    results = tab.core.xmpp['xep_0313'].retrieve(jid=remote_jid,
                    iterator=True, reverse=top, rsm={'before':before, 'max':amount})
                else:
                    results = tab.core.xmpp['xep_0313'].retrieve(jid=remote_jid,
                    iterator=True, reverse=top, end=end, rsm={'max':amount})
            except (IqError, IqTimeout):
                if action is 'scroll':
                    return tab.core.information('%s : Failed to retrieve messages' % remote_jid, 'Error')
        else:
            try:
                if before is not None:
                    results = tab.core.xmpp['xep_0313'].retrieve(with_jid=remote_jid,
                    iterator=True, reverse=top, rsm={'before':before, 'max':amount})
                else:
                    results = tab.core.xmpp['xep_0313'].retrieve(with_jid=remote_jid,
                    iterator=True, reverse=top, end=end, rsm={'max':amount})
            except (IqError, IqTimeout):
                if action is 'scroll':
                    return tab.core.information('%s : Failed to retrieve messages' % remote_jid, 'Error')
    else:
        if 'conference' in list(iq['disco_info']['identities'])[0]:
            try:
                results = tab.core.xmpp['xep_0313'].retrieve(jid=remote_jid,
                iterator=True, reverse=top, start=start, end=end)
            except (IqError, IqTimeout):
                return tab.core.information('%s : Failed to retrieve messages' % remote_jid, 'Error')
        else:
            try:
                results = tab.core.xmpp['xep_0313'].retrieve(with_jid=remote_jid,
                iterator=True, reverse=top, start=start, end=end)
            except (IqError, IqTimeout):
                return tab.core.information('%s : Failed to retrieve messages' % remote_jid, 'Error')
    msg_count = 0
    msgs = []
    async for rsm in results:
        if top:
            for msg in rsm['mam']['results']:
                if msg['mam_result']['forwarded']['stanza'].xml.find(
                    '{%s}%s' % ('jabber:client', 'body')) is not None:
                    msgs.append(msg)
                if msg_count == amount:
                    tab.query_status = False
                    tab.core.refresh_window()
                    return
                msg_count += 1
            msgs.reverse()
            for msg in msgs:
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                tab.last_stanza_id = msg['mam_result']['id']
                nick = str(message['from'])
                add_line(tab, text_buffer, message['body'], timestamp, nick, top)
        else:
            for msg in rsm['mam']['results']:
                forwarded = msg['mam_result']['forwarded']
                timestamp = forwarded['delay']['stamp']
                message = forwarded['stanza']
                nick = str(message['from'])
                add_line(tab, text_buffer, message['body'], timestamp, nick, top)
                tab.core.refresh_window()
    tab.query_status = False

def mam_scroll(tab, action):
    remote_jid = tab.jid
    text_buffer = tab._text_buffer
    before = tab.last_stanza_id
    end = datetime.now()
    if isinstance(tab, tabs.MucTab) is False:
        for message in text_buffer.messages:
            time = message.time
            if time < end:
                end = time
        end = end + timedelta(seconds=-1)
    tzone = datetime.now().astimezone().tzinfo
    end = end.replace(tzinfo=tzone).astimezone(tz=timezone.utc)
    end = end.replace(tzinfo=None)
    end = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')
    if action is 'scroll':
        amount = tab.text_win.height
    else:
        amount = 2 * tab.text_win.height
    if amount >= 100:
        amount = 99
    if before is None:
        asyncio.ensure_future(query(tab, remote_jid, action, amount, top=True, end=end))
    else:
        asyncio.ensure_future(query(tab, remote_jid, action, amount, top=True, before=before))
    tab.query_status = True
