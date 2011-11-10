# A plugin that can execute a command and send the result in the conversation

from plugin import BasePlugin
import os
import common
import shlex
import subprocess

class Plugin(BasePlugin):
    def init(self):
        self.add_command('exec', self.command_exec, "Usage: /exec [-o|-O] <command>\nExec: Execute a shell command and prints the result in the information buffer. The command should be ONE argument, that means it should be between \"\". The first argument (before the command) can be -o or -O. If -o is specified, it sends the result in the current conversation. If -O is specified, it sends the command and its result in the current conversation.\nExample: /exec -O \"uptime\" will send “uptime\n20:36:19 up  3:47,  4 users,  load average: 0.09, 0.13, 0.09” in the current conversation.")

    def command_exec(self, args):
        args = common.shell_split(args)
        if len(args) == 1:
            command = args[0]
            arg = None
        elif len(args) == 2:
            command = args[1]
            arg = args[0]
        else:
            self.core.command_help('exec')
            return
        try:
            process = subprocess.Popen(['sh', '-c', command], stdout=subprocess.PIPE)
        except OSError as e:
            self.core.information('Failed to execute command: %s' % (e,), 'Error')
            return
        result = process.communicate()[0].decode('utf-8')
        if arg and arg == '-o':
            if not self.core.send_message('%s' % (result,)):
                self.core.information('Cannot send result (%s), this is not a conversation tab' % result)
        elif arg and arg == '-O':
            if not self.core.send_message('%s:\n%s' % (command, result)):
                self.core.information('Cannot send result (%s), this is not a conversation tab' % result)
        else:
            self.core.information('%s:\n%s' % (command, result), 'Info')
        return
