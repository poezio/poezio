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
from poezio.common import parse_secs_to_str
from slixmpp.xmlstream import ET
from slixmpp import JID, InvalidJID
from slixmpp.exceptions import IqError, IqTimeout


class Plugin(BasePlugin):
    def init(self):
        self.api.add_command(
            'uptime',
            self.command_uptime,
            usage='<jid>',
            help='Ask for the uptime of a server or component (see XEP-0012).',
            short='Get the uptime')

    async def command_uptime(self, arg):
        try:
            jid = JID(arg)
        except InvalidJID:
            return
        iq = self.core.xmpp.make_iq_get(ito=jid.server)
        iq.append(ET.Element('{jabber:iq:last}query'))
        try:
            iq = await iq.send()
            result = iq.xml.find('{jabber:iq:last}query')
            if result is not None:
                self.api.information(
                    'Server %s online since %s' %
                    (iq['from'], parse_secs_to_str(
                        int(result.attrib['seconds']))), 'Info')
                return
        except (IqError, IqTimeout):
            pass
        self.api.information('Could not retrieve uptime', 'Error')

