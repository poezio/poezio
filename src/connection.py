# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Defines the Connection class
"""

import logging
log = logging.getLogger(__name__)

from gettext import (bindtextdomain, textdomain, bind_textdomain_codeset,
                     gettext as _)

import getpass
import sys
import sleekxmpp

from config import config, options
from logger import logger
import common
from common import safeJID

class Connection(sleekxmpp.ClientXMPP):
    """
    Receives everything from Jabber and emits the
    appropriate signals
    """
    __init = False
    def __init__(self):
        resource = config.get('resource', '')
        if config.get('jid', ''):
            self.anon = False # Field used to know if we are anonymous or not.
            # many features will be handled diferently
            # depending on this setting
            jid = '%s' % config.get('jid', '')
            if resource:
                jid = '%s/%s'% (jid, resource)
            password = config.get('password', '') or getpass.getpass()
        else: # anonymous auth
            self.anon = True
            jid = config.get('server', 'anon.louiz.org')
            if resource:
                jid = '%s/%s' % (jid, resource)
            password = None
        jid = safeJID(jid)
        # TODO: use the system language
        sleekxmpp.ClientXMPP.__init__(self, jid, password, lang=config.get('lang', 'en'))
        self.core = None
        self.auto_reconnect = True if config.get('auto_reconnect', 'false').lower() in ('true', '1') else False
        self.reconnect_max_attempts = 0
        self.auto_authorize = None
        self.ca_certs = config.get('ca_cert_path', '') or None
        interval = config.get('whitespace_interval', '300')
        if interval.isnumeric():
            self.whitespace_keepalive_interval = int(interval)
        else:
            self.whitespace_keepalive_interval = 300
        # Hack to check the sleekxmpp version
        # TODO: Remove that when a sufficient time has passed since the move
        self.register_plugin('xep_0004')
        self.register_plugin('xep_0012')
        self.register_plugin('xep_0030')
        self.register_plugin('xep_0045')
        self.register_plugin('xep_0048')
        self.register_plugin('xep_0060')
        self.register_plugin('xep_0071')
        self.register_plugin('xep_0085')
        self.register_plugin('xep_0115')
        self.register_plugin('xep_0191')

        if config.get('receive_user_tune', 'true') != 'false':
            self.register_plugin('xep_0118')
        if config.get('use_pep_nick', 'true') != 'false':
            self.register_plugin('xep_0172')
        if config.get('send_poezio_info', 'true') == 'true':
            info = {'name':'poezio',
                    'version': options.version}
            if config.get('send_os_info', 'true') == 'true':
                info['os'] = common.get_os_info()
            self.plugin['xep_0030'].set_identities(identities=set([('client', 'pc', None,'Poezio')]))
        else:
            info = {'name': '', 'version': ''}
            self.plugin['xep_0030'].set_identities(identities=set([('client', 'pc', None,'')]))
        self.register_plugin('xep_0092', pconfig=info)
        if config.get('send_time', 'true') == 'true':
            self.register_plugin('xep_0202')
        self.register_plugin('xep_0224')
        self.register_plugin('xep_0308')

        self.plugin['xep_0115'].update_caps()

    def start(self):
        # TODO, try multiple servers
        # With anon auth.
        # (domain, config.get('port', 5222))
        custom_host = config.get('custom_host', '')
        custom_port = config.get('custom_port', 5222)
        if custom_port == -1:
            custom_port = 5222
        if custom_host:
            res = self.connect((custom_host, custom_port), reattempt=True)
        elif custom_port != 5222 and custom_port != -1:
            res = self.connect((self.boundjid.host, custom_port), reattempt=True)
        else:
            res = self.connect(reattempt=True)
        if not res:
            return False
        self.process(threaded=True)
        return True

    def send_raw(self, data, now=False, reconnect=None):
        """
        Overrides XMLStream.send_raw, with an event added
        """
        if self.core:
            self.core.outgoing_stanza(data)
        sleekxmpp.ClientXMPP.send_raw(self, data, now, reconnect)

class MatchAll(sleekxmpp.xmlstream.matcher.base.MatcherBase):
    """
    Callback to retrieve all the stanzas for the XML tab
    """
    def match(self, xml):
        return True
