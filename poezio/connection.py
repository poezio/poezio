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

import getpass
import subprocess
import sys
import base64
import random

import slixmpp
from slixmpp.xmlstream import ET
from slixmpp.plugins.xep_0184 import XEP_0184
from slixmpp.plugins.xep_0030 import DiscoInfo
from slixmpp.util import FileSystemCache

from poezio import common
from poezio import fixes
from poezio import xdg
from poezio.common import safeJID
from poezio.config import config, options


class Connection(slixmpp.ClientXMPP):
    """
    Receives everything from Jabber and emits the
    appropriate signals
    """
    __init = False

    def __init__(self):
        keyfile = config.get('keyfile')
        certfile = config.get('certfile')

        device_id = config.get('device_id')
        if not device_id:
            rng = random.SystemRandom()
            device_id = base64.urlsafe_b64encode(
                rng.getrandbits(24).to_bytes(3, 'little')).decode('ascii')
            config.set_and_save('device_id', device_id)

        if config.get('jid'):
            # Field used to know if we are anonymous or not.
            # many features will be handled differently
            # depending on this setting
            self.anon = False
            jid = config.get('jid')
            password = config.get('password')
            eval_password = config.get('eval_password')
            if not password and not eval_password and not (keyfile
                                                           and certfile):
                password = getpass.getpass()
            elif not password and not (keyfile and certfile):
                sys.stderr.write(
                    "No password or certificates provided, using the eval_password command.\n"
                )
                process = subprocess.Popen(
                    ['sh', '-c', eval_password],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    close_fds=True)
                code = process.wait()
                if code != 0:
                    sys.stderr.write(
                        'The eval_password command (%s) returned a '
                        'nonzero status code: %s.\n' % (eval_password, code))
                    sys.stderr.write('Poezio will now exit\n')
                    sys.exit(code)
                password = process.stdout.readline().decode('utf-8').strip(
                    '\n')
        else:  # anonymous auth
            self.anon = True
            jid = config.get('server')
            password = None
        jid = safeJID(jid)
        jid.resource = '%s-%s' % (
            jid.resource,
            device_id) if jid.resource else 'poezio-%s' % device_id
        # TODO: use the system language
        slixmpp.ClientXMPP.__init__(
            self, jid, password, lang=config.get('lang'))

        force_encryption = config.get('force_encryption')
        if force_encryption:
            self['feature_mechanisms'].unencrypted_plain = False
            self['feature_mechanisms'].unencrypted_digest = False
            self['feature_mechanisms'].unencrypted_cram = False
            self['feature_mechanisms'].unencrypted_scram = False

        self.keyfile = config.get('keyfile')
        self.certfile = config.get('certfile')
        if keyfile and not certfile:
            log.error(
                'keyfile is present in configuration file without certfile')
        elif certfile and not keyfile:
            log.error(
                'certfile is present in configuration file without keyfile')

        self.core = None
        self.auto_reconnect = config.get('auto_reconnect')
        self.auto_authorize = None
        # prosody defaults, lowest is AES128-SHA, it should be a minimum
        # for anything that came out after 2002
        self.ciphers = config.get(
            'ciphers', 'HIGH+kEDH:HIGH+kEECDH:HIGH:!PSK'
            ':!SRP:!3DES:!aNULL')
        self.ca_certs = config.get('ca_cert_path') or None
        interval = config.get('whitespace_interval')
        if int(interval) > 0:
            self.whitespace_keepalive_interval = int(interval)
        else:
            self.whitespace_keepalive = False
        self.register_plugin('xep_0004')
        self.register_plugin('xep_0012')
        # Must be loaded before 0030.
        self.register_plugin(
            'xep_0115', {
                'caps_node':
                'https://poez.io',
                'cache':
                FileSystemCache(
                    str(xdg.CACHE_HOME),
                    'caps',
                    encode=str,
                    decode=lambda x: DiscoInfo(ET.fromstring(x))),
            })
        self.register_plugin('xep_0030')
        self.register_plugin('xep_0045')
        self.register_plugin('xep_0048')
        self.register_plugin('xep_0050')
        self.register_plugin('xep_0054')
        self.register_plugin('xep_0060')
        self.register_plugin('xep_0066')
        self.register_plugin('xep_0070')
        self.register_plugin('xep_0071')
        self.register_plugin('xep_0077')
        self.plugin['xep_0077'].create_account = False
        self.register_plugin('xep_0084')
        self.register_plugin('xep_0085')
        self.register_plugin('xep_0153')

        # monkey-patch xep_0184 to avoid requesting receipts for messages
        # without a body
        XEP_0184._filter_add_receipt_request = fixes._filter_add_receipt_request
        self.register_plugin('xep_0184')
        self.plugin['xep_0184'].auto_ack = config.get('ack_message_receipts')
        self.plugin['xep_0184'].auto_request = config.get(
            'request_message_receipts')

        self.register_plugin('xep_0191')
        if config.get('enable_smacks'):
            self.register_plugin('xep_0198')
        self.register_plugin('xep_0199')

        if config.get('enable_user_tune'):
            self.register_plugin('xep_0118')

        if config.get('enable_user_nick'):
            self.register_plugin('xep_0172')

        if config.get('enable_user_mood'):
            self.register_plugin('xep_0107')

        if config.get('enable_user_activity'):
            self.register_plugin('xep_0108')

        if config.get('enable_user_gaming'):
            self.register_plugin('xep_0196')

        if config.get('send_poezio_info'):
            info = {'name': 'poezio', 'version': options.version}
            if config.get('send_os_info'):
                info['os'] = common.get_os_info()
            self.plugin['xep_0030'].set_identities(identities={('client',
                                                                'console',
                                                                None,
                                                                'Poezio')})
        else:
            info = {'name': '', 'version': ''}
            self.plugin['xep_0030'].set_identities(identities={('client',
                                                                'console',
                                                                None, '')})
        self.register_plugin('xep_0092', pconfig=info)
        if config.get('send_time'):
            self.register_plugin('xep_0202')
        self.register_plugin('xep_0224')
        self.register_plugin('xep_0231')
        self.register_plugin('xep_0249')
        self.register_plugin('xep_0257')
        self.register_plugin('xep_0280')
        self.register_plugin('xep_0297')
        self.register_plugin('xep_0308')
        self.register_plugin('xep_0319')
        self.register_plugin('xep_0334')
        self.register_plugin('xep_0352')
        try:
            self.register_plugin('xep_0363')
        except SyntaxError:
            log.error('Failed to load HTTP File Upload plugin, it can only be '
                      'used on Python 3.5+')
        except slixmpp.plugins.base.PluginNotFound:
            log.error('Failed to load HTTP File Upload plugin, it can only be '
                      'used with aiohttp installed')
        self.register_plugin('xep_0380')
        self.init_plugins()

    def set_keepalive_values(self, option=None, value=None):
        """
        Called after the XMPP session has been started, or triggered when one of
        "connection_timeout_delay" and "connection_check_interval" options
        is changed.  Unload and reload the ping plugin, with the new values.
        """
        if not self.is_connected():
            # Happens when we change the value with /set while we are not
            # connected. Do nothing in that case
            return
        ping_interval = config.get('connection_check_interval')
        timeout_delay = config.get('connection_timeout_delay')
        if timeout_delay <= 0:
            # We help the stupid user (with a delay of 0, poezio will try to
            # reconnect immediately because the timeout is immediately
            # passed)
            # 1 second is short, but, well
            timeout_delay = 1
        self.plugin['xep_0199'].disable_keepalive()
        # If the ping_interval is 0 or less, we just disable the keepalive
        if ping_interval > 0:
            self.plugin['xep_0199'].enable_keepalive(ping_interval,
                                                     timeout_delay)

    def start(self):
        """
        Connect and process events.
        """
        custom_host = config.get('custom_host')
        custom_port = config.get('custom_port', 5222)
        if custom_port == -1:
            custom_port = 5222
        if custom_host:
            self.connect((custom_host, custom_port))
        elif custom_port != 5222 and custom_port != -1:
            self.connect((self.boundjid.host, custom_port))
        else:
            self.connect()

    def send_raw(self, data):
        """
        Overrides XMLStream.send_raw, with an event added
        """
        if self.core:
            self.core.handler.outgoing_stanza(data)
        slixmpp.ClientXMPP.send_raw(self, data)


class MatchAll(slixmpp.xmlstream.matcher.base.MatcherBase):
    """
    Callback to retrieve all the stanzas for the XML tab
    """

    def match(self, xml):
        "match everything"
        return True
