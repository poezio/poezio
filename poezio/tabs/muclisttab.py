"""
A MucListTab is a tab listing the rooms on a conference server.

It has no functionality except scrolling the list, and allowing the
user to join the rooms.
"""
import logging
from typing import Dict, Callable

from poezio.tabs import ListTab
from poezio.core.structs import Command

from slixmpp.plugins.xep_0030.stanza.items import DiscoItem

log = logging.getLogger(__name__)


class MucListTab(ListTab):
    """
    A tab listing rooms from a specific server, displaying various information,
    scrollable, and letting the user join them, etc
    """
    plugin_commands = {}  # type: Dict[str, Command]
    plugin_keys = {}  # type: Dict[str, Callable]

    def __init__(self, core, server):
        ListTab.__init__(self, core, server.full, "“j”: join room.",
                         'Chatroom list on server %s (Loading)' % server,
                         (('node-part', 0), ('name', 2), ('users', 3)))
        self.key_func['j'] = self.join_selected
        self.key_func['J'] = self.join_selected_no_focus
        self.key_func['^M'] = self.join_selected

    def get_columns_sizes(self):
        return {
            'node-part': int(self.width * 2 / 8),
            'name': int(self.width * 5 / 8),
            'users':
            self.width - int(self.width * 2 / 8) - int(self.width * 5 / 8)
        }

    def join_selected_no_focus(self):
        return

    def on_muc_list_item_received(self, iq):
        """
        Callback called when a disco#items result is received
        Used with command_list
        """
        if iq['type'] == 'error':
            self.set_error(iq['error']['type'], iq['error']['code'],
                           iq['error']['text'])
            return

        def get_items():
            substanza = iq['disco_items']
            for item in substanza['substanzas']:
                if isinstance(item, DiscoItem):
                    yield (item['jid'], item['node'], item['name'])

        items = [(item[0].split('@')[0], item[0], item[2] or '', '')
                 for item in get_items()]
        items = sorted(items, key=lambda item: item[0])
        self.listview.set_lines(items)
        self.info_header.message = 'Chatroom list on server %s' % self.name
        if self.core.tabs.current_tab is self:
            self.refresh()
        else:
            self.state = 'highlight'
            self.refresh_tab_win()
        self.core.doupdate()

    def join_selected(self):
        row = self.listview.get_selected_row()
        if not row:
            return
        self.core.command.join(row[1])
