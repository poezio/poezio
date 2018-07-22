"""
``close_all`` plugin: close all tabs except chatrooms and the contact list.

Commands
--------

.. glossary::

    /closeall
        **Usage:** ``/closeall``

        Close all tabs except the roster and chatroom tabs.
"""
from poezio.plugin import BasePlugin
from poezio import tabs
from poezio.decorators import command_args_parser


class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('closeall', self.command_closeall,
                             help='Close all non-chatroom tabs.')

    @command_args_parser.ignored
    def command_closeall(self):
        """
        /closeall
        """
        current = self.api.current_tab()
        if not isinstance(current, (tabs.RosterInfoTab, tabs.MucTab)):
            self.core.go_to_roster()
            current = self.api.current_tab()

        def filter_func(x):
            return not isinstance(x, (tabs.RosterInfoTab, tabs.MucTab))

        matching_tabs = list(filter(filter_func, self.core.tabs.get_tabs()))
        length = len(matching_tabs)
        for tab in matching_tabs:
            self.core.close_tab(tab)
        self.api.information('%s tabs closed.' % length, 'Info')
        self.core.refresh_window()


