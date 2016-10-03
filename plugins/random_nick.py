"""
This plugin makes you have a random nick when joining a chatroom.

Usage
-----

To have a random nick, just join a room with “RANDOM” as your nick. It will
automatically be changed to something random, for example: ::

    /join coucou@conference.example.com/RANDOM

"""

from poezio.plugin import BasePlugin
from random import choice

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('joining_muc', self.change_nick_to_random)
        self.api.add_event_handler('changing_nick', self.change_nick_to_random)

    def change_nick_to_random(self, presence):
        to = presence["to"]
        if to.resource == 'RANDOM':
            to.resource = gen_nick(3)
            presence["to"] = to

s = ["i", "ou", "ou", "on", "a", "o", "u", "i"]
c = ["b", "c", "d", "f", "g", "h", "j", "k", "m", "l", "n", "p", "r", "s", "t", "v", "z"]

def gen_nick(size):
    res = ''
    for _ in range(size):
        res += '%s%s' % (choice(c), choice(s))
    return res
