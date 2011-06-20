# Copyright 2010-2011 Le Coz Florent <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

import logging
log = logging.getLogger(__name__)

import curses

import windows
import tabs

from sleekxmpp.xmlstream import ElementBase, ET

class PubsubNode(object):
    node_type = None            # unknown yet
    def __init__(self, name, parent=None):
        self.items = []
        self.name = name
        self.parent = parent


class LeafNode(PubsubNode):
    node_type = "leaf"
    def __init__(self, name, parent=None):
        PubsubNode.__init__(self, name, parent)


class CollectionNode(PubsubNode):
    node_type = "collection"
    def __init__(self, name, parent=None):
        PubsubNode.__init__(self, name, parent)
        self.subnodes = []


class PubsubItem(object):
    def __init__(self, idd, content):
        self.id = idd
        self.content = content

    def to_dict(self, columns):
        """
        returns a dict of the values listed in columns
        """
        ret = {}
        for col in columns:
            ret[col] = self.__dict__.get(col) or ''
        return ret

class PubsubBrowserTab(tabs.Tab):
    """
    A tab containing a pubsub browser letting the user
    list nodes and items, view, add and delete items, etc
    """
    def __init__(self, server):
        """
        Server is the name of the pubsub server, for example:
        pubsub.example.com
        All action done in this tab will be made on that server.
        """
        tabs.Tab.__init__(self)
        self.current_node = None # the subnode we are listing. None means the root
        self.server = server
        self.nodes = []         # the lower level of nodes

        self.tab_win = windows.GlobalInfoBar()
        self.upper_message = windows.Topic()
        self.upper_message.set_message('Pubsub server: %s/%s' % (self.server,self.current_node or ''))

        # Node List View
        node_columns = ('node', 'name',)
        self.node_list_header = windows.ColumnHeaderWin(node_columns)
        self.node_listview = windows.ListWin(node_columns)

        # Item List View
        item_columns = ('id',)
        self.item_list_header = windows.ColumnHeaderWin(item_columns)
        self.item_listview = windows.ListWin(item_columns)

        self.default_help_message = windows.HelpText("“c”: create a node.")
        self.input = self.default_help_message

        self.key_func['c'] = self.command_create_node
        self.key_func["M-KEY_DOWN"] = self.scroll_node_down
        self.key_func["M-KEY_UP"] = self.scroll_node_up
        self.key_func["KEY_DOWN"] = self.item_listview.move_cursor_down
        self.key_func["KEY_UP"] = self.item_listview.move_cursor_up
        self.resize()

        self.get_nodes()

    def resize(self):
        self.upper_message.resize(1, self.width, 0, 0)
        self.tab_win.resize(1, self.width, self.height-2, 0)

        column_size = {'node': self.width//4,
                       'name': self.width//4,}
        self.node_list_header.resize_columns(column_size)
        self.node_list_header.resize(1, self.width//2, 1, 0)
        self.node_listview.resize_columns(column_size)
        self.node_listview.resize(self.height//2-2, self.width//2, 2, 0)

        column_size = {'id': self.width//2,}
        self.item_list_header.resize_columns(column_size)
        self.item_list_header.resize(self.height//2+1, self.width//2, self.height//2, 0)
        self.item_listview.resize_columns(column_size)
        self.item_listview.resize(self.height//2-3, self.width//2, self.height//2+1, 0)

        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s'%self.__class__.__name__)
        self.upper_message.refresh()
        self.node_list_header.refresh()
        self.node_listview.refresh()
        self.item_list_header.refresh()
        self.item_listview.refresh()
        self.tab_win.refresh()
        self.input.refresh()

    def get_name(self):
        return '%s@@pubsubbrowser' % (self.server,)

    def on_input(self, key):
        res = self.input.do_command(key)
        if res:
            return True
        if key in self.key_func:
            return self.key_func[key]()

    def get_selected_node_name(self):
        """
        From the node_view_list, returns the node name of the selected
        one. None can be returned
        """
        line = self.node_listview.get_selected_row()
        if not line:
            return None
        return line['node']

    def get_node_by_name(self, name):
        """
        in the current browsed node (or on the root), return the node with that name
        """
        nodes = self.current_node and self.current_node.subnodes or self.nodes
        for node in nodes:
            if node.name == name:
                return node
        return None

    def get_items(self, node):
        """
        Get all items in the given node
        """
        items = self.core.xmpp.plugin['xep_0060'].get_items(self.server, node.name)
        item_list = []
        if items:
            for it in items:
                item_list.append(PubsubItem(it.attrib['id'], it))
            node.items = item_list
            log.debug('get_selected_node_name: %s' % self.get_selected_node_name())
            if self.get_selected_node_name() == node.name:
                self.display_items_from_node(node)
        log.debug('Item on node %s: %s' % (node.name, item_list))

    def display_items_from_node(self, node):
        """
        takes a node, and set fill the item_listview with that
        node’s items
        """
        columns = self.item_list_header.get_columns()
        self.item_listview.lines = []
        log.debug('display_items_from_node: %s' % node.items)
        for item in node.items:
            self.item_listview.lines.append(item.to_dict(columns))

    def add_nodes(self, node_list, parent=None):
        """
        Add Node objects to the list of the parent.
        If parent is None, they are added to the root list.
        If the current selected node is parent, we add
        them directly to the node_listview
        """
        log.debug('Adding nodes to %s: %s' % (node_list, parent,))
        if not parent:
            list_to_append = self.nodes
        else:
            list_to_append = parent.nodes
        self.node_listview.add_lines(node_list)
        for node in node_list:
            new_node = LeafNode(node['node'])
            list_to_append.append(new_node)
            self.get_items(new_node)

    def get_nodes(self, node=None):
        """
        Get all subnodes of the given node. If no node is given, get
        the root nodes
        """
        nodes = self.core.xmpp.plugin['xep_0060'].get_nodes(self.server)
        lines = [{'name': nodes[node] or '',
                  'node': node} for node in nodes.keys()]
        self.add_nodes(lines)

    def create_node(self, node_name):
        if node_name:
            res = self.core.xmpp.plugin['xep_0060'].create_node(self.server, node_name)
            if res:
                self.node_listview.add_lines([{'name': '', 'node': node_name}])
        self.reset_help_message()
        return True

    def reset_help_message(self, txt=None):
        """
        Just reset the help message when a command ends
        """
        curses.curs_set(0)
        self.input = self.default_help_message
        return True

    def command_create_node(self):
        """
        Prompt for a node name and create it on Enter key
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("[Create node]", self.reset_help_message, self.create_node, None)
        self.input.resize(1, self.width, self.height-1, 0)
        return True

    def scroll_node_up(self):
        """
        scroll the node up, and update the item list if needed
        """
        selected_node_before = self.get_selected_node_name()
        self.node_listview.move_cursor_up()
        selected_node_after = self.get_selected_node_name()
        if selected_node_after is not selected_node_before:
            self.display_items_from_node(self.get_node_by_name(selected_node_after))
            return True
        return False

    def scroll_node_down(self):
        """
        scroll the node down, and update the item list if needed
        """
        selected_node_before = self.get_selected_node_name()
        self.node_listview.move_cursor_down()
        selected_node_after = self.get_selected_node_name()
        if selected_node_after is not selected_node_before:
            self.display_items_from_node(self.get_node_by_name(selected_node_after))
            return True
        return False

