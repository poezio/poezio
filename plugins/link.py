# A plugin that adds the /link command, letting you open links that are pasted
# in the conversation, without having to click them.

import re

from plugin import BasePlugin, PluginConfig
from xhtml import clean_text
import common

url_pattern = re.compile(r'\b(http[s]?://(?:\S+))\b', re.I|re.U)

class Plugin(BasePlugin):
    def init(self):
        self.add_command('link', self.command_link, "Usage: /link\nLink: opens the last link from the conversation into a browser.")

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
            link = re.sub("'", "\\'", link)
            link = re.sub('"', '\\"', link)
            self.core.exec_command("%s %s" % (self.config.get('browser', 'firefox'), link))
        else:
            self.core.information('No URL found.', 'Warning')

    def cleanup(self):
        del self.config
