# -*- coding: utf-8 -*-

# Copyright 2009, 2010 Erwan Briand
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

# Implementation of the XEP-0045: Multi-User Chat.

from xmpp import NS_MUC_ADMIN, NS_MUC
from xmpp.protocol import Presence, Iq, Message, JID
import xmpp
import common
import threading
import os

from time import (altzone, gmtime, localtime, strftime, timezone)

from handler import Handler
from config import config

def get_stripped_jid(jid):
    """Return the stripped JID (bare representation)"""
    if isinstance(jid, basestring):
        jid = JID(jid)
    return jid.getStripped()

def is_jid(jid):
    """Return True if this is a valid JID"""
    if JID(jid).getNode() != '':
        return True

class VcardSender(threading.Thread):
    """
    avatar sending is really slow (don't know why...)
    use a thread to send it...
    """
    def __init__(self, connection):
        threading.Thread.__init__(self)
        self.connection = connection
        self.handler = Handler()

    def run(self):
        self.send_vcard()

    def send_vcard(self):
        """
        Method stolen from Gajim (thanks)
        ## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
        ##                    Junglecow J <junglecow AT gmail.com>
        ## Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
        ##                         Travis Shirk <travis AT pobox.com>
        ##                         Nikos Kouremenos <kourem AT gmail.com>
        ## Copyright (C) 2006-2008 Yann Leboulanger <asterix AT lagaule.org>
        ## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
        ## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
        ##                         Jean-Marie Traissard <jim AT lapin.org>
        ##                         Stephan Erb <steve-e AT h3c.de>
        ## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
        (one of these people coded this method, probably)
        """
        if not self.connection:
            return
        vcard = {
            "FN":config.get('full_name', ''),
            "URL":config.get('website', ''),
            "EMAIL":{
                "USERID":config.get('email', '')
                },
            "DESC":config.get('comment', 'A proud Poezio user')
            }
        photo_file_path = config.get('photo', '../data/poezio_80.png')
        (image, mime_type, sha1) = common.get_base64_from_file(photo_file_path)
        if image:
            vcard['PHOTO'] = {"TYPE":mime_type,"BINVAL":image}
        iq = xmpp.Iq(typ = 'set')
        iq2 = iq.setTag(xmpp.NS_VCARD + ' vCard')
        for i in vcard:
            if i == 'jid':
                continue
            if isinstance(vcard[i], dict):
                iq3 = iq2.addChild(i)
                for j in vcard[i]:
                    iq3.addChild(j).setData(vcard[i][j])
            elif isinstance(vcard[i], list):
                for j in vcard[i]:
                    iq3 = iq2.addChild(i)
                    for k in j:
                        iq3.addChild(k).setData(j[k])
            else:
                iq2.addChild(i).setData(vcard[i])
        self.connection.send(iq)
        iq = xmpp.Iq(typ = 'set')
        iq2 = iq.setTag(xmpp.NS_VCARD_UPDATE)
        iq2.addChild('PHOTO').setData(sha1)
        self.connection.send(iq)

class MultiUserChat(object):
    def __init__(self, connection):
        self.connection = connection
        self.vcard_sender = VcardSender(self.connection)

        self.rooms = []
        self.rn = {}

        self.own_jid = None

        self.handler = Handler()
        self.handler.connect('join-room', self.join_room)
        self.handler.connect('on-connected', self.on_connected)
        self.handler.connect('send-version', self.send_version)
        self.handler.connect('send-time', self.send_time)

    def on_connected(self, jid):
        self.own_jid = jid
        rooms = config.get('rooms', '')
        if rooms == '' or type(rooms) != str:
            return
        else:
            rooms = rooms.split(':')
        for room in rooms:
            args = room.split('/')
            if args[0] == '':
                return
            roomname = args[0]
            if len(args) == 2:
                nick = args[1]
            else:
                default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
                nick = config.get('default_nick', '')
                if nick == '':
                    nick = default
            self.handler.emit('join-room', room=roomname, nick=nick)
        if config.get('jid', '') == '': # Don't send the vcard if we're not anonymous
            self.vcard_sender.start()   # because the user ALREADY has one on the server

    def send_message(self, room, message):
        mes = Message(to=room)
        mes.setBody(message)
        mes.setType('groupchat')
        self.connection.send(mes)

    def send_private_message(self, user_jid, message):
        mes = Message(to=user_jid)
        mes.setBody(message)
        mes.setType('chat')
        self.connection.send(mes)

    def join_room(self, room, nick, password=None):
        """Join a new room"""
        pres = Presence(to='%s/%s' % (room, nick))
        pres.setFrom('%s'%self.own_jid)
        if not password:
            pres.addChild(name='x', namespace=NS_MUC)
        else:
            item = pres.addChild(name='x', namespace=NS_MUC)
            passwd = item.addChild(name='password')
            passwd.setData(password)
        self.connection.send(pres)

    def quit_room(self, room, nick, msg=None):
        """Quit a room"""
        if room is None and nick is None:
            self.on_disconnect()
            return

        pres = Presence(to='%s/%s' % (room, nick), typ='unavailable')
        if msg:
            pres.setStatus(msg)
        self.connection.send(pres)

    def disconnect(self, rooms, msg):
        """
        """
        for room in rooms:
            if room.jid is None and room.joined:
                pres = Presence(to='%s' % room.name,
                                typ='unavailable')
                pres.setStatus(msg)
                self.connection.send(pres)

    def on_disconnect(self):
        """Called at disconnection"""
        for room in self.rooms:
            pres = Presence(to='%s/%s' % (room, self.rn[room]),
                            typ='unavailable')
            self.connection.send(pres)

    def on_iq(self, iq):
        """Receive a MUC iq notification"""
        from_ = iq.getFrom().__str__()

        if get_stripped_jid(from_) in self.rooms:
            children = iq.getChildren()
            for child in children:
                if child.getName() == 'error':
                    code = int(child.getAttr('code'))
                    msg = None

                    echildren = child.getChildren()
                    for echild in echildren:
                        if echild.getName() == 'text':
                            msg = echild.getData()

                    self.handler.emit('on-muc-error',
                                      room=from_,
                                      code=code,
                                      msg=msg)

    def on_presence(self, presence):
        """Receive a MUC presence notification"""
        from_ = presence.getFrom().__str__()

        if get_stripped_jid(from_) in self.rooms:
            self.handler.emit('on-muc-presence-changed',
                               jid=from_.encode('utf-8'),
                               priority=presence.getPriority(),
                               show=presence.getShow(),
                               status=presence.getStatus(),
                               stanza=presence
                              )

    def on_message(self, message):
        """Receive a MUC message notification"""
        from_ = message.getFrom().__str__().encode('utf-8')

        if get_stripped_jid(from_) in self.rooms:
            body_ = message.getBody()
            type_ = message.getType()
            subj_ = message.getSubject()
            self.handler.emit('on-muc-message-received',
                              jid=from_, msg=body_, subject=subj_,
                              typ=type_, stanza=message)

    def eject_user(self, room, action, nick, reason):
        """Eject an user from a room"""
        iq = Iq(typ='set', to=room)
        query = iq.addChild('query', namespace=NS_MUC_ADMIN)
        item = query.addChild('item')

        if action == 'kick':
            item.setAttr('role', 'none')
            if is_jid(nick):
                item.setAttr('jid', nick)
            else:
                item.setAttr('nick', nick)
        elif action == 'ban':
            item.setAttr('affiliation', 'outcast')
            item.setAttr('jid', nick)

        if reason is not None:
            rson = item.addChild('reason')
            rson.setData(reason)

        self.connection.send(iq)

    def change_role(self, room, nick, role):
        """Change the role of an user"""
        iq = Iq(typ='set', to=room)
        query = iq.addChild('query', namespace=NS_MUC_ADMIN)
        item = query.addChild('item')
        item.setAttr('nick', nick)
        item.setAttr('role', role)

        self.connection.send(iq)

    def change_aff(self, room, jid, aff):
        """Change the affiliation of an user"""
        iq = Iq(typ='set', to=room)
        query = iq.addChild('query', namespace=NS_MUC_ADMIN)
        item = query.addChild('item')
        item.setAttr('jid', jid)
        item.setAttr('affiliation', aff)

        self.connection.send(iq)

    def change_subject(self, room, subject):
        """Change the subject of a room"""
        message = Message(typ='groupchat', to=room)
        subj = message.addChild('subject')
        subj.setData(subject)

        self.connection.send(message)

    def change_nick(self, room, nick):
        """Change the nickname"""
        pres = Presence(to='%s/%s' % (room, nick))
        self.connection.send(pres)

    def change_show(self, room, nick, show, status):
        pres = Presence(to='%s/%s' % (room, nick))
        pres.setShow(show)
        if status:
            pres.setStatus(status)
        self.connection.send(pres)

    def send_version(self, iq_obj):
        """
        from gajim and modified
        """
        iq_obj = iq_obj.buildReply('result')
        qp = iq_obj.getTag('query')
        if config.get('send_poezio_info', 'true') == 'true':
            qp.setTagData('name', 'Poezio')
            qp.setTagData('version', '0.6.1')
        else:
            qp.setTagData('name', 'Unknown')
            qp.setTagData('version', 'Unknown')
        if config.get('send_os_info', 'true') == 'true':
            qp.setTagData('os', common.get_os_info())
        else:
            qp.setTagData('os', 'Unknown')
        self.connection.send(iq_obj)
        raise xmpp.protocol.NodeProcessed

    def send_time(self, iq_obj):
        """
        from gajim
        """
        iq_obj = iq_obj.buildReply('result')
        qp = iq_obj.setTag('time',
                           namespace="urn:xmpp:time")
        if config.get('send_time', 'true') == 'true':
            qp.setTagData('utc', strftime('%Y-%m-%dT%H:%M:%SZ', gmtime()))
            isdst = localtime().tm_isdst
            zone = -(timezone, altzone)[isdst] / 60
            tzo = (zone / 60, abs(zone % 60))
            qp.setTagData('tzo', '%+03d:%02d' % (tzo))
            self.connection.send(iq_obj)
            raise xmpp.protocol.NodeProcessed
