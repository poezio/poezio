"""
Add a subtle little advertising in your messages.

Configuration
-------------

.. code-block:: ini

    [spam]
    ad = I’m a happy poezio user. Get it at http://poezio.eu

"""

from poezio.plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.advert)
        self.api.add_event_handler('conversation_say', self.advert)
        self.api.add_event_handler('private_say', self.advert)

    def advert(self, msg, tab):
        msg['body'] = "%s\n\n%s" % (msg['body'], self.config.get("ad", "Sent from poezio"))
