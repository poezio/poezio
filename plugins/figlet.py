"""
This plugin uses figlet to transform every message into a big ascii-art
message.


Usage
-----

Say something in a Chat tab.

.. note:: Can create fun things when used with :ref:`The rainbow plugin <rainbow-plugin>`.

"""
from poezio.plugin import BasePlugin
import subprocess

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.figletize)
        self.api.add_event_handler('conversation_say', self.figletize)
        self.api.add_event_handler('private_say', self.figletize)

    def figletize(self, msg, tab):
        process = subprocess.Popen(['figlet', '--', msg['body']], stdout=subprocess.PIPE)
        result = process.communicate()[0].decode('utf-8')
        msg['body'] = result
