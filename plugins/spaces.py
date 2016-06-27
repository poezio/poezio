"""
Insert a space between each character, in messages that you send, making
them horrible to read.
"""
from poezio.plugin import BasePlugin
from poezio import xhtml

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.add_spaces)
        self.api.add_event_handler('conversation_say', self.add_spaces)
        self.api.add_event_handler('private_say', self.add_spaces)

    def add_spaces(self, msg, tab):
        msg['body'] = " ".join(x for x in xhtml.clean_text(msg['body']))
