class PluginManager(object):
    def __init__(self, core):
        self.core = core
        self.plugins = {}

    def load(self, name):
        if name in self.plugins:
            self.plugins[name].unload()

        try:
            code = compile(open(name).read(), name, 'exec')
            from plugin import BasePlugin
            globals = { 'BasePlugin' : BasePlugin }
            exec(code, globals)
            self.plugins[name] = globals['Plugin'](self.core)
        except Exception as e:
            self.core.information("Could not load plugin: %s" % (e,))

    def unload(self, name):
        if name in self.plugins:
            try:
                self.plugins[name].unload()
                del self.plugins[name]
            except Exception as e:
                self.core.information("Could not unload plugin (may not be safe to try again): %s" % (e,))
