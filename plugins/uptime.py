from plugin import BasePlugin
import tabs
from common import parse_secs_to_str
from sleekxmpp.xmlstream import ET
from sleekxmpp.xmlstream.stanzabase import JID

class Plugin(BasePlugin):
    def init(self):
        self.add_command('uptime', self.command_uptime, '/uptime [jid]\nUptime: Ask for the uptime of a server or component (see XEP-0012).', None)

    def command_uptime(self, arg):
        def callback(iq):
            for query in iq.xml.getiterator('{jabber:iq:last}query'):
                self.core.information('Server %s online since %s' % (iq['from'], parse_secs_to_str(int(query.attrib['seconds']))), 'Info')
                return
            self.core.information('Could not retrieve uptime', 'Error')
        jid = JID(arg)
        if not jid.server:
            return
        iq = self.core.xmpp.makeIqGet(ito=jid.server)
        iq.append(ET.Element('{jabber:iq:last}query'))
        iq.send(block=False, callback=callback)
