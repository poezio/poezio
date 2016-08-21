"""
Usage
-----

This plugin defines two new global commands: :term:`/alias` and :term:`/unalias`.

.. glossary::

    /alias
        **Usage:** ``/alias <name> <command> [args]``

        This command will create a new command, named ``<name>`` (and callable
        with ``/name``), that runs ``/command``, with ``[args]`` as fixed
        args for the command.
        When you run the alias, you can also pass parameters to it, that will be
        given to the original command.

        Example: ::

            /alias toto say koin

        Will bind ``/say koin`` to ``/toto``, so this alias will work in any
        Chat tab. If someone calls it with ::

            /toto koin

        Poezio will then execute ``/say koin koin``.

        Also, you can rebind arguments arbitrarily, with the ``{}`` placeholder.
        For example, ::

            /alias toto say {} le {}
            /toto loulou coucou

        Will execute ``/say loulou le coucou``, because the ``{}`` are
        replaced with the command args, in the order they are given.

        Extra args are still added at the end of the command if provided
        (args used for the formatting are only used for the formatting).

    /unalias
        **Usage:** ``/unalias <name>``

        This command removes a defined alias.


Config
------

The aliases are stored inside the configuration file for the plugin.
You can either use the above commands or write it manually, and it
will be read when the plugin is loaded.


Example of the syntax:

.. code-block:: ini

    [alias]
    toto = say {} le {}
    j = join {}@conference.jabber.org/nick
    jp = say je proteste


"""

from poezio.plugin import BasePlugin
from poezio.common import shell_split
from poezio.core.structs import Completion


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
        self.load_conf()

    def load_conf(self):
        """
        load stored aliases on startup
        """
        for alias in self.config.options():
            full = self.config.get(alias, '')
            if full:
                self.command_alias(alias + ' ' + full, silent=True)

    def command_alias(self, line, silent=False):
        """
        /alias <alias> <command> [args]
        """
        arg = split_args(line)
        if not arg:
            if not silent:
                self.api.information('Alias: Not enough parameters', 'Error')
            return
        alias, command, args = arg

        if alias in self.commands:
            update = True
        elif alias in self.core.commands:
            if not silent:
                self.api.information('Alias: command already exists', 'Error')
            return
        else:
            update = False

        self.config.set(alias, command + ' ' + args)
        self.commands[alias] = command_wrapper(
                generic_command, lambda: self.get_command(command), args)
        self.api.del_command(alias)
        self.api.add_command(alias, self.commands[alias],
                             'This command is an alias for /%s %s' %
                                (alias, command))

        if not silent:
            if update:
                self.api.information('Alias /%s updated' % alias, 'Info')
            else:
                self.api.information('Alias /%s successfuly created' % alias,
                                 'Info')

    def command_unalias(self, alias):
        """
        /unalias <existing alias>
        """
        if alias in self.commands:
            del self.commands[alias]
            self.api.del_command(alias)
            self.config.remove(alias)
            self.api.information('Alias /%s successfuly deleted' % alias, 'Info')

    def completion_unalias(self, the_input):
        "Completion for /unalias"
        aliases = [alias for alias in self.commands]
        aliases.sort()
        return Completion(the_input.auto_completion, aliases, '', quotify=False)

    def get_command(self, name):
        """Returns the function associated with a command"""
        def dummy(args):
            """Dummy function called if the command doesn’t exist"""
            pass
        if name in self.commands:
            return dummy
        elif name in self.core.commands:
            return self.core.commands[name].func
        elif name in self.api.current_tab().commands:
            return self.api.current_tab().commands[name].func
        return dummy

def split_args(line):
    """
    Extract the relevant vars from the command line
    """
    arg = line.split()
    if len(arg) < 2:
        return None
    alias_pos = line.find(' ')
    alias = line[:alias_pos]
    end = line[alias_pos+1:]
    args_pos = end.find(' ')
    if args_pos == -1:
        command = end
        args = ''
    else:
        command = end[:args_pos]
        args = end[args_pos+1:]
    return (alias, command, args)

def generic_command(command, extra_args, args):
    """
    Function that will execute the command and set the relevant
    parameters (format string, etc).
    """
    args = shell_split(args)
    new_extra_args = extra_args.format(*args)
    count = extra_args.count('{}')
    args = args[count:]
    new_extra_args += ' '.join(args)
    return command()(new_extra_args)

def command_wrapper(func, command, extra_args):
    "set the predefined arguments"
    def wrapper(*args, **kwargs):
        return func(command, extra_args, *args, **kwargs)
    return wrapper


