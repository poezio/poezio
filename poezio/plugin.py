"""
Define the PluginConfig and Plugin classes, plus the SafetyMetaclass.
These are used in the plugin system added in poezio 0.7.5
(see plugin_manager.py)
"""
from functools import partial
from configparser import RawConfigParser
from poezio.timed_events import TimedEvent, DelayedEvent
from poezio import config
import inspect
import traceback
import logging
log = logging.getLogger(__name__)


class PluginConfig(config.Config):
    """
    Plugin configuration object.
    They are accessible inside the plugin with self.config
    and behave like the core Config object.
    """

    def __init__(self, filename, module_name, default=None):
        config.Config.__init__(self, filename, default=default)
        self.module_name = module_name
        self.read()

    def get(self, option, default=None, section=None):
        if not section:
            section = self.module_name
        return config.Config.get(self, option, default, section)

    def set(self, option, default, section=None):
        if not section:
            section = self.module_name
        return config.Config.set_and_save(self, option, default, section)

    def remove(self, option, section=None):
        if not section:
            section = self.module_name
        return config.Config.remove_and_save(self, option, section)

    def read(self):
        """Read the config file"""
        RawConfigParser.read(self, str(self.file_name))
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
            with self.file_name.open('w') as fp:
                RawConfigParser.write(self, fp)
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
                    log.error('Error in a plugin', exc_info=True)
                    SafetyMetaclass.core.information(traceback.format_exc(),
                                                     'Error')
                    return None

        return helper

    def __new__(meta, name, bases, class_dict):
        for k, v in class_dict.items():
            if inspect.isfunction(v):
                if k != '__init__' and k != 'init':
                    class_dict[k] = SafetyMetaclass.safe_func(v)
        return type.__new__(meta, name, bases, class_dict)


class PluginWrap:
    """
    A wrapper to implicitly pass the module name to PluginAPI
    """

    def __init__(self, api, module):
        self.api = api
        self.module = module

    def __getattribute__(self, name):
        api = object.__getattribute__(self, 'api')
        module = object.__getattribute__(self, 'module')
        return partial(getattr(api, name), module)


class PluginAPI:
    """
    The public API exposed to the plugins.
    Its goal is to limit the use of the raw Core object
    as much as possible.
    """

    def __init__(self, core, plugin_manager):
        self.core = core
        self.plugin_manager = plugin_manager

    def __getitem__(self, value):
        return PluginWrap(self, value)

    def send_message(self, _, *args, **kwargs):
        """
        Send a message to the current tab.

        :param str msg: The message to send.
        """
        return self.core.send_message(*args, **kwargs)

    def get_conversation_messages(self, _, *args, **kwargs):
        """
        Get all the Messages of the current Tab.

        :returns: The list of :py:class:`text_buffer.Message` objects.
        :returns: None if the Tab does not inherit from ChatTab.
        :rtype: :py:class:`list`
        """
        return self.core.get_conversation_messages()

    def add_timed_event(self, _, *args, **kwargs):
        """
        Schedule a timed event.

        :param timed_events.TimedEvent event: The timed event to schedule.
        """
        return self.core.add_timed_event(*args, **kwargs)

    def remove_timed_event(self, _, *args, **kwargs):
        """
        Unschedule a timed event.

        :param timed_events.TimedEvent event: The event to unschedule.
        """
        return self.core.remove_timed_event(*args, **kwargs)

    def create_timed_event(self, _, *args, **kwargs):
        """
        Create a timed event, but do not schedule it;
        :py:func:`~PluginAPI.add_timed_event` must be used for that.

        :param datetime.datetime date: The time at which the handler must be executed
        :param function callback: The handler that will be executed
        :param args: Optional arguments passed to the handler.
        :return: The created event.
        :rtype: :py:class:`timed_events.TimedEvent`
        """
        return TimedEvent(*args, **kwargs)

    def create_delayed_event(self, _, *args, **kwargs):
        """
        Create a delayed event, but do not schedule it;
        :py:func:`~PluginAPI.add_timed_event` must be used for that.

        A delayed event is a timed event with a delay from the time
        this function is called (instead of a datetime).

        :param int delay: The number of seconds to schedule the execution
        :param function callback: The handler that will be executed
        :param args: Optional arguments passed to the handler.
        :return: The created event.
        :rtype: :py:class:`timed_events.DelayedEvent`
        """
        return DelayedEvent(*args, **kwargs)

    def information(self, _, *args, **kwargs):
        """
        Display a new message in the information buffer.

        :param str msg: The message to display.
        :param str typ: The message type (e.g. Info, Error…)
        """
        return self.core.information(*args, **kwargs)

    def current_tab(self, _):
        """
        Get the current Tab.

        :returns: The current tab.
        """
        return self.core.tabs.current_tab

    def get_status(self, _):
        """
        Get the current user global status.

        :returns Status: The current status.
        """
        return self.core.get_status()

    def run_command(self, _, *args, **kwargs):
        """
        Run a command from the current tab.
        (a command starts with a /, if not, it’s a message)

        :param str line: The command to run.
        """
        return self.core.tabs.current_tab.execute_command(*args, **kwargs)

    def all_tabs(self, _):
        """
        Return a list of all opened tabs

        :returns list: The list of tabs.
        """
        return self.core.tabs

    def add_command(self, module, *args, **kwargs):
        """
        Add a global command.

        :param str name: The name of the command (/name)
        :param function handler: The function called when the command is run.
        :param str help: The complete help for that command.
        :param str short: A short description of the command.
        :param function completion: The completion function for that command
            (optional)
        :param str usage: A string showing the required and optional args
            of the command. Optional args should be surrounded by []
            and mandatory args should be surrounded by <>.

            Example string: "<server> [port]"

        :raises Exception: If the command already exists.
        """
        return self.plugin_manager.add_command(module, *args, **kwargs)

    def del_command(self, module, *args, **kwargs):
        """
        Remove a global command.

        :param str name: The name of the command to remove.
            That command _must_ have been added by the same plugin
        """
        return self.plugin_manager.del_command(module, *args, **kwargs)

    def add_key(self, module, *args, **kwargs):
        """
        Associate a global binding to a handler.

        :param str key: The curses representation of the binding.
        :param function handler: The function called when the binding is pressed.

        :raise Exception: If the binding is already present.
        """
        return self.plugin_manager.add_key(module, *args, **kwargs)

    def del_key(self, module, *args, **kwargs):
        """
        Remove a global binding.

        :param str key: The binding to remove.
        """
        return self.plugin_manager.del_key(module, *args, **kwargs)

    def add_tab_key(self, module, *args, **kwargs):
        """
        Associate a binding to a handler, but only for a certain tab type.

        :param Tab tab_type: The type of tab to target.
        :param str key: The binding to add.
        :param function handler: The function called when the binding is pressed
        """
        return self.plugin_manager.add_tab_key(module, *args, **kwargs)

    def del_tab_key(self, module, *args, **kwargs):
        """
        Remove a binding added with add_tab_key

        :param tabs.Tab tab_type: The type of tab to target.
        :param str key: The binding to remove.
        """
        return self.plugin_manager.del_tab_key(module, *args, **kwargs)

    def add_tab_command(self, module, *args, **kwargs):
        """
        Add a command to only one type of tab.

        :param tabs.Tab tab_type: The type of Tab to target.
        :param str name: The name of the command (/name)
        :param function handler: The function called when the command is run.
        :param str help: The complete help for that command.
        :param str short: A short description of the command.
        :param function completion: The completion function for that command
            (optional)
        :param str usage: A string showing the required and optional args
            of the command. Optional args should be surrounded by []
            and mandatory args should be surrounded by <>.

            Example string: "<server> [port]"

        :raise Exception: If the command already exists.
        """
        return self.plugin_manager.add_tab_command(module, *args, **kwargs)

    def del_tab_command(self, module, *args, **kwargs):
        """
        Remove a tab-specific command.

        :param tabs.Tab tab_type: The type of tab to target.
        :param str name: The name of the command to remove.
            That command _must_ have been added by the same plugin
        """
        return self.plugin_manager.del_tab_command(module, *args, **kwargs)

    def add_event_handler(self, module, *args, **kwargs):
        """
        Add an event handler for a poezio event.

        :param str event_name: The event name.
        :param function handler: The handler function.
        :param int position: The position of that handler in the handler list.
            This is useful for plugins like OTR, which must be the last
            function called on the text.
            Defaults to 0.

        A complete list of those events can be found at
        https://doc.poez.io/dev/events.html
        """
        return self.plugin_manager.add_event_handler(module, *args, **kwargs)

    def del_event_handler(self, module, *args, **kwargs):
        """
        Remove a handler for a poezio event.

        :param str event_name: The name of the targeted event.
        :param function handler: The function to remove from the handlers.
        """
        return self.plugin_manager.del_event_handler(module, *args, **kwargs)

    def add_slix_event_handler(self, module, event_name, handler):
        """
        Add an event handler for a slixmpp event.

        :param str event_name: The event name.
        :param function handler: The handler function.

        A list of the slixmpp events can be found here
        http://sleekxmpp.com/event_index.html
        """
        self.core.xmpp.add_event_handler(event_name, handler)

    def del_slix_event_handler(self, module, event_name, handler):
        """
        Remove a handler for a slixmpp event

        :param str event_name: The name of the targeted event.
        :param function handler: The function to remove from the handlers.
        """
        self.core.xmpp.del_event_handler(event_name, handler)


class BasePlugin(object, metaclass=SafetyMetaclass):
    """
    Class that all plugins derive from.
    """

    default_config = None

    def __init__(self, plugin_api, core, plugins_conf_dir):
        self.core = core
        # More hack; luckily we'll never have more than one core object
        SafetyMetaclass.core = core
        conf = plugins_conf_dir / (self.__module__ + '.cfg')
        try:
            self.config = PluginConfig(
                conf, self.__module__, default=self.default_config)
        except Exception:
            log.debug('Error while creating the plugin config', exc_info=True)
            self.config = PluginConfig(conf, self.__module__)
        self._api = plugin_api[self.name]
        self.init()

    @property
    def name(self):
        """
        Get the name (module name) of the plugin.
        """
        return self.__module__

    @property
    def api(self):
        return self._api

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

    def add_command(self,
                    name,
                    handler,
                    help,
                    completion=None,
                    short='',
                    usage=''):
        """
        Add a global command.
        You cannot overwrite the existing commands.
        """
        return self.api.add_command(
            name,
            handler,
            help,
            completion=completion,
            short=short,
            usage=usage)

    def del_command(self, name):
        """
        Remove a global command.
        This only works if the command was added by the plugin
        """
        return self.api.del_command(name)

    def add_key(self, key, handler):
        """
        Add a global keybind
        """
        return self.api.add_key(key, handler)

    def del_key(self, key):
        """
        Remove a global keybind
        """
        return self.api.del_key(key)

    def add_tab_key(self, tab_type, key, handler):
        """
        Add a keybind only for a type of tab.
        """
        return self.api.add_tab_key(tab_type, key, handler)

    def del_tab_key(self, tab_type, key):
        """
        Remove a keybind added through add_tab_key.
        """
        return self.api.del_tab_key(tab_type, key)

    def add_tab_command(self,
                        tab_type,
                        name,
                        handler,
                        help,
                        completion=None,
                        short='',
                        usage=''):
        """
        Add a command only for a type of tab.
        """
        return self.api.add_tab_command(
            tab_type,
            name,
            handler,
            help,
            completion=completion,
            short=short,
            usage=usage)

    def del_tab_command(self, tab_type, name):
        """
        Delete a command added through add_tab_command.
        """
        return self.api.del_tab_command(tab_type, name)

    def add_event_handler(self, event_name, handler, position=0):
        """
        Add an event handler to the event event_name.
        An optional position in the event handler list can be provided.
        """
        return self.api.add_event_handler(event_name, handler, position)

    def del_event_handler(self, event_name, handler):
        """
        Remove 'handler' from the event list for 'event_name'.
        """
        return self.api.del_event_handler(event_name, handler)
