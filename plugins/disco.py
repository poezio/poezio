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
            usage='<JID> [node] [info|items]',
            short='Get the disco#info of a JID',
            help='Get the disco#info of a JID')

    def on_info(self, iq):
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

    def on_items(self, iq):
        if iq['type'] == 'error':
            self.api.information(iq['error']['text'] or iq['error']['condition'], 'Error')
            return

        def describe(item):
            text = item[0]
            node = item[1]
            name = item[2]
            if node is not None:
                text += ', node=' + node
            if name is not None:
                text += ', name=' + name
            return text

        items = iq['disco_items']
        self.api.information('\n'.join(describe(item) for item in items['items']), 'Items')

    @command_args_parser.quoted(1, 3)
    def command_disco(self, args):
        if args is None:
            self.core.command.help('disco')
            return
        if len(args) == 1:
            jid, = args
            node = None
            type_ = 'info'
        elif len(args) == 2:
            jid, node = args
            type_ = 'info'
        else:
            jid, node, type_ = args
        try:
            if type_ == 'info':
                self.core.xmpp.plugin['xep_0030'].get_info(
                    jid=jid, node=node, cached=False, callback=self.on_info)
            elif type_ == 'items':
                self.core.xmpp.plugin['xep_0030'].get_items(
                    jid=jid, node=node, cached=False, callback=self.on_items)
        except InvalidJID as e:
            self.api.information('Invalid JID “%s”: %s' % (jid, e), 'Error')
