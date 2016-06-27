"""
Lists old versions of a corrected message.

Usage
-----

.. glossary::

    /display_corrections
        **Usage:** ``/display_corrections [number]``

        This command lists the old versions of a message.

        Without argument, it will list the last corrected message if there
        is any. If you give an integer as an argument, ``/display_corrections``
        will go back gradually in the buffer to find the message matching
        that number (starting from 1, for the last corrected message).

        If you are scrolling in the buffer, Poezio will list the corrected messages
        starting from the first you can see.  (although there are some problems with
        multiline messages).


"""
from poezio.plugin import BasePlugin
from poezio.common import shell_split
from poezio import tabs

class Plugin(BasePlugin):
    def init(self):
        for tab_type in (tabs.MucTab, tabs.PrivateTab, tabs.ConversationTab):
            self.api.add_tab_command(tab_type, 'display_corrections',
                    handler=self.command_display_corrections,
                    usage='<number>',
                    help='Display all the corrections of the number-th last corrected message.',
                    short='Display the corrections of a message')

    def find_corrected(self, nb):
        messages = self.api.get_conversation_messages()
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
                return self.api.run_command('/help display_corrections')
        else:
            nb = 1
        message = self.find_corrected(nb)
        if message:
            display = []
            while message:
                display.append('%s %s%s%s %s' % (message.str_time, '* ' if message.me else '', message.nickname, '' if message.me else '>', message.txt))
                message = message.old_message
            self.api.information('Older versions:\n' + '\n'.join(display[::-1]), 'Info')
        else:
            self.api.information('No corrected message found.', 'Warning')

    def cleanup(self):
        del self.config
