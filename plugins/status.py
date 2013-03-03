from plugin import BasePlugin

class Plugin(BasePlugin):
    """
    Adds several convenient aliases to /status command
    """
    def init(self):
        for st in ('dnd', 'busy', 'afk', 'chat', 'xa', 'away', 'available'):
            self.add_command(st,
                    lambda line,st=st: self.core.command_status(st + ' "'+line+'"'),
                    usage='[status message]',
                    short='Set your status as %s' % st,
                    help='Set your status as %s' % st)
