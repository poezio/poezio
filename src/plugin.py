import os
from configparser import ConfigParser
import config
import inspect
import traceback

class PluginConfig(config.Config):
    def __init__(self, filename):
        ConfigParser.__init__(self)
        self.__config_file__ = filename
        self.read()

    def read(self):
        """Read the config file"""
        ConfigParser.read(self, self.__config_file__)

    def write(self):
        """Write the config to the disk"""
        try:
            fp = open(self.__config_file__, 'w')
            ConfigParser.write(self, fp)
            fp.close()
            return True
        except IOError:
            return False


class SafetyMetaclass(type):
    # A hack
    core = None

    @staticmethod
    def safe_func(f):
        def helper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except:
                if inspect.stack()[1][1] == inspect.getfile(f):
                    raise
                elif SafetyMetaclass.core:
                    SafetyMetaclass.core.information(traceback.format_exc())
                    return None
        return helper

    def __new__(meta, name, bases, class_dict):
        for k, v in class_dict.items():
            if inspect.isfunction(v):
                class_dict[k] = SafetyMetaclass.safe_func(v)
        return type.__new__(meta, name, bases, class_dict)

class BasePlugin(object, metaclass=SafetyMetaclass):
    """
    Class that all plugins derive from.  Any methods beginning with command_
    are interpreted as a command and beginning with on_ are interpreted as
    event handlers
    """

    def __init__(self, plugin_manager, core, plugins_conf_dir):
        self.core = core
        # More hack; luckily we'll never have more than one core object
        SafetyMetaclass.core = core
        self.plugin_manager = plugin_manager
        conf = os.path.join(plugins_conf_dir, self.__module__+'.cfg')
        self.config = PluginConfig(conf)
        self.init()

    def init(self):
        pass

    def cleanup(self):
        pass

    def unload(self):
        self.cleanup()

    def add_command(self, name, handler, help, completion=None):
        return self.plugin_manager.add_command(self.__module__, name, handler, help, completion)

    def del_command(self, name):
        return self.plugin_manager.del_command(self.__module__, name)

    def add_event_handler(self, event_name, handler):
        return self.plugin_manager.add_event_handler(self.__module__, event_name, handler)

    def del_event_handler(self, event_name, handler):
        return self.plugin_manager.del_event_handler(self.__module__, event_name, handler)

    def add_poezio_event_handler(self, event_name, handler, position=0):
        return self.plugin_manager.add_poezio_event_handler(self.__module__, event_name, handler, position)

    def del_poezio_event_handler(self, event_name, handler):
        return self.plugin_manager.del_poezio_event_handler(self.__module__, event_name, handler)
