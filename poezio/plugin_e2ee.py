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

from typing import Callable, Dict, List, Optional, Union

from slixmpp import InvalidJID, JID, Message
from slixmpp.xmlstream import StanzaBase
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
    """Interface for E2EE plugins.

        This is a wrapper built on top of BasePlugin. It provides a base for
        End-to-end Encryption mechanisms in poezio.

        Plugin developers are excepted to implement the `decrypt` and
        `encrypt` function, provide an encryption name (and/or short name),
        and an eme namespace.

        Once loaded, the plugin will attempt to decrypt any message that
        contains an EME message that matches the one set.

        The plugin will also register a command (using the short name) to
        enable encryption per tab. It is only possible to have one encryption
        mechanism per tab, even if multiple e2ee plugins are loaded.

        The encryption status will be displayed in the status bar, using the
        plugin short name, alongside the JID, nickname etc.
    """

    #: Specifies that the encryption mechanism does more than encrypting
    #: `<body/>`.
    stanza_encryption = False

    #: Whitelist applied to messages when `stanza_encryption` is `False`.
    tag_whitelist = list(map(lambda x: '{%s}%s' % (x[0], x[1]), [
        (JCLIENT_NS, 'body'),
        (EME_NS, EME_TAG),
        (HINTS_NS, 'store'),
        (HINTS_NS, 'no-copy'),
        (HINTS_NS, 'no-store'),
        (HINTS_NS, 'no-permanent-store'),
        # TODO: Add other encryption mechanisms tags here
    ]))

    #: Replaces body with `eme <https://xmpp.org/extensions/xep-0380.html>`_
    #: if set. Should be suitable for most plugins except those using
    #: `<body/>` directly as their encryption container, like OTR, or the
    #: example base64 plugin in poezio.
    replace_body_with_eme = True

    #: Encryption name, used in command descriptions, and logs. At least one
    #: of `encryption_name` and `encryption_short_name` must be set.
    encryption_name = None  # type: Optional[str]

    #: Encryption short name, used as command name, and also to display
    #: encryption status in a tab. At least one of `encryption_name` and
    #: `encryption_short_name` must be set.
    encryption_short_name = None  # type: Optional[str]

    #: Required. https://xmpp.org/extensions/xep-0380.html.
    eme_ns = None  # type: Optional[str]

    #: Used to figure out what messages to attempt decryption for. Also used
    #: in combination with `tag_whitelist` to avoid removing encrypted tags
    #: before sending.
    encrypted_tags = None  # type: Optional[List[Tuple[str, str]]]

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
        # Using a stream filter might be a bit too much, but at least we're
        # sure poezio is not sneaking anything past us.
        self.core.xmpp.add_filter('out', self._encrypt)

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

        has_eme = False
        if message.xml.find('{%s}%s' % (EME_NS, EME_TAG)) is not None and \
            message['eme']['namespace'] == self.eme_ns:
            has_eme = True

        has_encrypted_tag = False
        if not has_eme and self.encrypted_tags is not None:
            for (namespace, tag) in self.encrypted_tags:
                if message.xml.find('{%s}%s' % (namespace, tag)) is not None:
                    has_encrypted_tag = True
                    break

        if not has_eme and not has_encrypted_tag:
            return None

        log.debug('Received %s message: %r', self.encryption_name, message['body'])

        self.decrypt(message, tab)

        log.debug('Decrypted %s message: %r', self.encryption_name, message['body'])
        return None

    def _encrypt(self, stanza: StanzaBase) -> Optional[StanzaBase]:
        if not isinstance(stanza, Message) or stanza['type'] not in ('chat', 'groupchat'):
            return stanza
        message = stanza

        tab = self.api.current_tab()
        jid = tab.jid
        if not self._encryption_enabled(jid):
            return message

        log.debug('Sending %s message: %r', self.encryption_name, message)

        has_body = message.xml.find('{%s}%s' % (JCLIENT_NS, 'body')) is not None

        # Drop all messages that don't contain a body if the plugin doesn't do
        # Stanza Encryption
        if not self.stanza_encryption and not has_body:
            log.debug(
                '%s plugin: Dropping message as it contains no body, and is '
                'not doesn\'t do stanza encryption: %r',
                self.encryption_name,
                message,
            )
            return None

        # Call the enabled encrypt method
        self._enabled_tabs[jid](message, tab)

        if has_body:
            # Only add EME tag if the message has a body.
            # Per discussion in jdev@:
            # The receiving client needs to know the message contains
            # meaningful information or not to display notifications to the
            # user, and not display anything when it's e.g., a chatstate.
            # This does leak the fact that the encrypted payload contains a
            # message.
            message['eme']['namespace'] = self.eme_ns
            message['eme']['name'] = self.encryption_name

            if self.replace_body_with_eme:
                self.core.xmpp['xep_0380'].replace_body_with_eme(message)

        # Filter stanza with the whitelist. Plugins doing stanza encryption
        # will have to include these in their encrypted container beforehand.
        whitelist = self.tag_whitelist
        if self.encrypted_tags is not None:
            whitelist += self.encrypted_tags

        for elem in message.xml[:]:
            if elem.tag not in whitelist:
                message.xml.remove(elem)

        log.debug('Encrypted %s message: %r', self.encryption_name, message)
        return message

    def decrypt(self, _message: Message, tab: ChatTabs):
        """Decryption method

        This is a method the plugin must implement.  It is expected that this
        method will edit the received message and return nothing.

        :param message: Message to be decrypted.
        :param tab: Tab the message is coming from.

        :returns: None
        """

        raise NotImplementedError

    def encrypt(self, _message: Message, tab: ChatTabs):
        """Encryption method

        This is a method the plugin must implement.  It is expected that this
        method will edit the received message and return nothing.

        :param message: Message to be encrypted.
        :param tab: Tab the message is going to.

        :returns: None
        """

        raise NotImplementedError
