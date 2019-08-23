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
import logging

from poezio.plugin_e2ee import E2EEPlugin
from poezio.xdg import DATA_HOME

from omemo.exceptions import MissingBundleException
from slixmpp.stanza import Message
from slixmpp.exceptions import IqError, IqTimeout
from slixmpp_omemo import PluginCouldNotLoad, MissingOwnKey, NoAvailableSession
from slixmpp_omemo import UndecidedException, UntrustedException, EncryptionPrepareException
import slixmpp_omemo

log = logging.getLogger(__name__)


class Plugin(E2EEPlugin):
    """OMEMO (XEP-0384) Plugin"""

    encryption_name = 'omemo'
    eme_ns = slixmpp_omemo.OMEMO_BASE_NS
    replace_body_with_eme = True
    stanza_encryption = False

    encrypted_tags = [
        (slixmpp_omemo.OMEMO_BASE_NS, 'encrypted'),
    ]

    def init(self) -> None:
        super().init()

        self.info = lambda i: self.api.information(i, 'Info')

        data_dir = os.path.join(DATA_HOME, 'omemo', self.core.xmpp.boundjid.bare)
        os.makedirs(data_dir, exist_ok=True)

        try:
            self.core.xmpp.register_plugin(
                'xep_0384', {
                    'data_dir': data_dir,
                },
                module=slixmpp_omemo,
            ) # OMEMO
        except (PluginCouldNotLoad,):
            log.exception('And error occured when loading the omemo plugin.')

        asyncio.ensure_future(
            self.core.xmpp['xep_0384'].session_start(self.core.xmpp.boundjid)
        )

    def display_error(self, txt) -> None:
        self.api.information(txt, 'Error')

    def decrypt(self, message: Message, tab, allow_untrusted=False) -> None:

        body = None
        try:
            body = self.core.xmpp['xep_0384'].decrypt_message(message, allow_untrusted)
            body = body.decode('utf-8')
        except (MissingOwnKey,):
            # The message is missing our own key, it was not encrypted for
            # us, and we can't decrypt it.
            self.display_error(
                'I can\'t decrypt this message as it is not encrypted for me.'
            )
        except (NoAvailableSession,) as exn:
            # We received a message from that contained a session that we
            # don't know about (deleted session storage, etc.). We can't
            # decrypt the message, and it's going to be lost.
            # Here, as we need to initiate a new encrypted session, it is
            # best if we send an encrypted message directly. XXX: Is it
            # where we talk about self-healing messages?
            self.display_error(
                'I can\'t decrypt this message as it uses an encrypted '
                'session I don\'t know about.',
            )
        except (UndecidedException, UntrustedException) as exn:
            # We received a message from an untrusted device. We can
            # choose to decrypt the message nonetheless, with the
            # `allow_untrusted` flag on the `decrypt_message` call, which
            # we will do here. This is only possible for decryption,
            # encryption will require us to decide if we trust the device
            # or not. Clients _should_ indicate that the message was not
            # trusted, or in undecided state, if they decide to decrypt it
            # anyway.
            self.display_error(
                "Your device '%s' is not in my trusted devices." % exn.device,
            )
            # We resend, setting the `allow_untrusted` parameter to True.
            self.decrypt(message, tab, allow_untrusted=True)
        except (EncryptionPrepareException,):
            # Slixmpp tried its best, but there were errors it couldn't
            # resolve. At this point you should have seen other exceptions
            # and given a chance to resolve them already.
            self.display_error('I was not able to decrypt the message.')
        except (Exception,) as exn:
            self.display_error('An error occured while attempting decryption.\n%r' % exn)
            raise

        if body is not None:
            message['body'] = body

    async def encrypt(self, message: Message, _tab) -> None:
        mto = message['to']
        mtype = message['type']
        body = message['body']
        expect_problems = {}  # type: Optional[Dict[JID, List[int]]]

        while True:
            try:
                # `encrypt_message` excepts the plaintext to be sent, a list of
                # bare JIDs to encrypt to, and optionally a dict of problems to
                # expect per bare JID.
                #
                # Note that this function returns an `<encrypted/>` object,
                # and not a full Message stanza. This combined with the
                # `recipients` parameter that requires for a list of JIDs,
                # allows you to encrypt for 1:1 as well as groupchats (MUC).
                #
                # TODO: Document expect_problems
                # TODO: Handle multiple recipients (MUCs)
                recipients = [mto]
                encrypt = await self.core.xmpp['xep_0384'].encrypt_message(body, recipients, expect_problems)
                message.append(encrypt)
                return None
            except UndecidedException as exn:
                # The library prevents us from sending a message to an
                # untrusted/undecided barejid, so we need to make a decision here.
                # This is where you prompt your user to ask what to do. In
                # this bot we will automatically trust undecided recipients.
                self.core.xmpp['xep_0384'].trust(exn.bare_jid, exn.device, exn.ik)
            except MissingBundleException as exn:
                self.display_error(
                    'Could not find keys for device "%d" of recipient "%s". Skipping.' % (exn.device, exn.bare_jid),
                )
                device_list = expect_problems.setdefault(exn.bare_jid, [])
                device_list.append(exn.device)
            # TODO: catch NoEligibleDevicesException
            except (IqError, IqTimeout) as exn:
                self.display_error(
                    'An error occured while fetching information on a recipient.\n%r' % exn,
                )
                return None
            except Exception as exn:
                self.display_error(
                    'An error occured while attempting to encrypt.\n%r' % exn,
                )
                raise

        return None
