"""
This plugin adds a ``/server_part`` command to leave all rooms
on a server.

Command
-------

.. glossary::

    /server_part
        **Usage:** ``/server_part [<server> [message]]``

        Leave all rooms on ``<server>``, if not provided and the current
        tab is a chatroom tab, it will leave all rooms on the current server.
        ``[message]`` can indicate a quit message.


"""
from poezio.plugin import BasePlugin
from poezio.tabs import MucTab
from poezio.decorators import command_args_parser
from poezio.common import safeJID
from poezio.core.structs import Completion

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('server_part', self.command_server_part,
                usage='[<server> [message]]',
                short='Leave all the rooms on a server',
                help='Leave all the rooms on a sever.',
                completion=self.completion_server_part)

    @command_args_parser.quoted(0, 2, defaults=[])
    def command_server_part(self, args):
        current_tab = self.api.current_tab()
        if not args and not isinstance(current_tab, MucTab):
            return self.core.command_help('server_part')
        elif not args:
            jid = safeJID(current_tab.name).bare
            message = None
        elif len(args) == 1:
            jid = safeJID(args[0]).domain
            if not jid:
                return self.core.command_help('server_part')
            message = None
        else:
            jid = safeJID(args[0]).domain
            if not jid:
                return self.core.command_help('server_part')
            message = args[1]

        for tab in self.core.get_tabs(MucTab):
            if tab.name.endswith(jid):
                tab.command_part(message)

    def completion_server_part(self, the_input):
        serv_list = set()
        for tab in self.core.get_tabs(MucTab):
            if tab.joined:
                serv = safeJID(tab.name).server
                serv_list.add(serv)
        return Completion(the_input.new_completion, sorted(serv_list), 1, ' ')
