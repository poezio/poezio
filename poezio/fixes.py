"""
Module used to provide fixes for slixmpp functions not yet fixed
upstream.

TODO: Check that they are fixed and remove those hacks
"""

import asyncio
from typing import Callable, Any
from slixmpp import Message, Iq, ClientXMPP
from slixmpp.xmlstream import ET

import logging

log = logging.getLogger(__name__)


def has_identity(xmpp, jid, identity, on_true=None, on_false=None):
    def _cb(iq):
        ident = lambda x: x[0]
        res = identity in map(ident, iq['disco_info']['identities'])
        if res and on_true is not None:
            on_true()
        if not res and on_false is not None:
            on_false()

    asyncio.ensure_future(
        xmpp.plugin['xep_0030'].get_info(jid=jid, callback=_cb)
    )


def _filter_add_receipt_request(self, stanza):
    """
    Auto add receipt requests to outgoing messages, if:

        - ``self.auto_request`` is set to ``True``
        - The message is not for groupchat
        - The message does not contain a receipt acknowledgment
        - The recipient is a bare JID or, if a full JID, one
          that has the ``urn:xmpp:receipts`` feature enabled
        - The message has a body

    The disco cache is checked if a full JID is specified in
    the outgoing message, which may mean a round-trip disco#info
    delay for the first message sent to the JID if entity caps
    are not used.
    """

    if not self.auto_request:
        return stanza

    if not isinstance(stanza, Message):
        return stanza

    if stanza['request_receipt']:
        return stanza

    if stanza['type'] not in self.ack_types:
        return stanza

    if stanza['receipt']:
        return stanza

    if not stanza['body']:
        return stanza

    # hack
    if stanza['to'].resource and not hasattr(stanza, '_add_receipt'):
        return stanza

    stanza['request_receipt'] = True
    return stanza
