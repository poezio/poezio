"""
Replace some word with some other word in a message before sending it.

Configuration example
---------------------
.. code-block:: ini

[replace_word]
# How to appear casual in your daily conversations.
yes = yep
no = nope

Usage
-----
Just use the word in a message. It will be replaced automatically.

"""

from poezio.plugin import BasePlugin
import re

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('conversation_say', self.replace_pattern)
        self.api.add_event_handler('muc_say', self.replace_pattern)
        self.api.add_event_handler('private_say', self.replace_pattern)

    def replace_pattern(self, message, tab):
        """
        Look for a given word in the message and replace it by the corresponding word.
        """
        body = message['body']
        for before in self.config.options("replace_word"):
            after = self.config.get(before, before)
            body = re.sub(r"\b%s\b" % before, after, body)
        message['body'] = body
