from plugin import BasePlugin

class Plugin(BasePlugin):
    """
    Adds several convenient aliases to /status command
    """
    def init(self):
        self.add_command('dnd', lambda line: self.core.command_status('dnd '+line),
                '/dnd [status message]\nDnd: Set your status as dnd (do not disturb).')
        self.add_command('busy', lambda line: self.core.command_status('busy '+line),
                '/busy [status message]\nBusy: Set your status as busy.')
        self.add_command('chat', lambda line: self.core.command_status('chat '+line),
                '/chat [status message]\nChat: Set your status as chatty.')
        self.add_command('xa', lambda line: self.core.command_status('xa '+line),
                '/xa [status message]\nXa: Set your status as xa (eXtended away).')
        self.add_command('afk', lambda line: self.core.command_status('afk '+line),
                '/afk [status message]\nAfk: Set your status as afk (away from keyboard).')
        self.add_command('away', lambda line: self.core.command_status('away '+line),
                '/away [status message]\nAway: Set your status as away.')
        self.add_command('away', lambda line: self.core.command_status('away '+line),
                '/available [status message]\nAvailable: Set your status as available.')
