"""
Module used to provide fixes for sleekxmpp functions not yet fixed
upstream.

TODO: Check that they are fixed and remove those hacks
"""


from sleekxmpp.stanza import Message
from sleekxmpp.xmlstream import ET

import logging

log = logging.getLogger(__name__)

def has_identity(xmpp, jid, identity):
    try:
        iq = xmpp.plugin['xep_0030'].get_info(jid=jid, block=True, timeout=1)
        ident = lambda x: x[0]
        return identity in map(ident, iq['disco_info']['identities'])
    except:
        log.debug('Traceback while retrieving identity', exc_info=True)
    return False

def get_version(xmpp, jid, callback=None, **kwargs):
    def handle_result(res):
        if res and res['type'] != 'error':
            ret = res['software_version'].values
        else:
            ret = False
        if callback:
            callback(ret)
        return ret
    iq = xmpp.make_iq_get(ito=jid)
    iq['query'] = 'jabber:iq:version'
    result = iq.send(callback=handle_result if callback else None)
    if not callback:
        return handle_result(result)


def get_room_form(xmpp, room):
    iq = xmpp.make_iq_get(ito=room)
    query = ET.Element('{http://jabber.org/protocol/muc#owner}query')
    iq.append(query)
    try:
        result = iq.send()
    except:
        return False
    xform = result.xml.find('{http://jabber.org/protocol/muc#owner}query/{jabber:x:data}x')
    if xform is None:
        return False
    form = xmpp.plugin['xep_0004'].buildForm(xform)
    return form


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

    if not stanza['type'] in self.ack_types:
        return stanza

    if stanza['receipt']:
        return stanza

    if not stanza['body']:
        return stanza

    if stanza['to'].resource:
        if not self.xmpp['xep_0030'].supports(stanza['to'],
                feature='urn:xmpp:receipts',
                cached=True):
            return stanza

    stanza['request_receipt'] = True
    return stanza
