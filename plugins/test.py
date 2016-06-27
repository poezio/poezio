from poezio.plugin import BasePlugin
from poezio import tabs

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('plugintest', self.command_plugintest, 'Test command')
        self.api.add_tab_command(tabs.MucTab, 'plugintest', self.command_tab_plugintest, 'Test command')
        self.api.add_slix_event_handler('message', self.on_message)
        self.api.information("Plugin loaded")

    def cleanup(self):
        self.api.information("Plugin unloaded")

    def on_message(self, message):
        self.api.information("Test plugin received message: {}".format(message))

    def command_tab_plugintest(self, args):
        self.api.information("Command for MucTabs! With args {}".format(args))
        self.api.del_tab_command(tabs.MucTab, 'plugintest')

    def command_plugintest(self, args):
        self.api.information("Command! With args {}".format(args))
