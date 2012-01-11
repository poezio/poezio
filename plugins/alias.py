from plugin import BasePlugin
import common
from common import parse_command_args_to_alias as parse

class Plugin(BasePlugin):
    def init(self):
        self.add_command('alias', self.command_alias, '/alias <alias> <command> <args>\nAlias: create an alias command')
        self.add_command('unalias', self.command_unalias, '/unalias <alias>\nUnalias: remove a previously created alias')
        self.commands = {}

    def command_alias(self, line):
        arg = common.shell_split(line)
        if len(arg) < 2:
            self.core.information('Alias: Not enough parameters', 'Error')
            return
        alias = arg[0]
        tmp_args = common.shell_split(arg[1])
        command = tmp_args.pop(0)
        tmp_args = arg[1][len(command)+1:]

        if alias in self.core.commands or alias in self.commands:
            self.core.information('Alias: command already exists', 'Error')
            return
        self.commands[alias] = lambda arg: self.get_command(command)(parse(arg, tmp_args))
        self.add_command(alias, self.commands[alias], 'This command is an alias for /%s %s' %( command, tmp_args))
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
