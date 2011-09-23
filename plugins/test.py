class Plugin(BasePlugin):
    def init(self):
        self.core.information("Plugin loaded")

    def cleanup(self):
        self.core.information("Plugin unloaded")

    def on_message(self, message):
        self.core.information("Test plugin received message: {}".format(message))

    def command_plugintest(self, args):
        self.core.information("Command! With args {}".format(args))
