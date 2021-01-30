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
        contacts = []
        # iterate all data forms, in case there are multiple
        for form in iq['disco_info']:
            values = form.get_values()
            if values['FORM_TYPE'][0] == 'http://jabber.org/network/serverinfo':
                for var in values:
                    if not var.endswith('-addresses'):
                        continue
                    title = var[:-10] # strip '-addresses'
                    sep = '\n  ' + len(title) * ' '
                    field_value = values[var]
                    if field_value:
                        value = sep.join(field_value) if isinstance(field_value, list) else field_value
                        contacts.append('%s: %s' % (title, value))
        if contacts:
            self.api.information('\n'.join(contacts), 'Contact Info')
        else:
            self.api.information('No Contact Addresses for %s' % iq['from'], 'Error')

    async def command_disco(self, jid):
        try:
            iq = await self.core.xmpp.plugin['xep_0030'].get_info(jid=jid, cached=False)
            self.on_disco(iq)
        except InvalidJID as e:
            self.api.information('Invalid JID “%s”: %s' % (jid, e), 'Error')
