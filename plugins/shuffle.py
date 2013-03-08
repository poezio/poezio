from plugin import BasePlugin
from random import shuffle

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.shuffle)

    def shuffle(self, msg, tab):
        split = msg['body'].split()
        shuffle(split)
        msg['body'] = ' '.join(split)
