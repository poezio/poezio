#!/usr/bin/python
# -*- coding:utf-8 -*-
#
# Copyright 2010 Le Coz Florent <louizatakk@fedoraproject.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

import sys

import xmpp
from config import config
from logging import log
from threading import Thread
from multiuserchat import MultiUserChat
from handler import Handler

class Connection(Thread):
    """
    Handles all network transactions
    """
    def __init__(self, server, resource):
        Thread.__init__(self)
        self.handler = Handler()

        self.server = server
        self.resource = resource
        self.online = 0         # 1:connected, 2:auth confirmed
        self.jid = ''           # we don't know our jid yet (anon account)
        if not self.server:
            log.error('You should set a server in the configuration file')
        self.port = int(config.get('port'))
        if not self.port:
            log.warning('No port set in configuration file, defaulting to 5222')
            self.port = 5222

    def run(self):
        """
        connect to server
        """
        self.client = xmpp.Client(self.server)
        if not self.connect_to_server(self.server, self.port):
            log.error('Could not connect to server')
            sys.exit(-1)
        if not self.authenticate():
            log.error('Could not authenticate to server')
            sys.exit(-1)
        self.client.sendInitPresence()
        self.online = 1      # 2 when confirmation of auth is received
        self.register_handlers()

    def connect_to_server(self, server, port):
        # TODO proxy stuff
        return self.client.connect((server, port))

    def authenticate(self, anon=True):
        if anon:
            return self.client.auth(None, None, self.resource)
        else:
            log.error('Non-anonymous connections not handled currently')
            return None

    def register_handlers(self):
        self.client.RegisterHandler('message', self.handler_message)
        self.client.RegisterHandler('presence', self.handler_presence)
        self.client.RegisterHandler('iq', self.handler_iq)

    def handler_message(self, connection, message):
        # body = message.getTag('body').getData()
        # fro = str(message.getAttr('from'))
        # room, nick = fro.split('/')
        # print 'Message from %s in %s :' % (nick, room), body
        self.handler.emit('xmpp-message-handler', message=message)

    def handler_presence(self, connection, presence):
        affil, role = u'', u''
        fro = presence.getFrom()#presence.getAttr('from')
        room_from, nick_from = fro.getStripped().encode('utf-8'), fro.getResource().encode('utf-8')
        to = presence.getAttr('to')
        room_to, nick_to = to.getStripped().encode('utf-8'), to.getResource().encode('utf-8')
        if fro == to:           # own presence
            self.online = 2
            self.jid = to
            print 'Authentification confirmation received!'
            return
        for x in presence.getTags('x'):
            if x.getTag('item'):
                affil = x.getTagAttr('item', 'affiliation').encode('utf-8')
                role = x.getTagAttr('item', 'role').encode('utf-8')
                break
#        print '[%s] in room {%s}. (%s - %s)'% (nick_from, room_from, affil, role)
        self.handler.emit('xmpp-presence-handler', presence=presence)

    def handler_iq(self, connection, iq):
        pass

    def process(self, timeout=10):
        if self.online:
            self.client.Process(timeout)
        else:
            log.warning('disconnecting...')

if __name__ == '__main__':
    resource = config.get('resource')
    server = config.get('server')
    connection = Connection(server, resource)
    connection.start()
    rooms = config.get('rooms').split(':')
    from time import sleep
    print connection.online
    sleep(2)
    print connection.online
    for room in rooms:
        connection.send_join_room(room.split('/')[0], room.split('/')[1])
        i = 17
    while i:
        connection.process()
        i -= 1
