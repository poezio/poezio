# A simple broadcast plugin

from plugin import BasePlugin
from tabs import MucTab

class Plugin(BasePlugin):
    def init(self):
        self.add_command('amsg', self.command_amsg,
                usage='<message>',
                short='Broadcast a message',
                help='Broadcast the message to all the joined rooms.')

    def command_amsg(self, args):
        for room in self.core.tabs:
            if isinstance(room, MucTab) and room.joined:
                room.command_say(args)
