"""
Module used to provide fixes for slixmpp functions not yet fixed
upstream.

TODO: Check that they are fixed and remove those hacks
"""

from slixmpp import Message
from slixmpp.plugins.xep_0184 import XEP_0184

import logging

log = logging.getLogger(__name__)


def _filter_add_receipt_request(self: XEP_0184, stanza):
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
