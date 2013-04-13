"""
This plugin broadcasts a message to all your joined rooms.

.. note:: With great power comes great responsability.
          Use with moderation.

Installation
------------
You only have to load the plugin.::

    /load amsg

Command
-------

.. glossary::

    /amsg
        **Usage:** ``/amsg <message>``


"""
from plugin import BasePlugin
from tabs import MucTab

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('amsg', self.command_amsg,
                usage='<message>',
                short='Broadcast a message',
                help='Broadcast the message to all the joined rooms.')

    def command_amsg(self, args):
        for room in self.core.tabs:
            if isinstance(room, MucTab) and room.joined:
                room.command_say(args)
