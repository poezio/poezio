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
            jid = config.get('server', 'anon.jeproteste.info')
            if resource:
                jid = '%s/%s' % (jid, resource)
            password = None
        jid = safeJID(jid)
        # TODO: use the system language
        sleekxmpp.ClientXMPP.__init__(self, jid, password, lang=config.get('lang', 'en'))

        force_encryption = config.get('force_encryption', 'true').lower() != 'false'
        if force_encryption:
            self['feature_mechanisms'].unencrypted_plain = False
            self['feature_mechanisms'].unencrypted_digest = False
            self['feature_mechanisms'].unencrypted_cram = False
            self['feature_mechanisms'].unencrypted_scram = False

        self.core = None
        self.auto_reconnect = True if config.get('auto_reconnect', 'false').lower() in ('true', '1') else False
        self.reconnect_max_attempts = 0
        self.auto_authorize = None
        # prosody defaults, lowest is AES128-SHA, it should be a minimum
        # for anything that came out after 2002
        self.ciphers = config.get('ciphers', 'HIGH+kEDH:HIGH+kEECDH:HIGH:!PSK:!SRP:!3DES:!aNULL')
        self.ca_certs = config.get('ca_cert_path', '') or None
        interval = config.get('whitespace_interval', '300')
        if interval.isdecimal() and int(interval) > 0:
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
        self.register_plugin('xep_0066')
        self.register_plugin('xep_0071')
        self.register_plugin('xep_0077')
        self.plugin['xep_0077'].create_account = False
        self.register_plugin('xep_0085')
        self.register_plugin('xep_0115')
        self.register_plugin('xep_0191')
        self.register_plugin('xep_0199')
        self.set_keepalive_values()

        if config.get('enable_user_tune', 'true') != 'false':
            self.register_plugin('xep_0118')

        if config.get('enable_user_nick', 'true') != 'false':
            self.register_plugin('xep_0172')

        if config.get('enable_user_mood', 'true') != 'false':
            self.register_plugin('xep_0107')

        if config.get('enable_user_activity', 'true') != 'false':
            self.register_plugin('xep_0108')

        if config.get('enable_user_gaming', 'true') != 'false':
            self.register_plugin('xep_0196')

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
        self.register_plugin('xep_0280')
        self.register_plugin('xep_0297')
        self.register_plugin('xep_0308')

    def set_keepalive_values(self, option=None, value=None):
        """
        Called at startup, or triggered when one of
        "connection_timeout_delay" and "connection_check_interval" options
        is changed.
        Unload and reload the ping plugin, with the new values.
        """
        ping_interval = config.get('connection_check_interval', 60)
        timeout_delay = config.get('connection_timeout_delay', 10)
        if timeout_delay <= 0:
            # We help the stupid user (with a delay of 0, poezio will try to
            # reconnect immediately because the timeout is immediately
            # passed)
            # 1 second is short, but, well
            timeout_delay = 1
        self.plugin['xep_0199'].disable_keepalive()
        # If the ping_interval is 0 or less, we just disable the keepalive
        if ping_interval > 0:
            self.plugin['xep_0199'].enable_keepalive(ping_interval, timeout_delay)

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
