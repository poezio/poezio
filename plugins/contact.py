"""
Do a disco#info query on a JID, display the XEP-0157 Contact Addresses

Usage
-----

.. glossary::

    /contact
        **Usage:** ``/contact <JID>``

        This command queries a JID for its Contact Addresses.
"""

from poezio.plugin import BasePlugin
from slixmpp.jid import InvalidJID

CONTACT_TYPES = ['abuse', 'admin', 'feedback', 'sales', 'security', 'support']

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('contact', self.command_disco,
                usage='<JID>',
                short='Get the Contact Addresses of a JID',
                help='Get the Contact Addresses of a JID')

    def on_disco(self, iq):
        if iq['type'] == 'error':
            error_condition = iq['error']['condition']
            error_text = iq['error']['text']
            message = 'Error getting Contact Addresses from %s: %s: %s' % (iq['from'], error_condition, error_text)
            self.api.information(message, 'Error')
            return
        info = iq['disco_info']
        title = 'Contact Info'
        contacts = []
        for field in info['form']:
            var = field['var']
            if field['type'] == 'hidden' and var == 'FORM_TYPE':
                form_type = field['value'][0]
                if form_type != 'http://jabber.org/network/serverinfo':
                    self.api.information('Not a server: “%s”: %s' % (iq['from'], form_type), 'Error')
                    return
                continue
            if not var.endswith('-addresses'):
                continue
            var = var[:-10] # strip '-addresses'
            sep = '\n  ' + len(var) * ' '
            field_value = field.get_value(convert=False)
            value = sep.join(field_value) if isinstance(field_value, list) else field_value
            contacts.append('%s: %s' % (var, value))
        if contacts:
            self.api.information('\n'.join(contacts), title)
        else:
            self.api.information('No Contact Addresses for %s' % iq['from'], 'Error')

    def command_disco(self, jid):
        try:
            self.core.xmpp.plugin['xep_0030'].get_info(jid=jid, cached=False,
                                                       callback=self.on_disco)
        except InvalidJID as e:
            self.api.information('Invalid JID “%s”: %s' % (jid, e), 'Error')
