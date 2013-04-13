"""
Shuffle the words in every message you send in a :ref:`muctab`
(may confuse the reader).

Installation
------------

You only have to load the plugin:

.. code-block:: none

    /load shuffle

"""
from plugin import BasePlugin
from random import shuffle

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.shuffle)

    def shuffle(self, msg, tab):
        split = msg['body'].split()
        shuffle(split)
        msg['body'] = ' '.join(split)
