"""
This plugin lets you execute a system command through poezio.

Usage
-----

.. warning:: Running commands that start a daemon or an interface is not a good
             idea.

.. glossary::

    /exec
        **Usage:** ``/exec [-o|-O] <command>``

        Execute a system command.

        ::

            /exec command

        Will give you the result in the information buffer.

        ::

            /exec -o command

        Will send the result of the command into the current tab, if possible.

        ::

            /exec -O command

        Will send the result of the command and the command summary into the current
        tab, if possible.

"""

from poezio.plugin import BasePlugin
from poezio import common
import asyncio
import subprocess

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('exec', self.command_exec,
                usage='[-o|-O] <command>',
                help='Execute a shell command and prints the result in the information buffer. The command should be ONE argument, that means it should be between \"\". The first argument (before the command) can be -o or -O. If -o is specified, it sends the result in the current conversation. If -O is specified, it sends the command and its result in the current conversation.\nExample: /exec -O \"uptime\" will send “uptime\n20:36:19 up  3:47,  4 users,  load average: 0.09, 0.13, 0.09” in the current conversation.',
                short='Execute a command')

    async def async_exec(self, command, arg):
        create = asyncio.create_subprocess_exec('sh', '-c', command,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            process = await create
        except OSError as e:
            self.api.information('Failed to execute command: %s' % (e,), 'Error')
            return
        stdout, stderr = await process.communicate()
        result = stdout.decode('utf-8')
        stderr = stderr.decode('utf-8')
        if arg == '-o':
            if not self.api.send_message('%s' % (result,)):
                self.api.information('Cannot send result (%s), this is not a conversation tab' % result, 'Error')
        elif arg == '-O':
            if not self.api.send_message('%s:\n%s' % (command, result)):
                self.api.information('Cannot send result (%s), this is not a conversation tab' % result, 'Error')
        else:
            self.api.information('%s:\n%s' % (command, result), 'Info')
        if stderr:
            self.api.information('stderr for %s:\n%s' % (command, stderr), 'Info')
        await process.wait()

    def command_exec(self, args):
        args = common.shell_split(args)
        if len(args) == 1:
            command = args[0]
            arg = None
        elif len(args) == 2:
            command = args[1]
            arg = args[0]
        else:
            self.api.run_command('/help exec')
            return
        asyncio.ensure_future(self.async_exec(command, arg))
