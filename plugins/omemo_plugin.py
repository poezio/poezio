#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2018 Maxime “pep” Buquet <pep@bouah.net>
#
# Distributed under terms of the zlib license.
"""
    OMEMO Plugin.
"""

import os
import asyncio
import textwrap
from poezio.plugin import BasePlugin
from poezio.tabs import ConversationTab
from poezio.xdg import CACHE_HOME
from slixmpp.plugins.xep_0384.plugin import MissingOwnKey

import logging
log = logging.getLogger(__name__)

class Plugin(BasePlugin):
    def init(self):
        self.info = lambda i: self.api.information(i, 'Info')
        self.xmpp = self.core.xmpp

        cache_dir = os.path.join(CACHE_HOME, 'omemo')
        os.makedirs(cache_dir, exist_ok=True)

        self.xmpp.register_plugin(
            'xep_0384', {
                'cache_dir': cache_dir,
            })

        self.api.add_command(
            'omemo',
            self.command_status,
            help='Display contextual information status',
        )

        self.api.add_tab_command(
            ConversationTab,
            'omemo_enable',
            self.command_enable,
            help='Enable OMEMO encryption',
        )

        self.api.add_tab_command(
            ConversationTab,
            'omemo_disable',
            self.command_disable,
            help='Disable OMEMO encryption',
        )

        self.api.add_tab_command(
            ConversationTab,
            'omemo_toggle',
            self.command_toggle,
            help='Toggle OMEMO encryption state',
        )

        self.api.add_command(
            'omemo_clear_devices',
            self.command_clear_devices,
            help='Clear all other OMEMO devices',
        )

        self.api.add_event_handler(
            'conversation_say_after',
            self.on_conversation_say_after,
        )

        self.api.add_event_handler(
            'conversation_msg',
            self.on_conversation_msg,
        )

    def command_status(self, _args):
        """Display contextual information depending on currenttab."""
        tab = self.api.current_tab()
        self.info('OMEMO!')
        self.info("My device id: %d" % self.xmpp['xep_0384'].my_device_id())

    def command_enable(self, _args):
        pass

    def command_disable(self, args):
        pass

    def command_toggle(self, _args):
        pass

    def command_clear_devices(self, _args):
        asyncio.ensure_future(self.xmpp['xep_0384'].clear_device_list())
        info = """
        Device list has been reset.
        Your other devices will reannounce themselves next time they get
        online, but they might not be able to read encrypted messages in the
        meantime.
        """
        self.info(textwrap.dedent(info).strip())

    def on_conversation_say_after(self, message, tab):
        """
        Outbound messages
        """

        # Check encryption status globally and to the contact, if enabled, add
        # ['omemo_encrypt'] attribute to message and send. Maybe delete
        # ['body'] and tab.add_message ourselves to specify typ=0 so messages
        # are not logged.

        fromjid = message['from']
        self.xmpp['xep_0384'].encrypt_message(message)
        self.info('Foo1')

    def on_conversation_msg(self, message, _tab):
        """
        Inbound messages
        """

        # Check if encrypted, and if so replace message['body'] with
        # plaintext.

        self.info('Foo2')
        if self.xmpp['xep_0384'].is_encrypted(message):
            try:
                body = self.xmpp['xep_0384'].decrypt_message(message)
            except (MissingOwnKey,):
                log.debug("The following message is missing our key;"
                          "Couldn't decrypt: %r", message)
                return None
            message['body'] = body.decode("utf8")
