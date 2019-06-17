"""
This plugin uses figlet to transform every message into a big ascii-art
message.


Usage
-----

Say something in a Chat tab.

.. note:: Can create fun things when used with :ref:`The rainbow plugin <rainbow-plugin>`.

"""

import subprocess
from poezio.plugin import BasePlugin


def is_figlet() -> bool:
    """Ensure figlet exists"""
    process = subprocess.Popen(
        ['which', 'figlet'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process.wait() == 0


class Plugin(BasePlugin):
    def init(self):
        if not is_figlet():
            self.api.information(
                'Couldn\'t find the figlet program. '
                'Please install it and reload the plugin.',
                'Error',
            )
            return None

        self.api.add_event_handler('muc_say', self.figletize)
        self.api.add_event_handler('conversation_say', self.figletize)
        self.api.add_event_handler('private_say', self.figletize)
        return None

    def figletize(self, msg, tab):
        process = subprocess.Popen(
            ['figlet', '--', msg['body']], stdout=subprocess.PIPE)
        result = process.communicate()[0].decode('utf-8')
        msg['body'] = result
