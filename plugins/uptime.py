"""
This plugin retrieves the uptime of a server.

Installation
------------
You only have to load the plugin.

.. code-block:: none

    /load uptime


Command
-------

.. glossary::

    /uptime
        **Usage:** ``/uptime <jid>``

        Retrieve the uptime of the server of ``jid``.
"""
from plugin import BasePlugin
import tabs
from common import parse_secs_to_str, safeJID
from sleekxmpp.xmlstream import ET

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
        iq = self.core.xmpp.makeIqGet(ito=jid.server)
        iq.append(ET.Element('{jabber:iq:last}query'))
        iq.send(block=False, callback=callback)
