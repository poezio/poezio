from plugin import BasePlugin
import subprocess

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.figletize)
        self.api.add_event_handler('conversation_say', self.figletize)
        self.api.add_event_handler('private_say', self.figletize)

    def figletize(self, msg, tab):
        process = subprocess.Popen(['figlet', '--', msg['body']], stdout=subprocess.PIPE)
        result = process.communicate()[0].decode('utf-8')
        msg['body'] = result
