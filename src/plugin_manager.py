"""
Plugin manager module.
Define the PluginManager class, the one that glues all the plugins and
the API together. Defines also a bunch of variables related to the
plugin env.
"""

import imp
import os
from os import path
import sys
import logging
from gettext import gettext as _
from sys import version_info

import core
import tabs
from plugin import PluginAPI
from config import config

log = logging.getLogger(__name__)

load_path = []

plugins_dir = config.get('plugins_dir', '')
plugins_dir = plugins_dir or\
    os.path.join(os.environ.get('XDG_DATA_HOME') or\
                     os.path.join(os.environ.get('HOME'), '.local', 'share'),
                 'poezio', 'plugins')
plugins_dir = os.path.expanduser(plugins_dir)

plugins_conf_dir = config.get('plugins_conf_dir', '')
if not plugins_conf_dir:
    config_home = os.environ.get('XDG_CONFIG_HOME')
    if not config_home:
        config_home = os.path.join(os.environ.get('HOME'), '.config')
    plugins_conf_dir = os.path.join(config_home, 'poezio', 'plugins')
plugins_conf_dir = os.path.expanduser(plugins_conf_dir)

try:
    os.makedirs(plugins_dir)
except OSError:
    pass
else:
    load_path.append(plugins_dir)

try:
    os.makedirs(plugins_conf_dir)
except OSError:
    pass

default_plugin_path = path.join(path.dirname(path.dirname(__file__)), 'plugins')

if os.path.exists(default_plugin_path):
    load_path.append(default_plugin_path)

try:
    import poezio_plugins
except:
    pass
else:
    if poezio_plugins.__path__:
        load_path.append(list(poezio_plugins.__path__)[0])

if version_info[1] >= 3: # 3.3 & >
    from importlib import machinery
    finder = machinery.PathFinder()

class PluginManager(object):
    """
    Plugin Manager
    Contains all the references to the plugins
    And keeps track of everything the plugin has done through the API.
    """
    def __init__(self, core):
        self.core = core
        self.modules = {} # module name -> module object
        self.plugins = {} # module name -> plugin object
        self.commands = {} # module name -> dict of commands loaded for the module
        self.event_handlers = {} # module name -> list of event_name/handler pairs loaded for the module
        self.tab_commands = {} #module name -> dict of tab types; tab type -> commands loaded by the module
        self.keys = {} # module name → dict of keys/handlers loaded for the module
        self.tab_keys = {} #module name → dict of tab types; tab type → list of keybinds (tuples)
        self.roster_elements = {}
        self.plugin_api = PluginAPI(core, self)

    def disable_plugins(self):
        for plugin in set(self.plugins.keys()):
            try:
                self.unload(plugin)
            except:
                pass

    def load(self, name, notify=True):
        """
        Load a plugin.
        """
        if name in self.plugins:
            self.unload(name)

        try:
            module = None
            if version_info[1] < 3: # < 3.3
                if name in self.modules:
                    imp.acquire_lock()
                    module = imp.reload(self.modules[name])
                else:
                    file, filename, info = imp.find_module(name, load_path)
                    imp.acquire_lock()
                    module = imp.load_module(name, file, filename, info)
            else: # 3.3 & >
                loader = finder.find_module(name, load_path)
                if not loader:
                    self.core.information('Could not find plugin')
                    return
                module = loader.load_module()

        except Exception as e:
            import traceback
            log.debug("Could not load plugin %s: \n%s", name, traceback.format_exc())
            self.core.information("Could not load plugin %s: %s" % (name, e), 'Error')
        finally:
            if version_info[1] < 3 and imp.lock_held():
                imp.release_lock()
            if not module:
                return

        self.modules[name] = module
        self.commands[name] = {}
        self.keys[name] = {}
        self.tab_keys[name] = {}
        self.tab_commands[name] = {}
        self.event_handlers[name] = []
        self.plugins[name] = module.Plugin(self.plugin_api, self.core, plugins_conf_dir)
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
                        self.del_tab_command(name, getattr(tabs, tab), command[0])
                    del self.tab_commands[name][tab]
                for tab in list(self.tab_keys[name].keys()):
                    for key in self.tab_keys[name][tab][:]:
                        self.del_tab_key(name, getattr(tabs, tab), key[0])
                    del self.tab_keys[name][tab]
                for event_name, handler in self.event_handlers[name][:]:
                    self.del_event_handler(name, event_name, handler)

                self.plugins[name].unload()
                del self.plugins[name]
                del self.commands[name]
                del self.keys[name]
                del self.tab_commands[name]
                del self.event_handlers[name]
                if notify:
                    self.core.information('Plugin %s unloaded' % name, 'Info')
            except Exception as e:
                import traceback
                log.debug("Could not unload plugin: \n%s", traceback.format_exc())
                self.core.information("Could not unload plugin: %s" % e, 'Error')

    def add_command(self, module_name, name, handler, help, completion=None, short='', usage=''):
        """
        Add a global command.
        """
        if name in self.core.commands:
            raise Exception(_("Command '%s' already exists") % (name,))

        commands = self.commands[module_name]
        commands[name] = core.Command(handler, help, completion, short, usage)
        self.core.commands[name] = commands[name]

    def del_command(self, module_name, name):
        """
        Remove a global command added through add_command.
        """
        if name in self.commands[module_name]:
            del self.commands[module_name][name]
            if name in self.core.commands:
                del self.core.commands[name]

    def add_tab_command(self, module_name, tab_type, name, handler, help, completion=None, short='', usage=''):
        """
        Add a command only for a type of Tab.
        """
        commands = self.tab_commands[module_name]
        t = tab_type.__name__
        if name in tab_type.plugin_commands:
            return
        if not t in commands:
            commands[t] = []
        commands[t].append((name, handler, help, completion))
        tab_type.plugin_commands[name] = core.Command(handler, help, completion, short, usage)
        for tab in self.core.tabs:
            if isinstance(tab, tab_type):
                tab.update_commands()

    def del_tab_command(self, module_name, tab_type, name):
        """
        Remove a command added through add_tab_command.
        """
        commands = self.tab_commands[module_name]
        t = tab_type.__name__
        if not t in commands:
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
        if not t in keys:
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
        if not t in keys:
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
            raise Exception(_("Key '%s' already exists") % (key,))
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
        it is a sleekxmpp event.
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
        eh = list(filter(lambda e : e != (event_name, handler), eh))

    def completion_load(self, the_input):
        """
        completion function that completes the name of the plugins, from
        all .py files in plugins_dir
        """
        try:
            names = set()
            for path in load_path:
                try:
                    add = set(os.listdir(path))
                    names |= add
                except:
                    pass
        except OSError as e:
            self.core.information(_('Completion failed: %s' % e), 'Error')
            return
        plugins_files = [name[:-3] for name in names if name.endswith('.py')
                and name != '__init__.py' and not name.startswith('.')]
        plugins_files.sort()
        return the_input.new_completion(plugins_files, 1, '', quotify=False)

    def completion_unload(self, the_input):
        """
        completion function that completes the name of the plugins that are loaded
        """
        return the_input.new_completion(sorted(self.plugins.keys()), 1, '', quotify=False)

    def on_plugins_dir_change(self, new_value):
        global plugins_dir
        if plugins_dir in load_path:
            load_path.remove(plugins_dir)
        load_path.insert(0, new_value)
        plugins_dir = new_value

    def on_plugins_conf_dir_change(self, new_value):
        global plugins_conf_dir
        plugins_conf_dir = new_value
