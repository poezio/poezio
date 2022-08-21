#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8 et ts=4 sts=4 sw=4
#
# Copyright © 2019 Maxime “pep” Buquet <pep@bouah.net>
#
# Distributed under terms of the GPL-3.0+ license. See COPYING file.

"""
    Interface for E2EE (End-to-end Encryption) plugins.
"""

from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Set,
    Type,
)

from slixmpp import InvalidJID, JID, Message
from slixmpp.xmlstream import StanzaBase
from slixmpp.xmlstream.handler import CoroutineCallback
from slixmpp.xmlstream.matcher import MatchXPath
from poezio.tabs import (
    ChatTab,
    ConversationTab,
    DynamicConversationTab,
    MucTab,
    PrivateTab,
    RosterInfoTab,
    StaticConversationTab,
)
from poezio.plugin import BasePlugin
from poezio.theming import Theme, get_theme, dump_tuple
from poezio.config import config
from poezio.decorators import command_args_parser

import asyncio
from asyncio import iscoroutinefunction

import logging
log = logging.getLogger(__name__)


ChatTabs = Union[
    MucTab,
    DynamicConversationTab,
    StaticConversationTab,
    PrivateTab,
]

EME_NS = 'urn:xmpp:eme:0'
EME_TAG = 'encryption'

JCLIENT_NS = 'jabber:client'
HINTS_NS = 'urn:xmpp:hints'

class NothingToEncrypt(Exception):
    """
    Exception to raise inside the _encrypt filter on stanzas that do not need
    to be processed.
    """


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
    tag_whitelist = [
        (JCLIENT_NS, 'body'),
        (EME_NS, EME_TAG),
        (HINTS_NS, 'store'),
        (HINTS_NS, 'no-copy'),
        (HINTS_NS, 'no-store'),
        (HINTS_NS, 'no-permanent-store'),
        # TODO: Add other encryption mechanisms tags here
    ]

    #: Replaces body with `eme <https://xmpp.org/extensions/xep-0380.html>`_
    #: if set. Should be suitable for most plugins except those using
    #: `<body/>` directly as their encryption container, like OTR, or the
    #: example base64 plugin in poezio.
    replace_body_with_eme = True

    #: Encryption name, used in command descriptions, and logs. At least one
    #: of `encryption_name` and `encryption_short_name` must be set.
    encryption_name: Optional[str] = None

    #: Encryption short name, used as command name, and also to display
    #: encryption status in a tab. At least one of `encryption_name` and
    #: `encryption_short_name` must be set.
    encryption_short_name: Optional[str] = None

    #: Required. https://xmpp.org/extensions/xep-0380.html.
    eme_ns: Optional[str] = None

    #: Used to figure out what messages to attempt decryption for. Also used
    #: in combination with `tag_whitelist` to avoid removing encrypted tags
    #: before sending. If multiple tags are present, a handler will be
    #: registered for each invididual tag/ns pair under <message/>, as opposed
    #: to a single handler for all tags combined.
    encrypted_tags: Optional[List[Tuple[str, str]]] = None

    # Static map, to be able to limit to one encryption mechanism per tab at a
    # time
    _enabled_tabs: Dict[JID, Callable] = {}

    # Tabs that support this encryption mechanism
    supported_tab_types: Tuple[Type[ChatTab], ...] = tuple()

    # States for each remote entity
    trust_states: Dict[str, Set[str]] = {'accepted': set(), 'rejected': set()}

    def init(self):
        self._all_trust_states = self.trust_states['accepted'].union(
            self.trust_states['rejected']
        )
        if self.encryption_name is None and self.encryption_short_name is None:
            raise NotImplementedError

        if self.eme_ns is None:
            raise NotImplementedError

        if self.encryption_name is None:
            self.encryption_name = self.encryption_short_name
        if self.encryption_short_name is None:
            self.encryption_short_name = self.encryption_name

        if not self.supported_tab_types:
            raise NotImplementedError

        # Ensure decryption is done before everything, so that other handlers
        # don't have to know about the encryption mechanism.
        self.api.add_event_handler('muc_msg', self._decrypt_wrapper, priority=0)
        self.api.add_event_handler('conversation_msg', self._decrypt_wrapper, priority=0)
        self.api.add_event_handler('private_msg', self._decrypt_wrapper, priority=0)

        # Register a handler for each invididual tag/ns pair in encrypted_tags
        # as well. as _msg handlers only include messages with a <body/>.
        if self.encrypted_tags is not None:
            default_ns = self.core.xmpp.default_ns
            for i, (namespace, tag) in enumerate(self.encrypted_tags):
                self.core.xmpp.register_handler(CoroutineCallback(f'EncryptedTag{i}',
                    MatchXPath(f'{{{default_ns}}}message/{{{namespace}}}{tag}'),
                    self._decrypt_encryptedtag,
                ))

        # Ensure encryption is done after everything, so that whatever can be
        # encrypted is encrypted, and no plain element slips in.
        # Using a stream filter might be a bit too much, but at least we're
        # sure poezio is not sneaking anything past us.
        self.core.xmpp.add_filter('out', self._encrypt_wrapper)

        for tab_t in self.supported_tab_types:
            self.api.add_tab_command(
                tab_t,
                self.encryption_short_name,
                self._toggle_tab,
                usage='',
                short='Toggle {} encryption for tab.'.format(self.encryption_name),
                help='Toggle automatic {} encryption for tab.'.format(self.encryption_name),
            )

        trust_msg = 'Set {name} state to {state} for this fingerprint on this JID.'
        for state in self._all_trust_states:
            for tab_t in self.supported_tab_types:
                self.api.add_tab_command(
                    tab_t,
                    self.encryption_short_name + '_' + state,
                    lambda args: self.__command_set_state_local(args, state),
                    usage='<fingerprint>',
                    short=trust_msg.format(name=self.encryption_short_name, state=state),
                    help=trust_msg.format(name=self.encryption_short_name, state=state),
                )
            self.api.add_command(
                self.encryption_short_name + '_' + state,
                lambda args: self.__command_set_state_global(args, state),
                usage='<JID> <fingerprint>',
                short=trust_msg.format(name=self.encryption_short_name, state=state),
                help=trust_msg.format(name=self.encryption_short_name, state=state),
            )

        self.api.add_command(
            self.encryption_short_name + '_fingerprint',
            self._command_show_fingerprints,
            usage='[jid]',
            short=f'Show {self.encryption_short_name} fingerprint(s) for a JID.',
            help=f'Show {self.encryption_short_name} fingerprint(s) for a JID.',
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

        self.__load_encrypted_states()

    def __load_encrypted_states(self) -> None:
        """Load previously stored encryption states for jids."""
        for section in config.sections():
            value = config.getstr('encryption', section=section)
            if value and value == self.encryption_short_name:
                section_jid = JID(section)
                self._enabled_tabs[section_jid] = self.encrypt

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

        if self._encryption_enabled(jid) and self.encryption_short_name:
            return " " + self.encryption_short_name
        return ""

    def _toggle_tab(self, _input: str) -> None:
        tab = self.api.current_tab()
        jid: JID = tab.jid

        if self._encryption_enabled(jid):
            del self._enabled_tabs[jid]
            tab.e2e_encryption = None
            config.remove_and_save('encryption', section=jid)
            self.api.information(
                f'{self.encryption_name} encryption disabled for {jid}',
                'Info',
            )
        elif self.encryption_short_name:
            self._enabled_tabs[jid] = self.encrypt
            tab.e2e_encryption = self.encryption_name
            config.set_and_save('encryption', self.encryption_short_name, section=jid)
            self.api.information(
                f'{self.encryption_name} encryption enabled for {jid}',
                'Info',
            )

    @staticmethod
    def format_fingerprint(fingerprint: str, own: bool, theme: Theme) -> str:
        return fingerprint

    async def _show_fingerprints(self, jid: JID) -> None:
        """Display encryption fingerprints for a JID."""
        theme = get_theme()
        fprs = await self.get_fingerprints(jid)
        if len(fprs) == 1:
            fp, own = fprs[0]
            fingerprint = self.format_fingerprint(fp, own, theme)
            self.api.information(
                f'Fingerprint for {jid}:\n{fingerprint}',
                'Info',
            )
        elif fprs:
            fmt_fprs = map(lambda fp: self.format_fingerprint(fp[0], fp[1], theme), fprs)
            self.api.information(
                'Fingerprints for %s:\n%s' % (jid, '\n\n'.join(fmt_fprs)),
                'Info',
            )
        else:
            self.api.information(
                f'{jid}: No fingerprints to display',
                'Info',
            )

    @command_args_parser.quoted(0, 1)
    def _command_show_fingerprints(self, args: List[str]) -> None:
        tab = self.api.current_tab()
        if not args and isinstance(tab, self.supported_tab_types):
            jid = tab.jid
            if isinstance(tab, MucTab):
                jid = self.core.xmpp.boundjid.bare
        elif not args and isinstance(tab, RosterInfoTab):
            # Allow running the command without arguments in roster tab
            jid = self.core.xmpp.boundjid.bare
        elif args:
            jid = args[0]
        else:
            shortname = self.encryption_short_name
            self.api.information(
                f'{shortname}_fingerprint: Couldn\'t deduce JID from context',
                'Error',
            )
            return None
        asyncio.create_task(self._show_fingerprints(JID(jid)))

    @command_args_parser.quoted(2)
    def __command_set_state_global(self, args, state='') -> None:
        if not args:
            self.api.information(
                'No fingerprint provided to the command..',
                'Error',
            )
            return
        jid, fpr = args
        if state not in self._all_trust_states:
            shortname = self.encryption_short_name
            self.api.information(
                f'Unknown state for plugin {shortname}: {state}',
                'Error'
            )
            return
        self.store_trust(jid, state, fpr)

    @command_args_parser.quoted(1)
    def __command_set_state_local(self, args, state='') -> None:
        if isinstance(self.api.current_tab(), MucTab):
            self.api.information(
                'You can only trust each participant of a MUC individually.',
                'Info',
            )
            return
        jid = self.api.current_tab().jid
        if not args:
            self.api.information(
                'No fingerprint provided to the command..',
                'Error',
            )
            return
        fpr = args[0]
        if state not in self._all_trust_states:
            shortname = self.encryption_short_name
            self.api.information(
                f'Unknown state for plugin {shortname}: {state}',
                'Error',
            )
            return
        self.store_trust(jid, state, fpr)

    def _encryption_enabled(self, jid: JID) -> bool:
        return self._enabled_tabs.get(jid) == self.encrypt

    async def _encrypt_wrapper(self, stanza: StanzaBase) -> Optional[StanzaBase]:
        """
        Wrapper around _encrypt() to handle errors and display the message after encryption.
        """
        try:
            # pylint: disable=unexpected-keyword-arg
            result = await self._encrypt(stanza, passthrough=True)
        except NothingToEncrypt:
            return stanza
        except Exception as exc:
            jid = stanza['from']
            tab = self.core.tabs.by_name_and_class(jid, ChatTab)
            msg = ' \n\x19%s}Could not decrypt message: %s' % (
                dump_tuple(get_theme().COLOR_CHAR_NACK),
                exc,
            )
            # XXX: check before commit. Do we not nack in MUCs?
            if tab and not isinstance(tab, MucTab):
                tab.nack_message(msg, stanza['id'], stanza['to'])
            # TODO: display exceptions to the user properly
            log.error('Exception in encrypt:', exc_info=True)
            return None
        return result

    async def _decrypt_wrapper(self, stanza: Message, tab: Optional[ChatTabs]) -> None:
        """
        Wrapper around _decrypt() to handle errors and display the message after encryption.
        """
        try:
            # pylint: disable=unexpected-keyword-arg
            await self._decrypt(stanza, tab, passthrough=True)
        except Exception as exc:
            jid = stanza['to']
            tab = self.core.tabs.by_name_and_class(jid, ChatTab)
            msg = ' \n\x19%s}Could not send message: %s' % (
                dump_tuple(get_theme().COLOR_CHAR_NACK),
                exc,
            )
            # XXX: check before commit. Do we not nack in MUCs?
            if tab and not isinstance(tab, MucTab):
                tab.nack_message(msg, stanza['id'], stanza['from'])
            # TODO: display exceptions to the user properly
            log.error('Exception in decrypt:', exc_info=True)
            return None
        return None

    async def _decrypt_encryptedtag(self, stanza: Message) -> None:
        """
        Handler to decrypt encrypted_tags elements that are matched separately
        from other messages because the default 'message' handler that we use
        only matches messages containing a <body/>.
        """
        # If the message contains a body, it will already be handled by the
        # other handler. If not, pass it to the handler.
        if stanza.xml.find(f'{{{self.core.xmpp.default_ns}}}body') is not None:
            return None

        mfrom = stanza['from']

        # Find what tab this message corresponds to.
        if stanza['type'] == 'groupchat':  # MUC
            tab = self.core.tabs.by_name_and_class(
                name=mfrom.bare, cls=MucTab,
            )
        elif self.core.handler.is_known_muc_pm(stanza, mfrom):  # MUC-PM
            tab = self.core.tabs.by_name_and_class(
                name=mfrom.full, cls=PrivateTab,
            )
        else:  # 1:1
            tab = self.core.get_conversation_by_jid(
                jid=JID(mfrom.bare),
                create=False,
                fallback_barejid=True,
            )
        log.debug('Found tab %r for encrypted message', tab)
        await self._decrypt_wrapper(stanza, tab)

    async def _decrypt(self, message: Message, tab: Optional[ChatTabs], passthrough: bool = True) -> None:

        has_eme: bool = False
        if message.xml.find(f'{{{EME_NS}}}{EME_TAG}') is not None and \
                message['eme']['namespace'] == self.eme_ns:
            has_eme = True

        has_encrypted_tag: bool = False
        if not has_eme and self.encrypted_tags is not None:
            tmp: bool = True
            for (namespace, tag) in self.encrypted_tags:
                tmp = tmp and message.xml.find(f'{{{namespace}}}{tag}') is not None
            has_encrypted_tag = tmp

        if not has_eme and not has_encrypted_tag:
            return None

        log.debug('Received %s message: %r', self.encryption_name, message['body'])

        # Get the original JID of the sender. The JID might be None if it
        # comes from a semi-anonymous MUC for example. Some plugins might be
        # fine with this so let them handle it.
        jid = message['from']

        muctab: Optional[MucTab] = None
        if isinstance(tab, PrivateTab):
            muctab = tab.parent_muc
            jid = None

        if muctab is not None or isinstance(tab, MucTab):
            if muctab is None:
                muctab = tab  # type: ignore
            nick = message['from'].resource
            user = muctab.get_user_by_name(nick)  # type: ignore
            if user is not None:
                jid = user.jid or None

        # Call the enabled encrypt method
        func = self.decrypt
        if iscoroutinefunction(func):
            # pylint: disable=unexpected-keyword-arg
            await func(message, jid, tab, passthrough=True)  # type: ignore
        else:
            # pylint: disable=unexpected-keyword-arg
            func(message, jid, tab)  # type: ignore

        log.debug('Decrypted %s message: %r', self.encryption_name, message['body'])
        return None

    async def _encrypt(self, stanza: StanzaBase, passthrough: bool = True) -> Optional[StanzaBase]:
        # TODO: Let through messages that contain elements that don't need to
        # be encrypted even in an encrypted context, such as MUC mediated
        # invites, etc.
        # What to do when they're mixed with other elements? It probably
        # depends on the element. Maybe they can be mixed with
        # `self.tag_whitelist` that are already assumed to be sent as plain by
        # the E2EE plugin.
        # They might not be accompanied by a <body/> most of the time, nor by
        # an encrypted tag.

        if not isinstance(stanza, Message) or stanza['type'] not in ('normal', 'chat', 'groupchat'):
            raise NothingToEncrypt()
        message = stanza


        # Is this message already encrypted? Do we need to do all these
        # checks? Such as an OMEMO heartbeat.
        has_encrypted_tag: bool = False
        if self.encrypted_tags is not None:
            tmp: bool = True
            for (namespace, tag) in self.encrypted_tags:
                tmp = tmp and message.xml.find(f'{{{namespace}}}{tag}') is not None
            has_encrypted_tag = tmp

        if has_encrypted_tag:
            log.debug('Message already contains encrypted tags.')
            raise NothingToEncrypt()

        # Find who to encrypt to. If in a groupchat this can be multiple JIDs.
        # It is possible that we are not able to find a jid (e.g., semi-anon
        # MUCs). Let the plugin decide what to do with this information.
        jids: Optional[List[JID]] = [message['to']]
        tab = self.core.tabs.by_jid(message['to'])
        if tab is None and message['to'].resource:
            # Redo the search with the bare JID
            tab = self.core.tabs.by_jid(message['to'].bare)

        if tab is None:  # Possible message sent directly by the e2ee lib?
            log.debug(
                'A message we do not have a tab for '
                'is being sent to \'%s\'. \n%r.',
                message['to'],
                message,
            )

        parent = None
        if isinstance(tab, PrivateTab):
            parent = tab.parent_muc
            nick = tab.jid.resource
            jids = None

            for user in parent.users:
                if user.nick == nick:
                    jids = user.jid or None
                    break

        if isinstance(tab, MucTab):
            jids = []
            for user in tab.users:
                # If the JID of a user is None, assume all others are None and
                # we are in a (at least) semi-anon room. TODO: Really check if
                # the room is semi-anon. Currently a moderator of a semi-anon
                # room will possibly encrypt to everybody, leaking their
                # public key/identity, and they wouldn't be able to decrypt it
                # anyway if they don't know the moderator's JID.
                # TODO: Change MUC to give easier access to this information.
                if user.jid is None:
                    jids = None
                    break
                # If we encrypt to all of these JIDs is up to the plugin, we
                # just tell it who is in the room.
                # XXX: user.jid shouldn't be empty. That's a MucTab/slixmpp
                # bug.
                if user.jid.bare:
                    jids.append(user.jid)

        if tab and not self._encryption_enabled(tab.jid):
            raise NothingToEncrypt()

        log.debug('Sending %s message', self.encryption_name)

        has_body = message.xml.find('{%s}%s' % (JCLIENT_NS, 'body')) is not None

        if not self._encryption_enabled(tab.jid):
            raise NothingToEncrypt()

        # Drop all messages that don't contain a body if the plugin doesn't do
        # Stanza Encryption
        if not self.stanza_encryption and not has_body:
            log.debug(
                '%s plugin: Dropping message as it contains no body, and '
                'doesn\'t do stanza encryption',
                self.encryption_name,
            )
            return None

        # Call the enabled encrypt method
        func = self._enabled_tabs[tab.jid]
        if iscoroutinefunction(func):
            # pylint: disable=unexpected-keyword-arg
            await func(message, jids, tab, passthrough=True)
        else:
            # pylint: disable=unexpected-keyword-arg
            func(message, jids, tab, passthrough=True)

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

        tag_whitelist = {f'{{{ns}}}{tag}' for (ns, tag) in whitelist}

        for elem in message.xml[:]:
            if elem.tag not in tag_whitelist:
                message.xml.remove(elem)

        log.debug('Encrypted %s message', self.encryption_name)
        return message

    def store_trust(self, jid: JID, state: str, fingerprint: str) -> None:
        """Store trust for a fingerprint and a jid."""
        option_name = f'{self.encryption_short_name}:{fingerprint}'
        config.silent_set(option=option_name, value=state, section=jid)

    def fetch_trust(self, jid: JID, fingerprint: str) -> str:
        """Fetch trust of a fingerprint and a jid."""
        option_name = f'{self.encryption_short_name}:{fingerprint}'
        return config.getstr(option=option_name, section=jid)

    async def decrypt(self, message: Message, jid: Optional[JID], tab: Optional[ChatTab]):
        """Decryption method

        This is a method the plugin must implement.  It is expected that this
        method will edit the received message and return nothing.

        :param message: Message to be decrypted.
        :param jid: Real Jid of the sender if available. We might be
                    talking through a semi-anonymous MUC where real JIDs are
                    not available.
        :param tab: Tab the message is coming from.

        :returns: None
        """

        raise NotImplementedError

    async def encrypt(self, message: Message, jids: Optional[List[JID]], tab: ChatTabs):
        """Encryption method

        This is a method the plugin must implement.  It is expected that this
        method will edit the received message and return nothing.

        :param message: Message to be encrypted.
        :param jids: Real Jids of all possible recipients.
        :param tab: Tab the message is going to.

        :returns: None
        """

        raise NotImplementedError

    async def get_fingerprints(self, jid: JID) -> List[Tuple[str, bool]]:
        """Show fingerprint(s) for this encryption method and JID.

        To overload in plugins.

        :returns: A list of fingerprints to display
        """
        return []
