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
from typing import Callable, List, Optional, Set, Tuple, Union

from poezio.plugin import BasePlugin
from poezio.tabs import DynamicConversationTab, StaticConversationTab, ConversationTab, MucTab
from poezio.xdg import DATA_HOME

from slixmpp import JID
from slixmpp.stanza import Message
from slixmpp_omemo import PluginCouldNotLoad, MissingOwnKey, EncryptionPrepareException
import slixmpp_omemo

log = logging.getLogger(__name__)


class Plugin(BasePlugin):
    """OMEMO (XEP-0384) Plugin"""
    _enabled_jids = set()  # type: Set[JID]

    def init(self):
        self.info = lambda i: self.api.information(i, 'Info')
        self.xmpp = self.core.xmpp

        data_dir = os.path.join(DATA_HOME, 'omemo')
        os.makedirs(data_dir, exist_ok=True)

        try:
            self.xmpp.register_plugin(
                'xep_0384', {
                    'data_dir': data_dir,
                },
                module=slixmpp_omemo,
            ) # OMEMO
        except (PluginCouldNotLoad,):
            log.exception('And error occured when loading the omemo plugin.')
            return None

        self.api.add_command(
            'omemo',
            self.command_status,
            help='Display contextual information',
        )

        ConversationTab.add_information_element('omemo', self.display_encryption_status)
        MucTab.add_information_element('omemo', self.display_encryption_status)

        self.api.add_command(
            'omemo_enable',
            self.command_enable,
            help='Enable OMEMO encryption',
        )

        self.api.add_command(
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

    def cleanup(self) -> None:
        ConversationTab.remove_information_element('omemo')
        MucTab.remove_information_element('omemo')

    def display_encryption_status(self, jid: JID) -> str:
        """
            Return information to display in the infobar if OMEMO is enabled
            for the JID.
        """

        if jid in self._enabled_jids:
            return " OMEMO"
        return ""

    def command_status(self, _args):
        """Display contextual information depending on currenttab."""
        tab = self.api.current_tab()
        self.info("My device id: %d" % self.xmpp['xep_0384'].my_device_id())

    def _jid_from_context(self, jid: Optional[Union[str, JID]]) -> Tuple[Optional[JID], bool]:
        """
            Get bare JID from context if not specified

            Return a tuple with the JID and a bool specifying that the JID
            corresponds to the current tab.
        """

        tab = self.api.current_tab()

        tab_jid = None
        chat_tabs = (DynamicConversationTab, StaticConversationTab, ConversationTab, MucTab)
        if isinstance(tab, chat_tabs):
            tab_jid = JID(tab.name).bare

        # If current tab has a JID, use it if none is specified
        if not jid and tab_jid is not None:
            jid = tab_jid

        # We might not have found a JID at this stage. No JID provided and not
        # in a tab with a JID (InfoTab etc.).
        # If we do, make we
        if jid:
            # XXX: Ugly. We don't know if 'jid' is a str or a JID. And we want
            # to return a bareJID. We could change the JID API to allow us to
            # clear the resource one way or another.
            jid = JID(JID(jid).bare)
        else:
            jid = None

        return (jid, tab_jid is not None and tab_jid == jid)

    def command_enable(self, jid: Optional[str]) -> None:
        """
            Enable JID to use OMEMO with.

            Use current tab JID is none is specified. Refresh the tab if JID
            corresponds to the one being added.
        """

        jid, current_tab = self._jid_from_context(jid)
        if jid is None:
            return None

        if jid not in self._enabled_jids:
            self.info('OMEMO enabled for %s' % jid)
        self._enabled_jids.add(jid)

        # Refresh tab if JID matches
        if current_tab:
            self.api.current_tab().refresh()

        return None

    def command_disable(self, jid: Optional[str]) -> None:
        """
            Enable JID to use OMEMO with.

            Use current tab JID is none is specified. Refresh the tab if JID
            corresponds to the one being added.
        """

        jid, current_tab = self._jid_from_context(jid)
        if jid is None:
            return None

        if jid in self._enabled_jids:
            self.info('OMEMO disabled for %s' % jid)
        self._enabled_jids.remove(jid)

        # Refresh tab if JID matches
        if current_tab:
            self.api.current_tab().refresh()

        return None

    def send_message(self, _args):
        asyncio.ensure_future(
            self._send_encrypted_message(
                "Hello Encrypted World!",
                [JID('pep@bouah.net'), JID('test@bouah.net')],
                mto=JID('test@bouah.net'),
                mtype='chat',
            ),
        )

    async def _send_encrypted_message(
        self,
        payload: str,
        recipients: List[JID],
        mto: Optional[JID] = None,
        mtype: Optional[str] = 'chat',
    ) -> None:
        try:
            encrypted = await self.xmpp['xep_0384'].encrypt_message(payload, recipients)
        except EncryptionPrepareException as e:
            log.debug('Failed to encrypt message: %r', e)
            return None
        msg = self.core.xmpp.make_message(mto, mtype=mtype)
        msg['body'] = 'This message is encrypted with Legacy OMEMO (eu.siacs.conversations.axolotl)'
        msg['eme']['namespace'] = 'eu.siacs.conversations.axolotl'
        msg.append(encrypted)
        log.debug('BAR: message: %r', msg)
        msg.send()
        return None

    def on_conversation_say_after(
        self,
        message: Message,
        tabs: Union[DynamicConversationTab, StaticConversationTab, ConversationTab, MucTab],
    ) -> None:
        """
        Outbound messages
        """

        # Check encryption status with the contact, if enabled, add
        # ['omemo_encrypt'] attribute to message and send. Maybe delete
        # ['body'] and tab.add_message ourselves to specify typ=0 so messages
        # are not logged.

        fromjid = message['from']
        if fromjid not in self._enabled_jids:
            return None

        self.xmpp['xep_0384'].encrypt_message(message)
        return None

    def on_conversation_msg(self, message, _tab) -> None:
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
