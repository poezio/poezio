from plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.add_event_handler('muc_say', self.revstr)

    def revstr(self, msg, tab):
        msg['body'] = msg['body'][::-1]
