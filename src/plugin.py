import inspect

class BasePlugin(object):
    """
    Class that all plugins derive from.  Any methods beginning with command_
    are interpreted as a command and beginning with on_ are interpreted as
    event handlers
    """

    def __init__(self, core):
        self.core = core
        for k, v in inspect.getmembers(self, inspect.ismethod):
            if k.startswith('on_'):
                core.xmpp.add_event_handler(k[3:], v)
            elif k.startswith('command_'):
                command = k[len('command_'):]
                core.commands[command] = (v, v.__doc__, None)
        self.init()

    def init(self):
        pass

    def cleanup(self):
        pass

    def unload(self):
        for k, v in inspect.getmembers(self, inspect.ismethod):
            if k.startswith('on_'):
                self.core.xmpp.del_event_handler(k[3:], v)
            elif k.startswith('command_'):
                command = k[len('command_'):]
                del self.core.commands[command]
        self.cleanup()
