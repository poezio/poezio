"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from hashlib import md5
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)

from slixmpp import JID, Message as SMessage
from slixmpp.exceptions import IqError, IqTimeout
from poezio.theming import get_theme
from poezio import tabs
from poezio import colors
from poezio.common import to_utc
from poezio.ui.types import (
    BaseMessage,
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
        jid: JID,
        identifier: str = '',
        nick: str = ''
    ) -> Message:
    """Adds a textual entry in the TextBuffer"""

    # Convert to local timezone
    time = time.replace(tzinfo=timezone.utc).astimezone(tz=None)
    time = time.replace(tzinfo=None)

    if isinstance(tab, tabs.MucTab):
        nick = jid.resource
        user = tab.get_user_by_name(nick)
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
        if jid.bare == tab.core.xmpp.boundjid.bare:
            if not nick:
                nick = tab.core.own_nick
            color = get_theme().COLOR_OWN_NICK
        else:
            color = get_theme().COLOR_REMOTE_USER
            if not nick:
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
    ) -> AsyncIterable[SMessage]:
    """Get an async iterator for this mam query"""
    try:
        query_jid = remote_jid if groupchat else JID(core.xmpp.boundjid.bare)
        iq = await core.xmpp.plugin['xep_0030'].get_info(jid=query_jid)
    except (IqError, IqTimeout):
        raise DiscoInfoException()
    if 'urn:xmpp:mam:2' not in iq['disco_info'].get_features():
        raise NoMAMSupportException()

    args: Dict[str, Any] = {
        'iterator': True,
        'reverse': reverse,
    }

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
        'jid': message['from'],
        'text': message['body'],
        'identifier': message['origin-id']
    }


def _ignore_private_message(stanza: SMessage, filter_jid: Optional[JID]) -> bool:
    """Returns True if a MUC-PM should be ignored, as prosody returns
    all PMs within the same room.
    """
    if filter_jid is None:
        return False
    sent = stanza['from'].bare != filter_jid.bare
    if sent and stanza['to'].full != filter_jid.full:
        return True
    elif not sent and stanza['from'].full != filter_jid.full:
        return True
    return False


async def retrieve_messages(tab: tabs.ChatTab,
                            results: AsyncIterable[SMessage],
                            amount: int = 100) -> List[BaseMessage]:
    """Run the MAM query and put messages in order"""
    msg_count = 0
    msgs = []
    to_add = []
    tab_is_private = isinstance(tab, tabs.PrivateTab)
    filter_jid = None
    if tab_is_private:
        filter_jid = tab.jid
    try:
        async for rsm in results:
            for msg in rsm['mam']['results']:
                stanza = msg['mam_result']['forwarded']['stanza']
                if stanza.xml.find('{%s}%s' % ('jabber:client', 'body')) is not None:
                    if _ignore_private_message(stanza, filter_jid):
                        continue
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
