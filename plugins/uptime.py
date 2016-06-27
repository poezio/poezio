"""
This plugin retrieves the uptime of a server.

Command
-------

.. glossary::

    /uptime
        **Usage:** ``/uptime <jid>``

        Retrieve the uptime of the server of ``jid``.
"""
from poezio.plugin import BasePlugin
from poezio.common import parse_secs_to_str, safeJID
from slixmpp.xmlstream import ET

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('uptime', self.command_uptime,
                usage='<jid>',
                help='Ask for the uptime of a server or component (see XEP-0012).',
                short='Get the uptime')

    def command_uptime(self, arg):
        def callback(iq):
            for query in iq.xml.getiterator('{jabber:iq:last}query'):
                self.api.information('Server %s online since %s' % (iq['from'], parse_secs_to_str(int(query.attrib['seconds']))), 'Info')
                return
            self.api.information('Could not retrieve uptime', 'Error')
        jid = safeJID(arg)
        if not jid.server:
            return
        iq = self.core.xmpp.make_iq_get(ito=jid.server)
        iq.append(ET.Element('{jabber:iq:last}query'))
        iq.send(callback=callback)
