"""
Reverse everything you say.

Installation
------------

You only have to load the plugin:

.. code-block:: none

    /load revstr


"""
from plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.revstr)
        self.api.add_event_handler('conversation_say', self.revstr)
        self.api.add_event_handler('private_say', self.revstr)

    def revstr(self, msg, tab):
        msg['body'] = msg['body'][::-1]
