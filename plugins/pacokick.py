"""
This plugin adds a :term:`/pacokick` command, which is a random kick.

Usage
-----

.. glossary::

    /pacokick

        Run the command in a room where you are a moderator to
        kick someone randomly.
"""

from random import choice
from poezio.tabs import MucTab

from poezio.plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('pacokick', self.command_kick,
                usage='',
                help='Kick a random user.',
                short='Kick a random user')

    def command_kick(self, arg):
        tab = self.api.current_tab()
        if isinstance(tab, MucTab):
            kickable = list(filter(lambda x: x.affiliation in ('none', 'member'), tab.users))
            if kickable:
                to_kick = choice(kickable)
                if to_kick:
                    to_kick = to_kick.nick
                    tab.command_kick(to_kick + ' ' +arg)
            else:
                self.api.information('No one to kick :(', 'Info')
