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
from logging import logger
from threading import Thread
from multiuserchat import MultiUserChat
from handler import Handler

class Connection(Thread):
    """
    Receives everything from Jabber and emits the
    appropriate signals
    """
    def __init__(self, server, resource):
        Thread.__init__(self)
        self.handler = Handler()

        self.server = server
        self.resource = resource
        self.online = 0         # 1:connected, 2:auth confirmed
        self.jid = ''           # we don't know our jid yet (anon account)
        self.port = config.get('port', 5222)
        self.client = xmpp.Client(self.server, debug=[])

    def run(self):
        """
        run in a thread
        connect to server
        """
        if not self.connect_to_server(self.server, self.port):
            logger.error('Could not connect to server')
            sys.exit(-1)
        if not self.authenticate():
            logger.error('Could not authenticate to server')
            sys.exit(-1)
        self.client.sendInitPresence()
        self.online = 1      # 2 when confirmation of auth is received
        self.register_handlers()
        while 1:
            self.process()

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
        """
        register handlers from xmpppy signals
        """
        self.client.RegisterHandler('message', self.handler_message)
        self.client.RegisterHandler('presence', self.handler_presence)
        self.client.RegisterHandler('iq',         self.handler_iq)
        self.client.RegisterHandler('error',         self.handler_error)

    def handler_presence(self, connection, presence):
        fro = presence.getFrom()
        to = presence.getAttr('to')
        if fro == to:           # own presence
            self.online = 2
            self.jid = to
            self.handler.emit('on-connected', jid=fro)
            return
        self.handler.emit('room-presence', stanza=presence)

    def handler_message(self, connection, message):
        self.handler.emit('room-message', stanza=message)

    def handler_iq(self, connection, iq):
        self.handler.emit('room-iq', stanza=iq)

    def handler_error(self, connection, error):
        print "fion"
        sys.exit()
#        self.handler.emit('room-iq', stanza=iq)

    def process(self, timeout=10):
        if self.online:
            try:self.client.Process(timeout)
            except:
                pass
        else:
            log.warning('disconnecting...')
            sys.exit()
