"""
Once loaded, every line of your messages will be stripped of their trailing spaces.
"""
from poezio.plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.rstrip)
        self.api.add_event_handler('conversation_say', self.rstrip)
        self.api.add_event_handler('private_say', self.rstrip)

    def rstrip(self, msg, tab):
        msg['body'] = '\n'.join(line.rstrip() for line in msg['body'].split('\n'))
