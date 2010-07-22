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

"""
Defines the Connection class
"""

from gettext import (bindtextdomain, textdomain, bind_textdomain_codeset,
                     gettext as _)

import sys
import threading

import xmpp
from config import config
from logging import logger
from handler import Handler
from common import jid_get_node, jid_get_domain, is_jid_the_same

class Connection(threading.Thread):
    """
    Receives everything from Jabber and emits the
    appropriate signals
    """
    def __init__(self, server, resource):
        threading.Thread.__init__(self)
        self.handler = Handler()
        self.daemon = True      # exit the program when this thread exits
        if config.get('jid', '') == '':
            self.server = server
        else:
            self.server = jid_get_domain(config.get('jid', ''))
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
            self.handler.emit('error', msg='Could not connect to server')
            sys.exit(-1)
        if not self.authenticate(config.get('jid', '') == ''):
            self.handler.emit('error', msg='Could not authenticate to server')
            sys.exit(-1)
        # TODO, become invisible before sendInitPresence
        self.client.sendInitPresence(requestRoster=0)
        self.online = 1      # 2 when confirmation of our auth is received
        self.register_handlers()
        while 1:
            self.process()

    def connect_to_server(self, server, port):
        """
        Connect to the server
        """
        if config.get('use_proxy','false') == 'true':
            return self.client.connect((server, port),
                                       {'host': config.get("proxy_server", ""),
                                        'port': config.get("proxy_port", 1080),
                                        'user': config.get("proxy_user", ""),
                                        'password': config.get("proxy_password",
                                                               "")
                                        })
        else:
            return self.client.connect((server, port))

    def authenticate(self, anon=True):
        """
        Authenticate to the server
        """
        if anon:
            try:
                self.client.auth(None, "", self.resource)
                return True
            except TypeError:
                self.handler.emit('error', msg=_('Error: Could not authenticate. Please make sure the server you chose (%s) supports anonymous authentication' % (config.get('server', ''))))
                return False
        else:
            password = config.get('password', '')
            jid = config.get('jid', '')
            auth = self.client.auth(jid_get_node(jid), password, "salut")
            return True

    def register_handlers(self):
        """
        registers handlers from xmpppy signals
        """
        self.client.RegisterHandler('iq', self.on_get_time, typ='get',
                                    ns="urn:xmpp:time")
        self.client.RegisterHandler('iq', self.on_get_version, typ='get',
                                    ns=xmpp.NS_VERSION)
        self.client.RegisterHandler('presence', self.handler_presence)
        self.client.RegisterHandler('message', self.handler_message)

    def error_message(self, stanza):
        """
        handles the error messages
        """
        room_name = stanza.getFrom().getStripped()
        self.handler.emit('error-message', room=room_name,
                          error=stanza.getTag('error'),
                          msg=stanza.getError())
        raise xmpp.protocol.NodeProcessed

    def handler_presence(self, connection, presence):
        """
        check if it's a normal or a muc presence
        """
        is_muc = False
        tags = presence.getTags('x')
        for tag in tags:
            if tag.getAttr('xmlns') == 'http://jabber.org/protocol/muc#user':
                is_muc = True
        if is_muc:
            self.handler_muc_presence(connection, presence)
        else:
            self.handler_normal_presence(connection, presence)

    def handler_normal_presence(self, connection, presence):
        """
        """
        fro = presence.getFrom()
        toj = presence.getAttr('to')
        if presence.getType() == 'error':
            self.error_message(presence)
            return
        if fro == toj:           # own presence
            self.online = 2
            self.jid = toj
            self.handler.emit('on-connected', jid=fro)

    def handler_muc_presence(self, connection, presence):
        """
        handles the presence messages
        """
        if not connection:
            return
        self.handler.emit('room-presence', stanza=presence)
        raise xmpp.protocol.NodeProcessed

    def handler_delayed_message(self, connection, message):
        """
        handles the delayed messages
        These are received when we join a muc and we are sent the
        recent history
        """
        if not connection:
            return
        self.handler.emit('room-delayed-message', stanza=message)
        raise xmpp.protocol.NodeProcessed

    def handler_message(self, connection, message):
        """
        handles the common messages
        """
        if not connection:
            return
        if message.getType() == 'error':
            self.error_message(message)
            return
        if message.getType() == 'groupchat':
            self.handler.emit('room-message', stanza=message)
        else:
            self.handler.emit('private-message', stanza=message)

        raise xmpp.protocol.NodeProcessed

    def process(self, timeout=10):
        """
        Main connection loop
        It just waits for something to process (something is received
        or something has to be sent)
        """
        if self.online:
            self.client.Process(timeout)
        else:
            logger.warning('disconnecting...')
            sys.exit()

    def on_get_version(self, connection, iq):
        """
        Handles the iq requesting our software version
        """
        if not connection:
            return
        self.handler.emit('send-version', iq_obj=iq)

    def on_get_time(self, connection, iq):
        """
        handles the iq requesting our  time
        """
        if not connection:
            return
        self.handler.emit('send-time', iq_obj=iq)
