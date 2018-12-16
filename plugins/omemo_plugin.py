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
import logging
from typing import List, Optional

from poezio.plugin import BasePlugin
from poezio.tabs import ConversationTab
from poezio.xdg import DATA_HOME

from slixmpp import JID
from slixmpp.plugins.xep_0384.plugin import MissingOwnKey

log = logging.getLogger(__name__)


class Plugin(BasePlugin):
    """OMEMO (XEP-0384) Plugin"""

    def init(self):
        self.info = lambda i: self.api.information(i, 'Info')
        self.xmpp = self.core.xmpp

        data_dir = os.path.join(DATA_HOME, 'omemo')
        os.makedirs(data_dir, exist_ok=True)

        self.xmpp.register_plugin(
            'xep_0384', {
                'data_dir': data_dir,
            })

        self.api.add_command(
            'omemo',
            self.command_status,
            help='Display contextual information',
        )

        ConversationTab.add_information_element('omemo', self.display_encryption_status)
        # Waiting for https://lab.louiz.org/poezio/poezio/merge_requests/17
        # MucTab.add_information_element('omemo', self.display_encryption_status)

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

        self.api.add_command(
            'encrypted_message',
            self.send_message,
            help='Send OMEMO encrypted message',
        )

        self.api.add_event_handler(
            'conversation_say_after',
            self.on_conversation_say_after,
        )

        self.api.add_event_handler(
            'conversation_msg',
            self.on_conversation_msg,
        )

    def display_encryption_status(self, *_args):
        return " OMEMO"

    def command_status(self, _args):
        """Display contextual information depending on currenttab."""
        tab = self.api.current_tab()
        self.info('OMEMO!')
        self.info("My device id: %d" % self.xmpp['xep_0384'].my_device_id())

    def command_enable(self, _args):
        pass

    def command_disable(self, args):
        pass

    def send_message(self, _args):
        asyncio.ensure_future(
            self._send_message(
                "Hello Encrypted World!",
                [JID('some@jid')],
                mto=JID('some@jid'),
                mtype='chat',
            ),
        )

    async def _send_message(
        self,
        payload: str,
        recipients: List[JID],
        mto: Optional[JID] = None,
        mtype: Optional[str] = 'chat',
    ) -> None:
        encrypted = await self.xmpp['xep_0384'].encrypt_message(payload, recipients)
        msg = self.core.xmpp.make_message(mto, mtype=mtype)
        msg['body'] = 'This message is encrypted with Legacy OMEMO (eu.siacs.conversations.axolotl)'
        msg['eme']['namespace'] = 'eu.siacs.conversations.axolotl'
        msg.append(encrypted)
        log.debug('BAR: message: %r', msg)
        msg.send()

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
            return None
