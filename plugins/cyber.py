"""
This plugin adds a "cyber" prefix to a random word in your chatroom messages.

Usage
-----

Say something in a MUC tab.

Configuration options
---------------------

.. glossary::

    frequency
        **Default:** ``10``

        The percentage of the time the plugin will activate (randomly). 100 for every message, <= 0 for never.
"""

from poezio.plugin import BasePlugin
from random import choice, randint
import re


DEFAULT_CONFIG = {'cyber': {'frequency': 10}}

class Plugin(BasePlugin):

    default_config = DEFAULT_CONFIG

    def init(self):
        self.api.add_event_handler('muc_say', self.cyberize)

    def cyberize(self, msg, tab):
        if randint(1, 100) > self.config.get('frequency'):
            return
        words = [word for word in re.split('\W+', msg['body']) if len(word) > 3]
        if words:
            word = choice(words)
            msg['body'] = msg['body'].replace(word, 'cyber' + word)
