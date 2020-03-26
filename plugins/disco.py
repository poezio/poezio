"""
Do a disco#info query on a JID

Usage
-----

.. glossary::

    /disco
        **Usage:** ``/disco <JID>``

        This command queries a JID for its disco#info.

        There is no cache, as this is generally used for debug more than
        anything user-related.
"""

from poezio.plugin import BasePlugin
from poezio.decorators import command_args_parser
from slixmpp.jid import InvalidJID


class Plugin(BasePlugin):
    def init(self):
        self.api.add_command(
            'disco',
            self.command_disco,
            usage='<JID> [node]',
            short='Get the disco#info of a JID',
            help='Get the disco#info of a JID')

    def on_disco(self, iq):
        if iq['type'] == 'error':
            self.api.information(iq['error']['text'] or iq['error']['condition'], 'Error')
            return

        info = iq['disco_info']
        identities = (str(identity) for identity in info['identities'])
        self.api.information('\n'.join(identities), 'Identities')
        features = sorted(str(feature) for feature in info['features'])
        self.api.information('\n'.join(features), 'Features')
        title = 'Server Info'
        server_info = []
        for field in info['form']:
            var = field['var']
            if field['type'] == 'hidden' and var == 'FORM_TYPE':
                title = field['value'][0]
                continue
            sep = '\n  ' + len(var) * ' '
            field_value = field.get_value(convert=False)
            value = sep.join(field_value) if isinstance(field_value,
                                                        list) else field_value
            server_info.append('%s: %s' % (var, value))
        if server_info:
            self.api.information('\n'.join(server_info), title)

    @command_args_parser.quoted(1, 2)
    def command_disco(self, args):
        if args is None:
            self.core.command.help('disco')
            return
        if len(args) == 1:
            jid, = args
            node = None
        else:
            jid, node = args
        try:
            self.core.xmpp.plugin['xep_0030'].get_info(
                jid=jid, node=node, cached=False, callback=self.on_disco)
        except InvalidJID as e:
            self.api.information('Invalid JID “%s”: %s' % (jid, e), 'Error')
