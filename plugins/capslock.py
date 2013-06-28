"""
Shout

Installation
------------

You only have to load the plugin:

.. code-block:: none

    /load capslock


"""
from plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.caps)
        self.api.add_event_handler('conversation_say', self.caps)
        self.api.add_event_handler('private_say', self.caps)

    def caps(self, msg, tab):
        msg['body'] = msg['body'].upper()
