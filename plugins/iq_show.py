from plugin import BasePlugin
from sleekxmpp.xmlstream.matcher import StanzaPath
from sleekxmpp.xmlstream.handler import Callback

class Plugin(BasePlugin):
    def init(self):
        self.core.xmpp.register_handler(Callback('Iq_show', StanzaPath('iq'), self.handle_iq))

    def handle_iq(self, iq):
        self.core.information('%s' % iq, 'Iq')

    def cleanup(self):
        self.core.xmpp.remove_handler('Iq_show')
        del self.handle_iq
