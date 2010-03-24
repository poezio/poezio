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

from gettext import (bindtextdomain, textdomain, bind_textdomain_codeset,
                     gettext as _)


bindtextdomain('poezio')
textdomain('poezio')
bind_textdomain_codeset('poezio', 'utf-8')
import locale
locale.setlocale(locale.LC_ALL, '')

import sys

import xmpp
from config import config
from logging import logger
from handler import Handler
from common import exception_handler
import threading
import thread

class Connection(threading.Thread):
    """
    Receives everything from Jabber and emits the
    appropriate signals
    """
    def __init__(self, server, resource):
        threading.Thread.__init__(self)
        self.handler = Handler()
        self.daemon = True      # exit the program when this exits
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
        sys.excepthook = exception_handler
        if not self.connect_to_server(self.server, self.port):
            self.handler.emit('error', msg='Could not connect to server')
            sys.exit(-1)
        if not self.authenticate():
            self.handler.emit('error', msg='Could not authenticate to server')
            sys.exit(-1)
        self.client.sendInitPresence(requestRoster=0)
        self.online = 1      # 2 when confirmation of auth is received
        self.register_handlers()
        while 1:
            self.process()

    def connect_to_server(self, server, port):
        if config.get('use_proxy','false') == 'true':
            return self.client.connect((server, port),
                                       {'host': config.get("proxy_server", ""),
                                        'port': config.get("proxy_port", 1080),
                                        'user': config.get("proxy_user", ""),
                                        'password': config.get("proxy_password", "")
                                        })
        else:
            return self.client.connect((server, port))

    def authenticate(self, anon=True):
        if anon:
            try:
                self.client.auth(None, "", self.resource)
                return True
            except TypeError:
                self.handler.emit('error', msg=_('Error: Could not authenticate. Please make sure the server you chose (%s) supports anonymous authentication' % (config.get('server', '')))) # TODO msg
                return None
        else:
            log.error('Non-anonymous connections not handled currently')
            return None

    def register_handlers(self):
        """
        register handlers from xmpppy signals
        """
        self.client.RegisterHandler('iq', self.on_get_time, typ='get', ns="urn:xmpp:time")
        self.client.RegisterHandler('iq', self.on_get_version, typ='get', ns=xmpp.NS_VERSION)
        self.client.RegisterHandler('presence', self.handler_presence)
        self.client.RegisterHandler('message', self.handler_message)
        # self.client.RegisterHandler('message', self.handler_delayed_message, ns=xmpp.NS_DELAY)

    def handler_presence(self, connection, presence):
        fro = presence.getFrom()
        to = presence.getAttr('to')
        if fro == to:           # own presence
            self.online = 2
            self.jid = to
            self.handler.emit('on-connected', jid=fro)
            return
        self.handler.emit('room-presence', stanza=presence)
        raise xmpp.protocol.NodeProcessed

    def handler_delayed_message(self, connection, message):
        self.handler.emit('room-delayed-message', stanza=message)
        raise xmpp.protocol.NodeProcessed

    def handler_message(self, connection, message):
        self.handler.emit('room-message', stanza=message)
        raise xmpp.protocol.NodeProcessed

    def handler_error(self, connection, error):
        pass

    def process(self, timeout=10):
        if self.online:
            self.client.Process(timeout)
        else:
            log.warning('disconnecting...')
            sys.exit()

    def on_get_version(self, connection, iq):
        self.handler.emit('send-version', iq_obj=iq)

    def on_get_time(self, connection, iq):
        self.handler.emit('send-time', iq_obj=iq)
