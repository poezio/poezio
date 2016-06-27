"""
This plugin adds a command (that can be bound to a key) that adds a random
number of dots in the input, making you look depressed, or overly thinking...

Installation
------------
Load the plugin.::

    /load pointpoint

Then use the command: ::

    /pointpoint

But since the goal is to be able to add the dots while typing a message,
entering a command is not really useful. To be useful, this plugin needs to
be used through a bound key, for example like this: ::

    /bind M-. _exc_pointpoint

You just need to press Alt+. and this will insert dots in your message.

Command
-------

.. glossary::

    /pointpoint
        **Usage:** ``/pointpoint``

        …


"""

from poezio.plugin import BasePlugin
from random import randrange

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('pointpoint', self.command_pointpoint,
                             help='Insert a random number of dots in the input')

    def command_pointpoint(self, args):
        for i in range(randrange(8, 25)):
            self.core.current_tab().input.do_command(".")
