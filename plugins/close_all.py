"""
``close_all`` plugin: close all tabs except MUCs and the roster.

Commands
--------

.. glossary::

    /closeall
        **Usage:** ``/closeall``

        Close all tabs except the roster and MUC tabs.
"""
from plugin import BasePlugin
import tabs
from decorators import command_args_parser


class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('closeall', self.command_closeall,
                             help='Close all non-muc tabs.')

    @command_args_parser.ignored
    def command_closeall(self):
        """
        /closeall
        """
        current = self.core.current_tab()
        if not isinstance(current, (tabs.RosterInfoTab, tabs.MucTab)):
            self.core.go_to_roster()
            current = self.core.current_tab()

        def filter_func(x):
            return not isinstance(x, (tabs.RosterInfoTab, tabs.MucTab))

        matching_tabs = list(filter(filter_func, self.core.tabs))
        length = len(matching_tabs)
        for tab in matching_tabs:
            self.core.close_tab(tab)
        self.core.current_tab_nb = current.nb
        self.api.information('%s tabs closed.' % length, 'Info')
        self.core.refresh_window()


