from plugin import BasePlugin
import tabs

class Plugin(BasePlugin):
    def init(self):
        self.add_command('plugintest', self.command_plugintest, 'Test command')
        self.add_tab_command(tabs.MucTab, 'plugintest', self.command_tab_plugintest, 'Test command')
        self.add_event_handler('message', self.on_message)
        self.core.information("Plugin loaded")

    def cleanup(self):
        self.core.information("Plugin unloaded")

    def on_message(self, message):
        self.core.information("Test plugin received message: {}".format(message))

    def command_tab_plugintest(self, args):
        self.core.information("Command for MucTabs! With args {}".format(args))
        self.del_tab_command(tabs.MucTab, 'plugintest')

    def command_plugintest(self, args):
        self.core.information("Command! With args {}".format(args))
