# Copyright 2010, Florent Le Coz <louizatakk@fedoraproject.org>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation version 3 of the License.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Implementation of the XEP-0045: Multi-User Chat.
Add some facilities that are not available on the XEP_0045
sleek plugin
"""

import sleekxmpp

from xml.etree import cElementTree as ET


from common import debug

def send_private_message(xmpp, jid, line):
    """
    Send a private message
    """
    msg = xmpp.makeMessage(jid)
    msg['to'] = jid
    msg['type'] = 'chat'
    msg['body'] = line
    msg.send()

def send_groupchat_message(xmpp, jid, line):
    """
    Send a message to the groupchat
    """
    msg = xmpp.makeMessage(jid)
    msg['type'] = 'groupchat'
    msg['body'] = line
    msg.send()

def change_show(xmpp, jid, own_nick, show, status):
    """
    Change our 'Show'
    """
    pres = xmpp.makePresence(pto='%s/%s' % (jid, own_nick),
                             pfrom=xmpp.fulljid)
    if show: # if show is None, don't put a <show /> tag. It means "online"
        pres['type'] = show
    if status:
        pres['status'] = status
    debug('Change presence: %s\n' % (pres))
    pres.send()

def change_subject(xmpp, jid, subject):
    """
    Change the room subject
    """
    msg = xmpp.makeMessage(jid)
    msg['type'] = 'groupchat'
    msg['subject'] = subject
    msg['from'] = xmpp.jid
    msg.send()

def change_nick(xmpp, jid, nick):
    """
    Change our own nick in a room
    """
    xmpp.makePresence(pto='%s/%s' % (jid, nick),
                            pfrom=xmpp.jid).send()

def join_groupchat(xmpp, jid, nick, password=None):
    """
    Join the groupchat
    """
    xmpp.plugin['xep_0045'].joinMUC(jid, nick, password)

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
    query = ET.Element('{http://jabber.org/protocol/muc#admin}query')
    item = ET.Element('{http://jabber.org/protocol/muc#admin}item', {'nick':nick, 'role':'none'})
    if reason:
        reason_el = ET.Element('{http://jabber.org/protocol/muc#admin}reason')
        reason_el.text = reason
        item.append(reason_el)
    query.append(item)
    iq.append(query)
    iq['to'] = jid
    return iq.send()
