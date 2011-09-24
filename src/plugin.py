class BasePlugin(object):
    """
    Class that all plugins derive from.  Any methods beginning with command_
    are interpreted as a command and beginning with on_ are interpreted as
    event handlers
    """

    def __init__(self, plugin_manager, core):
        self.core = core
        self.plugin_manager = plugin_manager
        self.init()

    def init(self):
        pass

    def cleanup(self):
        pass

    def unload(self):
        self.cleanup()

    def add_command(self, name, handler, help, completion=None):
        return self.plugin_manager.add_command(self.__module__, name, handler, help, completion)

    def add_event_handler(self, event_name, handler):
        return self.plugin_manager.add_event_handler(self.__module__, event_name, handler)

    def del_event_handler(self, event_name, handler):
        return self.plugin_manager.del_event_handler(self.__module__, event_name, handler)
