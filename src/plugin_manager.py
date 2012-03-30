import imp
import os
import sys
import tabs
import logging
from config import config
from gettext import gettext as _

log = logging.getLogger(__name__)

plugins_dir = config.get('plugins_dir', '')
plugins_dir = plugins_dir or\
    os.path.join(os.environ.get('XDG_DATA_HOME') or\
                     os.path.join(os.environ.get('HOME'), '.local', 'share'),
                 'poezio', 'plugins')
plugins_dir = os.path.expanduser(plugins_dir)

config_home = os.environ.get("XDG_CONFIG_HOME")
if not config_home:
    config_home = os.path.join(os.environ.get('HOME'), '.config')
plugins_conf_dir = os.path.join(config_home, 'poezio', 'plugins')

try:
    os.makedirs(plugins_dir)
except OSError:
    pass

try:
    os.makedirs(plugins_conf_dir)
except OSError:
    pass

sys.path.append(plugins_dir)

class PluginManager(object):
    def __init__(self, core):
        self.core = core
        self.modules = {} # module name -> module object
        self.plugins = {} # module name -> plugin object
        self.commands = {} # module name -> dict of commands loaded for the module
        self.event_handlers = {} # module name -> list of event_name/handler pairs loaded for the module
        self.tab_commands = {} #module name -> dict of tab types; tab type -> commands loaded by the module
        self.keys = {} # module name → dict of keys/handlers loaded for the module
        self.tab_keys = {} #module name → dict of tab types; tab type → list of keybinds (tuples)

    def load(self, name, notify=True):
        if name in self.plugins:
            self.unload(name)

        try:
            if name in self.modules:
                imp.acquire_lock()
                module = imp.reload(self.modules[name])
                imp.release_lock()
            else:
                file, filename, info = imp.find_module(name, [plugins_dir])
                imp.acquire_lock()
                module = imp.load_module(name, file, filename, info)
                imp.release_lock()
        except Exception as e:
            import traceback
            log.debug("Could not load plugin: \n%s", traceback.format_exc())
            self.core.information("Could not load plugin: %s" % e, 'Error')
            return
        finally:
            if imp.lock_held():
                imp.release_lock()

        self.modules[name] = module
        self.commands[name] = {}
        self.keys[name] = {}
        self.tab_keys[name] = {}
        self.tab_commands[name] = {}
        self.event_handlers[name] = []
        self.plugins[name] = module.Plugin(self, self.core, plugins_conf_dir)
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

    def del_command(self, module_name, name):
        if name in self.commands[module_name]:
            del self.commands[module_name][name]
            if name in self.core.commands:
                del self.core.commands[name]

    def add_tab_command(self, module_name, tab_type, name, handler, help, completion=None):
        commands = self.tab_commands[module_name]
        t = tab_type.__name__
        if name in tab_type.plugin_commands:
            return
        if not t in commands:
            commands[t] = []
        commands[t].append((name, handler, help, completion))
        tab_type.plugin_commands[name] = (handler, help, completion)
        for tab in self.core.tabs:
            if isinstance(tab, tab_type):
                tab.update_commands()

    def del_tab_command(self, module_name, tab_type, name):
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
        if key in self.core.key_func:
            raise Exception(_("Key '%s' already exists") % (key,))
        keys = self.keys[module_name]
        keys[key] = handler
        self.core.key_func[key] = handler

    def del_key(self, module_name, key):
        if key in self.keys[module_name]:
            del self.keys[module_name][key]
            if key in self.core.key_func:
                del self.core.commands[key]

    def add_command(self, module_name, name, handler, help, completion=None):
        if name in self.core.commands:
            raise Exception(_("Command '%s' already exists") % (name,))

        commands = self.commands[module_name]
        commands[name] = (handler, help, completion)
        self.core.commands[name] = (handler, help, completion)

    def add_event_handler(self, module_name, event_name, handler, position=0):
        eh = self.event_handlers[module_name]
        eh.append((event_name, handler))
        if event_name in self.core.events.events:
            self.core.events.add_event_handler(event_name, handler, position)
        else:
            self.core.xmpp.add_event_handler(event_name, handler)

    def del_event_handler(self, module_name, event_name, handler):
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
            names = os.listdir(plugins_dir)
        except OSError as e:
            self.core.information(_('Completion failed: %s' % e), 'Error')
            return
        plugins_files = [name[:-3] for name in names if name.endswith('.py')]
        return the_input.auto_completion(plugins_files, '')

    def completion_unload(self, the_input):
        """
        completion function that completes the name of the plugins that are loaded
        """
        return the_input.auto_completion(list(self.plugins.keys()), '')
