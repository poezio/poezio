"""
This plugin adds several aliases, to shorten status changes.

Aliases
-------

.. glossary::
    :sorted:

    /afk
    /away
        Set your status to ``away``

    /dnd
    /busy
        Set your status to ``dnd``

    /available
        Set your status to ``available``

    /chat
        Set your status to ``chat``

    /xa
        Set your status to ``xa``

"""
from poezio.plugin import BasePlugin

class Plugin(BasePlugin):
    """
    Adds several convenient aliases to /status command
    """
    def init(self):
        for st in ('dnd', 'busy', 'afk', 'chat', 'xa', 'away', 'available'):
            self.api.add_command(st,
                    lambda line,st=st: self.api.run_command('/status ' + st + ' "'+line+'"'),
                    usage='[status message]',
                    short='Set your status as %s' % st,
                    help='Set your status as %s' % st)
