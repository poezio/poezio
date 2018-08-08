"""
This plugin colors each character of a message in white.

Usage
-----

.. glossary::

    /load white

        Say something in a Chat tab.

.. note:: This plugin is best used when someone else is writing in black,
assuming everyone is using a white background.  Black backgrounds matter too!
"""

from poezio.plugin import BasePlugin
from poezio import xhtml

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.whiteify)
        self.api.add_event_handler('private_say', self.whiteify)
        self.api.add_event_handler('conversation_say', self.whiteify)

    @staticmethod
    def whiteify(msg, _):
        msg['body'] = '\x197}' + xhtml.clean_text(msg['body'])
