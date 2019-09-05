#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from slixmpp import JID
from slixmpp.exceptions import IqError, IqTimeout
from poezio.theming import get_theme
from poezio import tabs
from poezio import xhtml, colors
from poezio.config import config
from poezio.text_buffer import Message, TextBuffer
from typing import List, Optional, Callable


class DiscoInfoException(Exception): pass
class MAMQueryException(Exception): pass
class NoMAMSupportException(Exception): pass


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

async def query(
        core,
        groupchat: bool,
        remote_jid: JID,
        amount: int,
        reverse: bool,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        before: Optional[str] = None,
        callback: Optional[Callable] = None,
    ) -> None:
    try:
        iq = await core.xmpp.plugin['xep_0030'].get_info(jid=remote_jid)
    except (IqError, IqTimeout):
        raise DiscoInfoException
    if 'urn:xmpp:mam:2' not in iq['disco_info'].get_features():
        raise NoMAMSupportException

    args = {
        'iterator': True,
        'reverse': reverse,
    }

    if groupchat:
        args['jid'] = remote_jid
    else:
        args['with_jid'] = remote_jid

    args['rsm'] = {'max': amount}
    if reverse:
        if before is not None:
            args['rsm']['before'] = before
        else:
            args['end'] = end
    else:
        args['rsm']['start'] = start
        if before is not None:
            args['rsm']['end'] = end
    try:
        results = core.xmpp['xep_0313'].retrieve(**args)
    except (IqError, IqTimeout):
        raise MAMQueryException
    if callback is not None:
        callback(results)

    return results

async def add_messages_to_buffer(tab, top: bool, results, amount: int) -> None:
    """Prepends or appends messages to the tab text_buffer"""

    text_buffer = tab._text_buffer
    msg_count = 0
    msgs = []
    async for rsm in results:
        if top:
            for msg in rsm['mam']['results']:
                if msg['mam_result']['forwarded']['stanza'] \
                .xml.find('{%s}%s' % ('jabber:client', 'body')) is not None:
                    msgs.append(msg)
                if msg_count == amount:
                    tab.core.refresh_window()
                    return False
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
    return False

async def fetch_history(tab, end: Optional[datetime] = None, amount: Optional[int] = None):
    remote_jid = tab.jid
    before = tab.last_stanza_id
    if end is None:
        end = datetime.now()
    tzone = datetime.now().astimezone().tzinfo
    end = end.replace(tzinfo=tzone).astimezone(tz=timezone.utc)
    end = end.replace(tzinfo=None)
    end = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')

    if amount >= 100:
        amount = 99

    groupchat = isinstance(tab, tabs.MucTab)

    results = await query(tab.core, groupchat, remote_jid, amount, reverse=True, end=end, before=before)
    query_status = await add_messages_to_buffer(tab, True, results, amount)
    tab.query_status = query_status

async def on_tab_open(tab) -> None:
    amount = 2 * tab.text_win.height
    end = datetime.now()
    for message in tab._text_buffer.messages:
        time = message.time
        if time < end:
            end = time
    end = end + timedelta(seconds=-1)
    try:
        await fetch_history(tab, end=end, amount=amount)
    except (NoMAMSupportException, MAMQueryException, DiscoInfoException):
        return None

async def on_scroll_up(tab) -> None:
    amount = tab.text_win.height
    try:
        await fetch_history(tab, amount=amount)
    except NoMAMSupportException:
        tab.core.information('MAM not supported for %r' % tab.jid, 'Info')
        return None
    except (MAMQueryException, DiscoInfoException):
        tab.core.information('An error occured when fetching MAM for %r' % tab.jid, 'Error')
        return None
