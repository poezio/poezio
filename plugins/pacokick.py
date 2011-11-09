from random import choice
from tabs import MucTab

from plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.add_command('pacokick', self.command_kick, '/pacokick <nick> [reason]\nPacokick: kick a random user.')

    def command_kick(self, arg):
        tab = self.core.current_tab()
        if isinstance(tab, MucTab):
            kickable = list(filter(lambda x: x.affiliation in ('none', 'member'), tab.users))
            if kickable:
                to_kick = choice(kickable)
                if to_kick:
                    to_kick = to_kick.nick
                    tab.command_kick(to_kick + ' ' +arg)
            else:
                self.core.information('No one to kick :(', 'Info')
