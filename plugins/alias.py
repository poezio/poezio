"""
Installation
------------
You only have to load the plugin:

``/load alias``

Usage
-----

This plugin defines two new global commands: :term:`/alias` and :term:`/unalias`.

.. glossary::

    /alias
        **Usage:** ``/alias <name> <command> [args]``

        This command will create a new command, named ``name`` (and callable with
        ``/name``), that runs ``/command``, with ``[args]`` as fixed args for the command.
        When you run the alias, you can also pass parameters to it, that will be fed
        to the original command.

        Example: ::

            /alias toto say "koin "

        Will bind ``/say koin `` to ``/toto``, so this alias will work in any
        Chat tab. If someone calls it with ::

            /toto koin

        Poezio will then execute ``/say koin koin``.

    /unalias
        **Usage:** ``/unalias <name>``

        This command removes a defined alias.

"""

from plugin import BasePlugin
import common
from common import shell_split

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('alias', self.command_alias,
                usage='<alias> <command> [args]',
                short='Create an alias command',
                help='Create an alias for <command> with [args].')
        self.api.add_command('unalias', self.command_unalias,
                usage='<alias>',
                help='Remove a previously created alias',
                short='Remove an alias',
                completion=self.completion_unalias)
        self.commands = {}

    def command_alias(self, line):
        """
        /alias <alias> <command> [args]
        """
        arg = common.shell_split(line)
        if len(arg) < 2:
            self.api.information('Alias: Not enough parameters', 'Error')
            return
        alias = arg[0]
        command = arg[1]
        tmp_args = arg[2] if len(arg) > 2 else ''

        if alias in self.core.commands or alias in self.commands:
            self.api.information('Alias: command already exists', 'Error')
            return

        self.commands[alias] = lambda arg: self.get_command(command)(tmp_args + arg)
        self.api.add_command(alias, self.commands[alias], 'This command is an alias for /%s %s' %( command, tmp_args))
        self.api.information('Alias /%s successfuly created' % alias, 'Info')

    def command_unalias(self, alias):
        """
        /unalias <existing alias>
        """
        if alias in self.commands:
            del self.commands[alias]
            self.api.del_command(alias)
            self.api.information('Alias /%s successfuly deleted' % alias, 'Info')

    def completion_unalias(self, the_input):
        aliases = [alias for alias in self.commands]
        aliases.sort()
        return the_input.auto_completion(aliases, '', quotify=False)

    def get_command(self, name):
        """Returns the function associated with a command"""
        def dummy(args):
            """Dummy function called if the command doesn’t exist"""
            pass
        if name in self.core.commands:
            return self.core.commands[name][0]
        elif name in self.api.current_tab().commands:
            return self.api.current_tab().commands[name][0]
        return dummy
