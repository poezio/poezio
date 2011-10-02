from plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.add_command('alias', self.command_alias, '/alias <alias> <command> <args>\nAlias: create an alias command')
        self.add_command('unalias', self.command_unalias, '/unalias <alias>\nUnalias: remove a previously created alias')
        self.commands = {}

    def command_alias(self, line):
        arg = line.split()
        if len(arg) < 2:
            self.core.information('Alias: Not enough parameters', 'Error')
            return
        alias = arg[0]
        command = arg[1]
        post_args = ' '.join(arg[2:])

        if alias in self.core.commands or alias in self.commands:
            self.core.information('Alias: command already exists', 'Error')
            return
        self.commands[alias] = lambda args: self.get_command(command)(post_args+args)
        self.add_command(alias, self.commands[alias], 'This command is an alias for /%s %s' % (command, post_args))
        self.core.information('Alias /%s successfuly created' % alias, 'Info')

    def command_unalias(self, alias):
        if alias in self.commands:
            del self.commands[alias]
            self.del_command(alias)
            self.core.information('Alias /%s successfuly deleted' % alias, 'Info')

    def get_command(self, name):
        """Returns the function associated with a command"""
        def dummy(args):
            """Dummy function called if the command doesn’t exist"""
            pass
        if name in self.core.commands:
            return self.core.commands[name][0]
        elif name in self.core.current_tab().commands:
            return self.core.current_tab().commands[name][0]
        return dummy
