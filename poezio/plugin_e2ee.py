#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8 et ts=4 sts=4 sw=4
#
# Copyright © 2019 Maxime “pep” Buquet <pep@bouah.net>
#
# Distributed under terms of the zlib license. See COPYING file.

"""
    Interface for E2EE (End-to-end Encryption) plugins.
"""

from typing import Callable, Dict, Optional, Union

from slixmpp import InvalidJID, JID, Message
from poezio.tabs import ConversationTab, DynamicConversationTab, PrivateTab, MucTab
from poezio.plugin import BasePlugin

import logging
log = logging.getLogger(__name__)


ChatTabs = Union[
    MucTab,
    DynamicConversationTab,
    PrivateTab,
]

EME_NS = 'urn:xmpp:eme:0'
EME_TAG = 'encryption'

JCLIENT_NS = 'jabber:client'
HINTS_NS = 'urn:xmpp:hints'


class E2EEPlugin(BasePlugin):
    """Interface for E2EE plugins"""

    # Specifies that the encryption mechanism does more than encrypting
    # <body/>.
    stanza_encryption = False

    # Whitelist applied to messages when `stanza_encryption` is False.
    tag_whitelist = list(map(lambda x: '{%s}%s' % (x[0], x[1]), [
        (EME_NS, EME_TAG),
        (HINTS_NS, 'store'),
        (HINTS_NS, 'no-copy'),
        (HINTS_NS, 'no-store'),
        (HINTS_NS, 'no-permanent-store'),
    ]))

    replace_body_with_eme = True

    # At least one of encryption_name and encryption_short_name must be set
    encryption_name = None  # type: Optional[str]
    encryption_short_name = None  # type: Optional[str]

    # Required.
    eme_ns = None  # type: Optional[str]

    # Static map, to be able to limit to one encryption mechanism per tab at a
    # time
    _enabled_tabs = {}  # type: Dict[JID, Callable]

    def init(self):
        if self.encryption_name is None and self.encryption_short_name is None:
            raise NotImplementedError

        if self.eme_ns is None:
            raise NotImplementedError

        if self.encryption_name is None:
            self.encryption_name = self.encryption_short_name
        if self.encryption_short_name is None:
            self.encryption_short_name = self.encryption_name

        # Ensure decryption is done before everything, so that other handlers
        # don't have to know about the encryption mechanism.
        self.api.add_event_handler('muc_msg', self._decrypt, priority=0)
        self.api.add_event_handler('conversation_msg', self._decrypt, priority=0)
        self.api.add_event_handler('private_msg', self._decrypt, priority=0)

        # Ensure encryption is done after everything, so that whatever can be
        # encrypted is encrypted, and no plain element slips in.
        self.api.add_event_handler('muc_say', self._encrypt, priority=100)
        self.api.add_event_handler('conversation_say', self._encrypt, priority=100)
        self.api.add_event_handler('private_say', self._encrypt, priority=100)

        for tab_t in (DynamicConversationTab, PrivateTab, MucTab):
            self.api.add_tab_command(
                tab_t,
                self.encryption_short_name,
                self._toggle_tab,
                usage='',
                short='Toggle {} encryption for tab.'.format(self.encryption_name),
                help='Toggle automatic {} encryption for tab.'.format(self.encryption_name),
            )

        ConversationTab.add_information_element(
            self.encryption_short_name,
            self._display_encryption_status,
        )
        MucTab.add_information_element(
            self.encryption_short_name,
            self._display_encryption_status,
        )
        PrivateTab.add_information_element(
            self.encryption_short_name,
            self._display_encryption_status,
        )

    def cleanup(self):
        ConversationTab.remove_information_element(self.encryption_short_name)
        MucTab.remove_information_element(self.encryption_short_name)
        PrivateTab.remove_information_element(self.encryption_short_name)

    def _display_encryption_status(self, jid_s: str) -> str:
        """
            Return information to display in the infobar if encryption is
            enabled for the JID.
        """

        try:
            jid = JID(jid_s)
        except InvalidJID:
            return ""

        if self._encryption_enabled(jid):
            return " " + self.encryption_short_name
        return ""

    def _toggle_tab(self, _input: str) -> None:
        jid = self.api.current_tab().jid  # type: JID

        if self._encryption_enabled(jid):
            del self._enabled_tabs[jid]
            self.api.information(
                '{} encryption disabled for {}'.format(self.encryption_name, jid),
                'Info',
            )
        else:
            self._enabled_tabs[jid] = self.encrypt
            self.api.information(
                '{} encryption enabled for {}'.format(self.encryption_name, jid),
                'Info',
            )

    def _encryption_enabled(self, jid: JID) -> bool:
        return jid in self._enabled_tabs and self._enabled_tabs[jid] == self.encrypt

    def _decrypt(self, message: Message, tab: ChatTabs) -> None:
        if message.xml.find('{%s}%s' % (EME_NS, EME_TAG)) is None:
            return None

        if message['eme']['namespace'] != self.eme_ns:
            return None

        log.debug('Received %s message: %r', self.encryption_name, message['body'])

        self.decrypt(message, tab)

        log.debug('Decrypted %s message: %r', self.encryption_name, message['body'])
        return None

    def _encrypt(self, message: Message, tab: ChatTabs):
        jid = tab.jid
        if not self._encryption_enabled(jid):
            return None

        log.debug('Sending %s message: %r', self.encryption_name, message['body'])

        message['eme']['namespace'] = self.eme_ns
        message['eme']['name'] = self.encryption_name

        # Call the enabled encrypt method
        self._enabled_tabs[jid](message, tab)

        # Filter stanza with the whitelist if we don't do stanza encryption
        if not self.stanza_encryption:
            for elem in message.xml[:]:
                if elem.tag not in self.tag_whitelist:
                    message.xml.remove(elem)

        if self.replace_body_with_eme:
            body = message.xml.find('{%s}%s' % (JCLIENT_NS, 'body'))
            if body is not None:
                self.core.xmpp['xep_0380'].replace_body_with_eme(message)

        log.debug('Decrypted %s message: %r', self.encryption_name, message['body'])
        return None

    def decrypt(self, _message: Message, tab: ChatTabs):
        """Decryption method"""
        raise NotImplementedError

    def encrypt(self, _message: Message, tab: ChatTabs):
        """Encryption method"""
        raise NotImplementedError