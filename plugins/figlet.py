from plugin import BasePlugin
import subprocess

class Plugin(BasePlugin):
    def init(self):
        self.add_event_handler('muc_say', self.figletize)
        self.add_event_handler('conversation_say', self.figletize)
        self.add_event_handler('private_say', self.figletize)

    def figletize(self, msg):
        process = subprocess.Popen(['figlet', msg['body']], stdout=subprocess.PIPE)
        result = process.communicate()[0].decode('utf-8')
        msg['body'] = result
