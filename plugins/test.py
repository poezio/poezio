from plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):
        self.add_command('plugintest', self.command_plugintest, 'Test command')
        self.add_event_handler('message', self.on_message)
        self.core.information("Plugin loaded")
        self.core.connect('enter', self.on_enter)

    def cleanup(self):
        self.core.information("Plugin unloaded")

    def on_enter(self, line):
        self.core.information('Text sent: {}'.format(line))

    def on_message(self, message):
        self.core.information("Test plugin received message: {}".format(message))

    def command_plugintest(self, args):
        self.core.information("Command! With args {}".format(args))
