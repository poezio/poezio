"""
Reverse everything you say (``Je proteste énergiquement`` will become
``tnemeuqigrené etsetorp eJ``)
"""
from poezio.plugin import BasePlugin
from poezio import xhtml

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.revstr)
        self.api.add_event_handler('conversation_say', self.revstr)
        self.api.add_event_handler('private_say', self.revstr)

    def revstr(self, msg, tab):
        msg['body'] = xhtml.clean_text(msg['body'])[::-1]
