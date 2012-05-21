"""
Define the PluginConfig and Plugin classes, plus the SafetyMetaclass.
These are used in the plugin system added in poezio 0.7.5
(see plugin_manager.py)
"""
import os
from configparser import RawConfigParser
import config
import inspect
import traceback

class PluginConfig(config.Config):
    """
    Plugin configuration object.
    They are accessible inside the plugin with self.config
    and behave like the core Config object.
    """
    def __init__(self, filename, module_name):
        self.file_name = filename
        self.module_name = module_name
        RawConfigParser.__init__(self, None)
        self.read()

    def get(self, option, default, section=None):
        if not section:
            section = self.module_name
        return config.Config.get(self, option, default, section)

    def set(self, option, default, section=None):
        if not section:
            section = self.module_name
        return config.Config.set(self, option, default, section)

    def read(self):
        """Read the config file"""
        RawConfigParser.read(self, self.file_name)
        if not self.has_section(self.module_name):
            self.add_section(self.module_name)

    def options(self, section=None):
        """
            Return the options of the section
            If no section is given, it defaults to the plugin name.
        """
        if not section:
            section = self.module_name
        if not self.has_section(section):
            self.add_section(section)
        return config.Config.options(self, section)

    def write(self):
        """Write the config to the disk"""
        try:
            fp = open(self.file_name, 'w')
            RawConfigParser.write(self, fp)
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
    Class that all plugins derive from.
    """

    def __init__(self, plugin_manager, core, plugins_conf_dir):
        self.core = core
        # More hack; luckily we'll never have more than one core object
        SafetyMetaclass.core = core
        self.plugin_manager = plugin_manager
        conf = os.path.join(plugins_conf_dir, self.__module__+'.cfg')
        self.config = PluginConfig(conf, self.__module__)
        self.init()

    def init(self):
        """
        Method called at the creation of the plugin.
        Do not overwrite __init__ and use this instead.
        """
        pass

    def cleanup(self):
        """
        Called when the plugin is unloaded.
        Overwrite this if you want to erase or save things before the plugin is disabled.
        """
        pass

    def unload(self):
        self.cleanup()

    def add_command(self, name, handler, help, completion=None):
        """
        Add a global command.
        You cannot overwrite the existing commands.
        """
        return self.plugin_manager.add_command(self.__module__, name, handler, help, completion)

    def del_command(self, name):
        """
        Remove a global command.
        This only works if the command was added by the plugin
        """
        return self.plugin_manager.del_command(self.__module__, name)

    def add_key(self, key, handler):
        """
        Add a global keybind
        """
        return self.plugin_manager.add_key(self.__module__, key, handler)

    def del_key(self, key):
        """
        Remove a global keybind
        """
        return self.plugin_manager.del_key(self.__module__, key)

    def add_tab_key(self, tab_type, key, handler):
        """
        Add a keybind only for a type of tab.
        """
        return self.plugin_manager.add_tab_key(self.__module__, tab_type, key, handler)

    def del_tab_key(self, tab_type, key):
        """
        Remove a keybind added through add_tab_key.
        """
        return self.plugin_manager.del_tab_key(self.__module__, tab_type, key)

    def add_tab_command(self, tab_type, name, handler, help, completion=None):
        """
        Add a command only for a type of tab.
        """
        return self.plugin_manager.add_tab_command(self.__module__, tab_type, name, handler, help, completion)

    def del_tab_command(self, tab_type, name):
        """
        Delete a command added through add_tab_command.
        """
        return self.plugin_manager.del_tab_command(self.__module__, tab_type, name)

    def add_event_handler(self, event_name, handler, position=0):
        """
        Add an event handler to the event event_name.
        An optional position in the event handler list can be provided.
        """
        return self.plugin_manager.add_event_handler(self.__module__, event_name, handler, position)

    def del_event_handler(self, event_name, handler):
        """
        Remove 'handler' from the event list for 'event_name'.
        """
        return self.plugin_manager.del_event_handler(self.__module__, event_name, handler)
