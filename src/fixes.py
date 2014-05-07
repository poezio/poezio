"""
Module used to provide fixes for sleekxmpp functions not yet fixed
upstream.

TODO: Check that they are fixed and remove those hacks
"""

from sleekxmpp.stanza import Message
from sleekxmpp.xmlstream import ET

import logging

# used to avoid doing numerous useless disco#info requests
# especially with message receipts
IQ_ERRORS = set()

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

def xep_30_supports(self, jid, node, ifrom, data):
    """
    Check if a JID supports a given feature.

    The data parameter may provide:
        feature  -- The feature to check for support.
        local    -- If true, then the query is for a JID/node
                    combination handled by this Sleek instance and
                    no stanzas need to be sent.
                    Otherwise, a disco stanza must be sent to the
                    remove JID to retrieve the info.
        cached   -- If true, then look for the disco info data from
                    the local cache system. If no results are found,
                    send the query as usual. The self.use_cache
                    setting must be set to true for this option to
                    be useful. If set to false, then the cache will
                    be skipped, even if a result has already been
                    cached. Defaults to false.
    """
    feature = data.get('feature', None)

    data = {'local': data.get('local', False),
            'cached': data.get('cached', True)}

    if not feature or jid.full in IQ_ERRORS:
        return False

    try:
        info = self.disco.get_info(jid=jid, node=node,
                                   ifrom=ifrom, **data)
        info = self.disco._wrap(ifrom, jid, info, True)
        features = info['disco_info']['features']
        return feature in features
    except:
        IQ_ERRORS.add(jid.full)
        log.debug('%s added to the list of entities that do'
                  'not honor disco#info', jid.full)
        return False

def xep_115_supports(self, jid, node, ifrom, data):
    """
    Check if a JID supports a given feature.

    The data parameter may provide:
        feature  -- The feature to check for support.
        local    -- If true, then the query is for a JID/node
                    combination handled by this Sleek instance and
                    no stanzas need to be sent.
                    Otherwise, a disco stanza must be sent to the
                    remove JID to retrieve the info.
        cached   -- If true, then look for the disco info data from
                    the local cache system. If no results are found,
                    send the query as usual. The self.use_cache
                    setting must be set to true for this option to
                    be useful. If set to false, then the cache will
                    be skipped, even if a result has already been
                    cached. Defaults to false.
    """
    feature = data.get('feature', None)

    data = {'local': data.get('local', False),
            'cached': data.get('cached', True)}

    if not feature or jid.full in IQ_ERRORS:
        return False

    if node in (None, ''):
        info = self.caps.get_caps(jid)
        if info and feature in info['features']:
            return True

    try:
        info = self.disco.get_info(jid=jid, node=node,
                                   ifrom=ifrom, **data)
        info = self.disco._wrap(ifrom, jid, info, True)
        return feature in info['disco_info']['features']
    except:
        IQ_ERRORS.add(jid.full)
        log.debug('%s added to the list of entities that do'
                  'not honor disco#info', jid.full)
        return False

def reset_iq_errors():
    "reset the iq error cache"
    IQ_ERRORS.clear()
