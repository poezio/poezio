# A plugin that adds the /display_corrections command, to view the previous
# versions of a corrected message.

from plugin import BasePlugin
from common import shell_split
import tabs

class Plugin(BasePlugin):
    def init(self):
        usage = 'Usage: /display_corrections <number>\nDisplay_corrections: display all the corrections of the number-th last corrected message.'
        for tab_type in (tabs.MucTab, tabs.PrivateTab, tabs.ConversationTab):
            self.add_tab_command(tab_type, 'display_corrections', self.command_display_corrections, usage)

    def find_corrected(self, nb):
        messages = self.core.get_conversation_messages()
        if not messages:
            return None
        for message in messages[::-1]:
            if message.old_message:
                if nb == 1:
                    return message
                else:
                    nb -= 1
        return None

    def command_display_corrections(self, args):
        args = shell_split(args)
        if len(args) == 1:
            try:
                nb = int(args[0])
            except:
                return self.core.command_help('display_corrections')
        else:
            nb = 1
        message = self.find_corrected(nb)
        if message:
            display = []
            while message:
                display.append('%s %s%s%s %s' % (message.str_time, '* ' if message.me else '', message.nickname, '' if message.me else '>', message.txt))
                message = message.old_message
            self.core.information('Older versions:\n' + '\n'.join(display[::-1]), 'Info')
        else:
            self.core.information('No corrected message found.', 'Warning')

    def cleanup(self):
        del self.config
