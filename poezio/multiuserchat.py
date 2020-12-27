# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.
"""
Implementation of the XEP-0045: Multi-User Chat.
Add some facilities that are not available on the XEP_0045
slix plugin
"""

from __future__ import annotations

from xml.etree import ElementTree as ET
from typing import (
    Optional,
    TYPE_CHECKING,
)

from poezio.common import safeJID
from slixmpp import (
    JID,
    ClientXMPP,
    Iq,
)

import logging
log = logging.getLogger(__name__)


if TYPE_CHECKING:
    from poezio.core import Core
    from poezio.tabs import Tab


def change_show(
    xmpp: ClientXMPP,
    jid: JID,
    own_nick: str,
    show: str,
    status: Optional[str]
) -> None:
    """
    Change our 'Show'
    """
    jid = safeJID(jid)
    pres = xmpp.make_presence(pto='%s/%s' % (jid, own_nick))
    if show:  # if show is None, don't put a <show /> tag. It means "available"
        pres['type'] = show
    if status:
        pres['status'] = status
    pres.send()


def change_subject(xmpp: ClientXMPP, jid: JID, subject: str) -> None:
    """
    Change the room subject
    """
    jid = safeJID(jid)
    msg = xmpp.make_message(jid)
    msg['type'] = 'groupchat'
    msg['subject'] = subject
    msg.send()


def change_nick(
    core: Core,
    jid: JID,
    nick: str,
    status: Optional[str] = None,
    show: Optional[str] = None
) -> None:
    """
    Change our own nick in a room
    """
    xmpp = core.xmpp
    presence = xmpp.make_presence(
        pshow=show, pstatus=status, pto=safeJID('%s/%s' % (jid, nick)))
    core.events.trigger('changing_nick', presence)
    presence.send()


def join_groupchat(
    core: Core,
    jid: JID,
    nick: str,
    passwd: str = '',
    status: Optional[str] = None,
    show: Optional[str] = None,
    seconds: Optional[int] = None,
    tab: Optional[Tab] = None
) -> None:
    xmpp = core.xmpp
    stanza = xmpp.make_presence(
        pto='%s/%s' % (jid, nick), pstatus=status, pshow=show)
    x = ET.Element('{http://jabber.org/protocol/muc}x')
    if passwd:
        passelement = ET.Element('password')
        passelement.text = passwd
        x.append(passelement)

    def on_disco(iq: Iq) -> None:
        if ('urn:xmpp:mam:2' in iq['disco_info'].get_features()
                or (tab and tab._text_buffer.last_message)):
            history = ET.Element('{http://jabber.org/protocol/muc}history')
            history.attrib['seconds'] = str(0)
            x.append(history)
        else:
            if seconds is not None:
                history = ET.Element('{http://jabber.org/protocol/muc}history')
                history.attrib['seconds'] = str(seconds)
                x.append(history)
        stanza.append(x)
        core.events.trigger('joining_muc', stanza)
        to = stanza["to"]
        stanza.send()
        xmpp.plugin['xep_0045'].rooms[jid] = {}
        xmpp.plugin['xep_0045'].our_nicks[jid] = to.resource

    xmpp.plugin['xep_0030'].get_info(jid=jid, callback=on_disco)


def leave_groupchat(
    xmpp: ClientXMPP,
    jid: JID,
    own_nick: str,
    msg: str
) -> None:
    """
    Leave the groupchat
    """
    jid = safeJID(jid)
    try:
        xmpp.plugin['xep_0045'].leave_muc(jid, own_nick, msg)
    except KeyError:
        log.debug(
            "muc.leave_groupchat: could not leave the room %s",
            jid,
            exc_info=True)
