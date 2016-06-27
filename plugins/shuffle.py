"""
Shuffle the words in every message you send in a :ref:`muctab`
(may/should confuse the reader).
"""
from poezio.plugin import BasePlugin
from random import shuffle
from poezio import xhtml

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.shuffle)

    def shuffle(self, msg, tab):
        split = xhtml.clean_text(msg['body']).split()
        shuffle(split)
        msg['body'] = ' '.join(split)
