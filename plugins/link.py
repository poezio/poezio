# A plugin that adds the /link command, letting you open links that are pasted
# in the conversation, without having to click them.

import re

from plugin import BasePlugin
from xhtml import clean_text
import common
import tabs

url_pattern = re.compile(r'\b(http[s]?://(?:\S+))\b', re.I|re.U)

class Plugin(BasePlugin):
    def init(self):
        for _class in (tabs.MucTab, tabs.PrivateTab, tabs.ConversationTab):
            self.add_tab_command(_class, 'link', self.command_link,
                    usage='[num]',
                    help='Opens the last link from the conversation into a browser.\nIf [num] is given, then it will open the num-th link displayed.',
                    short='Open links into a browser')

    def find_link(self, nb):
        messages = self.core.get_conversation_messages()
        if not messages:
            return None
        for message in messages[::-1]:
            matches = url_pattern.findall(clean_text(message.txt))
            if matches:
                for url in matches[::-1]:
                    if nb == 1:
                        return url
                    else:
                        nb -= 1
        return None

    def command_link(self, args):
        args = common.shell_split(args)
        if len(args) == 1:
            try:
                nb = int(args[0])
            except:
                return self.core.command_help('link')
        else:
            nb = 1
        link = self.find_link(nb)
        if link:
            self.core.exec_command([self.config.get('browser', 'firefox'), link])
        else:
            self.core.information('No URL found.', 'Warning')

    def cleanup(self):
        del self.config
