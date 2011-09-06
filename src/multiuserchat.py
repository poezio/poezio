# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the MIT license. See the COPYING file.

"""
Implementation of the XEP-0045: Multi-User Chat.
Add some facilities that are not available on the XEP_0045
sleek plugin
"""

import sleekxmpp

from xml.etree import cElementTree as ET

import logging
log = logging.getLogger(__name__)

NS_MUC_ADMIN = 'http://jabber.org/protocol/muc#admin'

def send_private_message(xmpp, jid, line):
    """
    Send a private message
    """
    xmpp.send_message(mto=jid, mbody=line, mtype='chat')

def send_groupchat_message(xmpp, jid, line):
    """
    Send a message to the groupchat
    """
    xmpp.send_message(mto=jid, mbody=line, mtype='groupchat')

def change_show(xmpp, jid, own_nick, show, status):
    """
    Change our 'Show'
    """
    pres = xmpp.make_presence(pto='%s/%s' % (jid, own_nick))
    if show: # if show is None, don't put a <show /> tag. It means "available"
        pres['type'] = show
    if status:
        pres['status'] = status
    pres.send()

def change_subject(xmpp, jid, subject):
    """
    Change the room subject
    """
    msg = xmpp.make_message(jid)
    msg['type'] = 'groupchat'
    msg['subject'] = subject
    msg.send()

def change_nick(xmpp, jid, nick, status=None, show=None):
    """
    Change our own nick in a room
    """
    xmpp.make_presence(pshow=show, pstatus=status, pto='%s/%s' % (jid, nick)).send()

def join_groupchat(xmpp, jid, nick, passwd='', maxhistory=None, status=None, show=None):
    xmpp.plugin['xep_0045'].joinMUC(jid, nick, maxhistory=maxhistory, password=passwd, pstatus=status, pshow=show)

def leave_groupchat(xmpp, jid, own_nick, msg):
    """
    Leave the groupchat
    """
    xmpp.plugin['xep_0045'].leaveMUC(jid, own_nick, msg)

def eject_user(xmpp, jid, nick, reason):
    """
    (try to) Eject an user from the room
    """
    iq = xmpp.makeIqSet()
    query = ET.Element('{%s}query' % NS_MUC_ADMIN)
    item = ET.Element('{%s}item' % NS_MUC_ADMIN, {'nick':nick, 'role':'none'})
    if reason:
        reason_el = ET.Element('{%s}reason' % NS_MUC_ADMIN)
        reason_el.text = reason
        item.append(reason_el)
    query.append(item)
    iq.append(query)
    iq['to'] = jid
    return iq.send()
