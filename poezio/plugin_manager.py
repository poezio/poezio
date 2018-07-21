"""
Plugin manager module.
Define the PluginManager class, the one that glues all the plugins and
the API together. Defines also a bunch of variables related to the
plugin env.
"""

import os
from os import path
from pathlib import Path
import logging

from poezio import tabs, xdg
from poezio.core.structs import Command, Completion
from poezio.plugin import PluginAPI
from poezio.config import config

log = logging.getLogger(__name__)


class PluginManager:
    """
    Plugin Manager
    Contains all the references to the plugins
    And keeps track of everything the plugin has done through the API.
    """

    def __init__(self, core):
        self.core = core
        # module name -> module object
        self.modules = {}
        # module name -> plugin object
        self.plugins = {}
        # module name -> dict of commands loaded for the module
        self.commands = {}
        # module name -> list of event_name/handler pairs loaded for the module
        self.event_handlers = {}
        # module name -> dict of tab types; tab type -> commands
        # loaded by the module
        self.tab_commands = {}
        # module name → dict of keys/handlers loaded for the module
        self.keys = {}
        # module name → dict of tab types; tab type → list of keybinds (tuples)
        self.tab_keys = {}
        self.roster_elements = {}

        from importlib import machinery
        self.finder = machinery.PathFinder()

        self.initial_set_plugins_dir()
        self.initial_set_plugins_conf_dir()
        self.fill_load_path()

        self.plugin_api = PluginAPI(core, self)

    def disable_plugins(self):
        for plugin in set(self.plugins.keys()):
            self.unload(plugin, notify=False)

    def load(self, name, notify=True):
        """
        Load a plugin.
        """
        if name in self.plugins:
            self.unload(name)

        try:
            module = None
            loader = self.finder.find_module(name, self.load_path)
            if not loader:
                self.core.information('Could not find plugin: %s' % name,
                                      'Error')
                return
            module = loader.load_module()
        except Exception as e:
            log.debug("Could not load plugin %s", name, exc_info=True)
            self.core.information("Could not load plugin %s: %s" % (name, e),
                                  'Error')
        finally:
            if not module:
                return

        self.modules[name] = module
        self.commands[name] = {}
        self.keys[name] = {}
        self.tab_keys[name] = {}
        self.tab_commands[name] = {}
        self.event_handlers[name] = []
        try:
            self.plugins[name] = None
            self.plugins[name] = module.Plugin(self.plugin_api, self.core,
                                               self.plugins_conf_dir)
        except Exception as e:
            log.error('Error while loading the plugin %s', name, exc_info=True)
            if notify:
                self.core.information(
                    'Unable to load the plugin %s: %s' % (name, e), 'Error')
            self.unload(name, notify=False)
        else:
            if notify:
                self.core.information('Plugin %s loaded' % name, 'Info')

    def unload(self, name, notify=True):
        if name in self.plugins:
            try:
                for command in self.commands[name].keys():
                    del self.core.commands[command]
                for key in self.keys[name].keys():
                    del self.core.key_func[key]
                for tab in list(self.tab_commands[name].keys()):
                    for command in self.tab_commands[name][tab][:]:
                        self.del_tab_command(name, getattr(tabs, tab),
                                             command[0])
                    del self.tab_commands[name][tab]
                for tab in list(self.tab_keys[name].keys()):
                    for key in self.tab_keys[name][tab][:]:
                        self.del_tab_key(name, getattr(tabs, tab), key[0])
                    del self.tab_keys[name][tab]
                for event_name, handler in self.event_handlers[name][:]:
                    self.del_event_handler(name, event_name, handler)

                if self.plugins[name] is not None:
                    self.plugins[name].unload()
                del self.plugins[name]
                del self.commands[name]
                del self.keys[name]
                del self.tab_commands[name]
                del self.event_handlers[name]
                if notify:
                    self.core.information('Plugin %s unloaded' % name, 'Info')
            except Exception as e:
                log.debug("Could not unload plugin %s", name, exc_info=True)
                self.core.information(
                    "Could not unload plugin %s: %s" % (name, e), 'Error')

    def add_command(self,
                    module_name,
                    name,
                    handler,
                    help,
                    completion=None,
                    short='',
                    usage=''):
        """
        Add a global command.
        """
        if name in self.core.commands:
            raise Exception("Command '%s' already exists" % (name, ))

        commands = self.commands[module_name]
        commands[name] = Command(handler, help, completion, short, usage)
        self.core.commands[name] = commands[name]

    def del_command(self, module_name, name):
        """
        Remove a global command added through add_command.
        """
        if name in self.commands[module_name]:
            del self.commands[module_name][name]
            if name in self.core.commands:
                del self.core.commands[name]

    def add_tab_command(self,
                        module_name,
                        tab_type,
                        name,
                        handler,
                        help,
                        completion=None,
                        short='',
                        usage=''):
        """
        Add a command only for a type of Tab.
        """
        commands = self.tab_commands[module_name]
        t = tab_type.__name__
        if name in tab_type.plugin_commands:
            return
        if t not in commands:
            commands[t] = []
        commands[t].append((name, handler, help, completion))
        tab_type.plugin_commands[name] = Command(handler, help, completion,
                                                 short, usage)
        for tab in self.core.tabs:
            if isinstance(tab, tab_type):
                tab.update_commands()

    def del_tab_command(self, module_name, tab_type, name):
        """
        Remove a command added through add_tab_command.
        """
        commands = self.tab_commands[module_name]
        t = tab_type.__name__
        if t not in commands:
            return
        for command in commands[t]:
            if command[0] == name:
                commands[t].remove(command)
                del tab_type.plugin_commands[name]
                for tab in self.core.tabs:
                    if isinstance(tab, tab_type) and name in tab.commands:
                        del tab.commands[name]

    def add_tab_key(self, module_name, tab_type, key, handler):
        """
        Associate a key binding to a handler only for a type of Tab.
        """
        keys = self.tab_keys[module_name]
        t = tab_type.__name__
        if key in tab_type.plugin_keys:
            return
        if t not in keys:
            keys[t] = []
        keys[t].append((key, handler))
        tab_type.plugin_keys[key] = handler
        for tab in self.core.tabs:
            if isinstance(tab, tab_type):
                tab.update_keys()

    def del_tab_key(self, module_name, tab_type, key):
        """
        Remove a key binding added through add_tab_key.
        """
        keys = self.tab_keys[module_name]
        t = tab_type.__name__
        if t not in keys:
            return
        for _key in keys[t]:
            if _key[0] == key:
                keys[t].remove(_key)
                del tab_type.plugin_keys[key]
                for tab in self.core.tabs:
                    if isinstance(tab, tab_type) and key in tab.key_func:
                        del tab.key_func[key]

    def add_key(self, module_name, key, handler):
        """
        Associate a global key binding to a handler, except if it
        already exists.
        """
        if key in self.core.key_func:
            raise Exception("Key '%s' already exists" % (key, ))
        keys = self.keys[module_name]
        keys[key] = handler
        self.core.key_func[key] = handler

    def del_key(self, module_name, key):
        """
        Remove a global key binding added by a plugin.
        """
        if key in self.keys[module_name]:
            del self.keys[module_name][key]
            if key in self.core.key_func:
                del self.core.commands[key]

    def add_event_handler(self, module_name, event_name, handler, position=0):
        """
        Add an event handler. If event_name isn’t in the event list, assume
        it is a slixmpp event.
        """
        eh = self.event_handlers[module_name]
        eh.append((event_name, handler))
        if event_name in self.core.events.events:
            self.core.events.add_event_handler(event_name, handler, position)
        else:
            self.core.xmpp.add_event_handler(event_name, handler)

    def del_event_handler(self, module_name, event_name, handler):
        """
        Remove an event handler if it exists.
        """
        if event_name in self.core.events.events:
            self.core.events.del_event_handler(None, handler)
        else:
            self.core.xmpp.del_event_handler(event_name, handler)
        eh = self.event_handlers[module_name]
        eh = [e for e in eh if e != (event_name, handler)]

    def completion_load(self, the_input):
        """
        completion function that completes the name of the plugins, from
        all .py files in plugins_dir
        """
        names = set()
        for path_ in self.load_path:
            try:
                add = set(os.listdir(path_))
                names |= add
            except OSError:
                pass
        plugins_files = [
            name[:-3] for name in names if name.endswith('.py')
            and name != '__init__.py' and not name.startswith('.')
        ]
        plugins_files.sort()
        position = the_input.get_argument_position(quoted=False)
        return Completion(
            the_input.new_completion,
            plugins_files,
            position,
            '',
            quotify=False)

    def completion_unload(self, the_input):
        """
        completion function that completes the name of loaded plugins
        """
        position = the_input.get_argument_position(quoted=False)
        return Completion(
            the_input.new_completion,
            sorted(self.plugins.keys()),
            position,
            '',
            quotify=False)

    def on_plugins_dir_change(self, _, new_value):
        self.plugins_dir = Path(new_value).expanduser()
        self.check_create_plugins_dir()
        self.fill_load_path()

    def on_plugins_conf_dir_change(self, _, new_value):
        self.plugins_conf_dir = Path(new_value).expanduser()
        self.check_create_plugins_conf_dir()

    def initial_set_plugins_conf_dir(self):
        """
        Create the plugins_conf_dir
        """
        plugins_conf_dir = config.get('plugins_conf_dir')
        self.plugins_conf_dir = Path(plugins_conf_dir).expanduser(
        ) if plugins_conf_dir else xdg.CONFIG_HOME / 'plugins'
        self.check_create_plugins_conf_dir()

    def check_create_plugins_conf_dir(self):
        """
        Create the plugins config directory if it does not exist.
        Returns True on success, False on failure.
        """
        if not os.access(str(self.plugins_conf_dir), os.R_OK | os.X_OK):
            try:
                self.plugins_conf_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                log.error(
                    'Unable to create the plugin conf dir: %s',
                    self.plugins_conf_dir,
                    exc_info=True)
                return False
        return True

    def initial_set_plugins_dir(self):
        """
        Set the plugins_dir on start
        """
        plugins_dir = config.get('plugins_dir')
        self.plugins_dir = Path(plugins_dir).expanduser(
        ) if plugins_dir else xdg.DATA_HOME / 'plugins'
        self.check_create_plugins_dir()

    def check_create_plugins_dir(self):
        """
        Create the plugins directory if it does not exist.
        Returns True on success, False on failure.
        """
        if not os.access(str(self.plugins_dir), os.R_OK | os.X_OK):
            try:
                self.plugins_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                log.error(
                    'Unable to create the plugins dir: %s',
                    self.plugins_dir,
                    exc_info=True)
                return False
        return True

    def fill_load_path(self):
        """
        Append the global packages and the source directory if available
        """

        self.load_path = []

        default_plugin_path = path.join(
            path.dirname(path.dirname(__file__)), 'plugins')

        if os.access(default_plugin_path, os.R_OK | os.X_OK):
            self.load_path.insert(0, default_plugin_path)

        if os.access(str(self.plugins_dir), os.R_OK | os.X_OK):
            self.load_path.append(str(self.plugins_dir))

        try:
            import poezio_plugins
        except:
            pass
        else:
            if poezio_plugins.__path__:
                self.load_path.append(list(poezio_plugins.__path__)[0])
