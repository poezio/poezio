#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from hashlib import md5
from typing import (
    Any,
    AsyncIterable,
    Callable,
    Dict,
    List,
    Optional,
)

from slixmpp import JID, Message as SMessage
from slixmpp.exceptions import IqError, IqTimeout
from poezio.theming import get_theme
from poezio import tabs
from poezio import xhtml, colors
from poezio.config import config
from poezio.common import to_utc
from poezio.text_buffer import TextBuffer, HistoryGap
from poezio.ui.types import (
    BaseMessage,
    EndOfArchive,
    Message,
)


log = logging.getLogger(__name__)

class DiscoInfoException(Exception): pass
class MAMQueryException(Exception): pass
class NoMAMSupportException(Exception): pass


def make_line(
        tab: tabs.ChatTab,
        text: str,
        time: datetime,
        nick: str,
        identifier: str = '',
    ) -> Message:
    """Adds a textual entry in the TextBuffer"""

    # Convert to local timezone
    time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)
    time = time.replace(tzinfo=None)

    deterministic = config.get_by_tabname('deterministic_nick_colors', tab.jid.bare)
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
                    nick_pos = int(md5(nick.encode('utf-8')).hexdigest(), 16) % mod
                    color = theme.LIST_COLOR_NICKNAMES[nick_pos]
        else:
            color = random.choice(list(xhtml.colors))
            color = xhtml.colors.get(color)
            color = (color, -1)
    else:
        if nick.split('/')[0] == tab.core.xmpp.boundjid.bare:
            color = get_theme().COLOR_OWN_NICK
        else:
            color = get_theme().COLOR_REMOTE_USER
        nick = tab.get_nick()
    return Message(
        txt=text,
        identifier=identifier,
        time=time,
        nickname=nick,
        nick_color=color,
        history=True,
        user=None,
    )

async def get_mam_iterator(
        core,
        groupchat: bool,
        remote_jid: JID,
        amount: int,
        reverse: bool = True,
        start: Optional[str] = None,
        end: Optional[str] = None,
        before: Optional[str] = None,
    ) -> AsyncIterable[Message]:
    """Get an async iterator for this mam query"""
    try:
        query_jid = remote_jid if groupchat else JID(core.xmpp.boundjid.bare)
        iq = await core.xmpp.plugin['xep_0030'].get_info(jid=query_jid)
    except (IqError, IqTimeout):
        raise DiscoInfoException()
    if 'urn:xmpp:mam:2' not in iq['disco_info'].get_features():
        raise NoMAMSupportException()

    args = {
        'iterator': True,
        'reverse': reverse,
    }  # type: Dict[str, Any]

    if groupchat:
        args['jid'] = remote_jid
    else:
        args['with_jid'] = remote_jid

    if amount > 0:
        args['rsm'] = {'max': amount}
    args['start'] = start
    args['end'] = end
    return core.xmpp['xep_0313'].retrieve(**args)


def _parse_message(msg: SMessage) -> Dict:
    """Parse info inside a MAM forwarded message"""
    forwarded = msg['mam_result']['forwarded']
    message = forwarded['stanza']
    return {
        'time': forwarded['delay']['stamp'],
        'nick': str(message['from']),
        'text': message['body'],
        'identifier': message['origin-id']
    }


async def retrieve_messages(tab: tabs.ChatTab,
                            results: AsyncIterable[SMessage],
                            amount: int = 100) -> List[BaseMessage]:
    """Run the MAM query and put messages in order"""
    text_buffer = tab._text_buffer
    msg_count = 0
    msgs = []
    to_add = []
    try:
        async for rsm in results:
            for msg in rsm['mam']['results']:
                if msg['mam_result']['forwarded']['stanza'] \
                        .xml.find('{%s}%s' % ('jabber:client', 'body')) is not None:
                    args = _parse_message(msg)
                    msgs.append(make_line(tab, **args))
            for msg in reversed(msgs):
                to_add.append(msg)
                msg_count += 1
                if msg_count == amount:
                    to_add.reverse()
                    return to_add
            msgs = []
        to_add.reverse()
        return to_add
    except (IqError, IqTimeout) as exc:
        log.debug('Unable to complete MAM query: %s', exc, exc_info=True)
        raise MAMQueryException('Query interrupted')


async def fetch_history(tab: tabs.ChatTab,
                        start: Optional[datetime] = None,
                        end: Optional[datetime] = None,
                        amount: int = 100) -> List[BaseMessage]:
    remote_jid = tab.jid
    if not end:
        for msg in tab._text_buffer.messages:
            if isinstance(msg, Message):
                end = msg.time
                end -= timedelta(microseconds=1)
                break
    if end is None:
        end = datetime.now()
    end = to_utc(end)
    end_str = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')

    start_str = None
    if start is not None:
        start = to_utc(start)
        start_str = datetime.strftime(start, '%Y-%m-%dT%H:%M:%SZ')

    mam_iterator = await get_mam_iterator(
        core=tab.core,
        groupchat=isinstance(tab, tabs.MucTab),
        remote_jid=remote_jid,
        amount=amount,
        end=end_str,
        start=start_str,
        reverse=True,
    )
    return await retrieve_messages(tab, mam_iterator, amount)

async def fill_missing_history(tab: tabs.ChatTab, gap: HistoryGap) -> None:
    start = gap.last_timestamp_before_leave
    end = gap.first_timestamp_after_join
    if start:
        start = start + timedelta(seconds=1)
    if end:
        end = end - timedelta(seconds=1)
    try:
        messages = await fetch_history(tab, start=start, end=end, amount=999)
        tab._text_buffer.add_history_messages(messages, gap=gap)
        if messages:
            tab.core.refresh_window()
    except (NoMAMSupportException, MAMQueryException, DiscoInfoException):
        return
    finally:
        tab.query_status = False

async def on_new_tab_open(tab: tabs.ChatTab) -> None:
    """Called when opening a new tab"""
    amount = 2 * tab.text_win.height
    end = datetime.now()
    for message in tab._text_buffer.messages:
        if isinstance(message, Message) and to_utc(message.time) < to_utc(end):
            end = message.time
            break
    end = end - timedelta(microseconds=1)
    try:
        messages = await fetch_history(tab, end=end, amount=amount)
        tab._text_buffer.add_history_messages(messages)
        if messages:
            tab.core.refresh_window()
    except (NoMAMSupportException, MAMQueryException, DiscoInfoException):
        return None
    finally:
        tab.query_status = False


def schedule_tab_open(tab: tabs.ChatTab) -> None:
    """Set the query status and schedule a MAM query"""
    tab.query_status = True
    asyncio.ensure_future(on_tab_open(tab))


async def on_tab_open(tab: tabs.ChatTab) -> None:
    gap = tab._text_buffer.find_last_gap_muc()
    if gap is None or not gap.leave_message:
        await on_new_tab_open(tab)
    else:
        await fill_missing_history(tab, gap)


def schedule_scroll_up(tab: tabs.ChatTab) -> None:
    """Set query status and schedule a scroll up"""
    tab.query_status = True
    asyncio.ensure_future(on_scroll_up(tab))


async def on_scroll_up(tab: tabs.ChatTab) -> None:
    tw = tab.text_win

    # If position in the tab is < two screen pages, then fetch MAM, so that we
    # keep some prefetched margin. A first page should also be prefetched on
    # join if not already available.
    total, pos, height = len(tw.built_lines), tw.pos, tw.height
    rest = (total - pos) // height

    if rest > 1:
        tab.query_status = False
        return None

    try:
        # XXX: Do we want to fetch a possibly variable number of messages?
        # (InfoTab changes height depending on the type of messages, see
        # `information_buffer_popup_on`).
        messages = await fetch_history(tab, amount=height)
        last_message_exists = False
        if tab._text_buffer.messages:
            last_message = tab._text_buffer.messages[0]
            last_message_exists = True
        if not messages and last_message_exists and not isinstance(last_message, EndOfArchive):
            time = tab._text_buffer.messages[0].time
            messages = [EndOfArchive('End of archive reached', time=time)]
        tab._text_buffer.add_history_messages(messages)
        if messages:
            tab.core.refresh_window()
    except NoMAMSupportException:
        tab.core.information('MAM not supported for %r' % tab.jid, 'Info')
        return None
    except (MAMQueryException, DiscoInfoException):
        tab.core.information('An error occured when fetching MAM for %r' % tab.jid, 'Error')
        return None
    finally:
        tab.query_status = False
