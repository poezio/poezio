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

from xml.etree import cElementTree as ET

from poezio.common import safeJID
from slixmpp.exceptions import IqError, IqTimeout
import logging
log = logging.getLogger(__name__)

NS_MUC_ADMIN = 'http://jabber.org/protocol/muc#admin'
NS_MUC_OWNER = 'http://jabber.org/protocol/muc#owner'


def destroy_room(xmpp, room, reason='', altroom=''):
    """
    destroy a room
    """
    room = safeJID(room)
    if not room:
        return False
    iq = xmpp.make_iq_set()
    iq['to'] = room
    query = ET.Element('{%s}query' % NS_MUC_OWNER)
    destroy = ET.Element('{%s}destroy' % NS_MUC_OWNER)
    if altroom:
        destroy.attrib['jid'] = altroom
    if reason:
        xreason = ET.Element('{%s}reason' % NS_MUC_OWNER)
        xreason.text = reason
        destroy.append(xreason)
    query.append(destroy)
    iq.append(query)

    def callback(iq):
        if not iq or iq['type'] == 'error':
            xmpp.core.information('Unable to destroy room %s' % room, 'Info')
        else:
            xmpp.core.information('Room %s destroyed' % room, 'Info')

    iq.send(callback=callback)
    return True


def send_private_message(xmpp, jid, line):
    """
    Send a private message
    """
    jid = safeJID(jid)
    xmpp.send_message(mto=jid, mbody=line, mtype='chat')


def send_groupchat_message(xmpp, jid, line):
    """
    Send a message to the groupchat
    """
    jid = safeJID(jid)
    xmpp.send_message(mto=jid, mbody=line, mtype='groupchat')


def change_show(xmpp, jid, own_nick, show, status):
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


def change_subject(xmpp, jid, subject):
    """
    Change the room subject
    """
    jid = safeJID(jid)
    msg = xmpp.make_message(jid)
    msg['type'] = 'groupchat'
    msg['subject'] = subject
    msg.send()


def change_nick(core, jid, nick, status=None, show=None):
    """
    Change our own nick in a room
    """
    xmpp = core.xmpp
    presence = xmpp.make_presence(
        pshow=show, pstatus=status, pto=safeJID('%s/%s' % (jid, nick)))
    core.events.trigger('changing_nick', presence)
    presence.send()


def join_groupchat(core,
                   jid,
                   nick,
                   passwd='',
                   status=None,
                   show=None,
                   seconds=None):
    xmpp = core.xmpp
    stanza = xmpp.make_presence(
        pto='%s/%s' % (jid, nick), pstatus=status, pshow=show)
    x = ET.Element('{http://jabber.org/protocol/muc}x')
    if passwd:
        passelement = ET.Element('password')
        passelement.text = passwd
        x.append(passelement)
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


def leave_groupchat(xmpp, jid, own_nick, msg):
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


def set_user_role(xmpp, jid, nick, reason, role, callback=None):
    """
    (try to) Set the role of a MUC user
    (role = 'none': eject user)
    """
    jid = safeJID(jid)
    iq = xmpp.make_iq_set()
    query = ET.Element('{%s}query' % NS_MUC_ADMIN)
    item = ET.Element('{%s}item' % NS_MUC_ADMIN, {'nick': nick, 'role': role})
    if reason:
        reason_el = ET.Element('{%s}reason' % NS_MUC_ADMIN)
        reason_el.text = reason
        item.append(reason_el)
    query.append(item)
    iq.append(query)
    iq['to'] = jid
    if callback:
        return iq.send(callback=callback)
    try:
        return iq.send()
    except (IqError, IqTimeout) as e:
        return e.iq


def set_user_affiliation(xmpp,
                         muc_jid,
                         affiliation,
                         nick=None,
                         jid=None,
                         reason=None,
                         callback=None):
    """
    (try to) Set the affiliation of a MUC user
    """
    muc_jid = safeJID(muc_jid)
    query = ET.Element('{http://jabber.org/protocol/muc#admin}query')
    if nick:
        item = ET.Element('{http://jabber.org/protocol/muc#admin}item', {
            'affiliation': affiliation,
            'nick': nick
        })
    else:
        item = ET.Element('{http://jabber.org/protocol/muc#admin}item', {
            'affiliation': affiliation,
            'jid': str(jid)
        })

    if reason:
        reason_item = ET.Element(
            '{http://jabber.org/protocol/muc#admin}reason')
        reason_item.text = reason
        item.append(reason_item)

    query.append(item)
    iq = xmpp.make_iq_set(query)
    iq['to'] = muc_jid
    if callback:
        return iq.send(callback=callback)
    try:
        return xmpp.plugin['xep_0045'].set_affiliation(
            str(muc_jid),
            str(jid) if jid else None, nick, affiliation)
    except:
        log.debug('Error setting the affiliation: %s', exc_info=True)
        return False


def cancel_config(xmpp, room):
    query = ET.Element('{http://jabber.org/protocol/muc#owner}query')
    x = ET.Element('{jabber:x:data}x', type='cancel')
    query.append(x)
    iq = xmpp.make_iq_set(query)
    iq['to'] = room
    iq.send()


def configure_room(xmpp, room, form):
    if form is None:
        return
    iq = xmpp.make_iq_set()
    iq['to'] = room
    query = ET.Element('{http://jabber.org/protocol/muc#owner}query')
    form['type'] = 'submit'
    query.append(form.xml)
    iq.append(query)
    iq.send()
