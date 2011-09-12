# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

import logging
log = logging.getLogger(__name__)

import os
import curses
import tempfile
import subprocess

import tabs
import windows
import atom_parser

from config import config

from datetime import datetime
from sleekxmpp.xmlstream import ElementBase, ET

ATOM_XMLNS = "http://www.w3.org/2005/Atom"

item_template = \
"""
-- About you
-- Your name
Author: %(author)s

-- Your jid (e.g. xmpp:romeo@example.com) or website’s url (http://example.com)
URI: xmpp:%(jid)s

-- Your email address (e.g. romeo@mail.com)
email: 
Title: 

-- Please use the form dd/mm/yyy hh:mm:ss, or leave empty
-- If you leave the date empty it will automatically be filled with the current time and date (recommended)
Date: 

--- body --- Until the end of file, this will be your item's body

"""

def parse_template(lines):
    """
    takes a template string (splitted by lines) and returns a dict with the correstponding values
    """
    lines = [line.lower() for line in lines]
    res = {}
    reading_body = False
    body = []
    for line in lines:
        if line.startswith('--- body ---'):
            reading_body = True
            continue
        if reading_body:
            body.append(line)
            continue
        if line.startswith('-- '):
            continue
        for value in ('author', 'uri', 'email', 'title', 'date'):
            if line.startswith('%s:' % (value,)):
                res[value] = line.split(':', 1)[1].strip()
    res['body'] = ''.join(body)
    return res

def create_entry_from_dict(dic):
    """
    Takes a dict with the correct values and returns an ET.Element
    representing an Atom entry
    """
    entry_elem = ET.Element('entry', xmlns=ATOM_XMLNS)

    author_elem = ET.Element('author', xmlns=ATOM_XMLNS)
    if dic.get('author'):
        name_elem = ET.Element('name', xmlns=ATOM_XMLNS)
        name_elem.text = dic.get('author')
        author_elem.append(name_elem)
    if dic.get('uri'):
        uri_elem = ET.Element('uri', xmlns=ATOM_XMLNS)
        uri_elem.text = dic.get('uri')
        author_elem.append(uri_elem)
    if dic.get('email'):
        email_elem = ET.Element('email', xmlns=ATOM_XMLNS)
        email_elem.text = dic.get('email')
        author_elem.append(email_elem)
    entry_elem.append(author_elem)
    if dic.get('title'):
        title_elem = ET.Element('title', xmlns=ATOM_XMLNS)
        title_elem.text = dic.get('title')
        entry_elem.append(title_elem)
    # TODO
    # if dic.get('date'):
    date_elem =  ET.Element('published', xmlns=ATOM_XMLNS)
    date_elem.text = '%s' % datetime.now()
    entry_elem.append(date_elem)
    summary_elem = ET.Element('summary', xmlns=ATOM_XMLNS)
    summary_elem.text = dic.get('body') or ''
    entry_elem.append(summary_elem)
    return entry_elem

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
        self.parsed_content = atom_parser.parse_atom_entry(content)

    def to_dict(self, columns):
        """
        returns a dict of the values listed in columns
        """
        ret = {}
        for col in columns:
            ret[col] = self.__dict__.get(col) or ''
        if self.parsed_content:
            ret['title'] = self.parsed_content.get('title')
            ret['author'] = self.parsed_content['author'].get('name')
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

        self.upper_message = windows.Topic()
        self.set_info_message('Loading')

        # Node List View
        node_columns = ('node', 'name',)
        self.node_list_header = windows.ColumnHeaderWin(node_columns)
        self.node_listview = windows.ListWin(node_columns)

        # Item List View
        item_columns = ('title', 'author', 'id')
        self.item_list_header = windows.ColumnHeaderWin(item_columns)
        self.item_listview = windows.ListWin(item_columns)

        # Vertical Separator
        self.vertical_separator = windows.VerticalSeparator()

        # Item viewer
        self.item_viewer = windows.SimpleTextWin('')
        self.default_help_message = windows.HelpText("“c”: create a node.")
        self.input = self.default_help_message

        self.key_func['c'] = self.command_create_node
        self.key_func['p'] = self.command_publish_item
        self.key_func["M-KEY_DOWN"] = self.scroll_node_down
        self.key_func["M-KEY_UP"] = self.scroll_node_up
        self.key_func["KEY_DOWN"] = self.item_listview.move_cursor_down
        self.key_func["KEY_UP"] = self.item_listview.move_cursor_up
        self.key_func["^M"] = self.open_selected_item
        self.resize()

        self.get_nodes()

    def command_publish_item(self):
        self.core.background = True
        editor = config.get('editor', '') or os.getenv('EDITOR') or 'vi'
        log.debug('Starting item edition with command %s' % editor)
        tmpfile = tempfile.NamedTemporaryFile(mode='r+')
        tmpfile.write(item_template % {'author': self.core.xmpp.boundjid.user, 'jid': self.core.xmpp.boundjid.bare})
        tmpfile.flush()
        process = subprocess.call(editor.split() + [tmpfile.name])
        tmpfile.flush()
        tmpfile.seek(0)
        item_dict = parse_template(tmpfile.readlines())
        tmpfile.close()
        log.debug('[%s]' % item_dict)

        self.core.background = False
        self.core.full_screen_redraw()
        entry = create_entry_from_dict(item_dict)
        self.publish_item(entry, self.get_selected_node_name())

    def publish_item(self, content, node_name):
        """
        publish the given item on the given node
        """
        def callback(res):
            if res:
                self.set_info_message('Item published')
            else:
                self.set_info_message('Item not published')
            self.force_refresh()

        self.core.xmpp.plugin['xep_0060'].setItem(self.server, node_name, content, callback=callback)

    def set_info_message(self, message):
        """
        Set an informative message in the upper line, near the server name
        """
        self.upper_message.set_message('Pubsub server: %s/%s [%s]' % (self.server, self.current_node or '', message))

    def resize(self):
        self.upper_message.resize(1, self.width, 0, 0)
        self.tab_win.resize(1, self.width, self.height-2, 0)

        column_size = {'node': self.width//4,
                       'name': self.width//4,}
        self.node_list_header.resize_columns(column_size)
        self.node_list_header.resize(1, self.width//2, 1, 0)
        self.node_listview.resize_columns(column_size)
        self.node_listview.resize(self.height//2-2, self.width//2, 2, 0)

        w = self.width//2
        column_size = {'id': w//8,
                       'title':w//8*5,
                       'author':w//8*2}
        self.item_list_header.resize_columns(column_size)
        self.item_list_header.resize(self.height//2+1, self.width//2, self.height//2, 0)
        self.item_listview.resize_columns(column_size)
        self.item_listview.resize(self.height//2-3, self.width//2, self.height//2+1, 0)

        self.vertical_separator.resize(self.height-3, 1, 1, self.width//2)

        self.item_viewer.resize(self.height-3, self.width//2+1, 1, self.width//2+1)
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
        self.item_viewer.refresh()
        self.tab_win.refresh()
        self.vertical_separator.refresh()
        self.input.refresh()

    def force_refresh(self):
        if self.core.current_tab() is self:
            self.core.refresh_window()

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
        in the currently browsed node (or on the root), return the node with that name
        """
        nodes = self.current_node and self.current_node.subnodes or self.nodes
        for node in nodes:
            if node.name == name:
                return node
        return None

    def get_item_by_id(self, idd):
        """
        in the currently selected node, return the item with that id
        """
        selected_node_name = self.get_selected_node_name()
        if not selected_node_name:
            return None
        selected_node = self.get_node_by_name(selected_node_name)
        if not selected_node:
            return None
        for item in selected_node.items:
            if item.id == idd:
                return item
        return None

    def get_selected_item_id(self):
        """
        returns the id of the currently selected item
        """
        line = self.item_listview.get_selected_row()
        if not line:
            return None
        return line['id']

    def get_items(self, node):
        """
        Get all items in the given node
        """
        def callback(items):
            item_list = []
            if items:
                for it in items:
                    item_list.append(PubsubItem(it.attrib['id'], it))
                node.items = item_list
                log.debug('get_selected_node_name: %s' % self.get_selected_node_name())
                if self.get_selected_node_name() == node.name:
                    self.display_items_from_node(node)
            log.debug('Item on node %s: %s' % (node.name, item_list))
            self.set_info_message('Items received')
            self.force_refresh()

        self.core.xmpp.plugin['xep_0060'].get_items(self.server, node.name, callback=callback)

    def display_items_from_node(self, node):
        """
        takes a node, and set fill the item_listview with that
        node’s items
        """
        columns = self.item_list_header.get_columns()
        self.item_listview.empty()
        log.debug('display_items_from_node: %s' % node.items)
        for item in node.items:
            line = item.to_dict(columns)
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
        def callback(nodes):
            lines = [{'name': nodes[node] or '',
                  'node': node} for node in nodes.keys()]
            self.add_nodes(lines)
            self.set_info_message('Nodes received')
            self.force_refresh()
        self.core.xmpp.plugin['xep_0060'].get_nodes(self.server, callback=callback)

    def create_node(self, node_name):
        def callback(res):
            if res:
                self.node_listview.add_lines([{'name': '', 'node': node_name}])
                self.set_info_message('Node created')
            else:
                self.set_info_message('Node not created')
            self.reset_help_message()
            self.force_refresh()
        if node_name:
            self.core.xmpp.plugin['xep_0060'].create_node(self.server, node_name, callback=callback)
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

    def open_selected_item(self):
        """
        displays the currently selected item in the item view window
        """
        selected_item = self.get_item_by_id(self.get_selected_item_id())
        if not selected_item:
            return
        log.debug('Content: %s'%ET.tostring(selected_item.content))
        entry = atom_parser.parse_atom_entry(selected_item.content)
        if not entry:
            self.item_viewer._text = str(ET.tostring(selected_item.content))
        else:
            self.item_viewer._text = \
"""\x193Title:\x19o %(title)s
\x193Author:\x19o %(author_name)s (%(author_uri)s)
%(dates)s\x193Link:\x19o %(link)s

\x193Summary:\x19o
%(summary)s
""" % {'title': entry.get('title') or '',
       'author_name': entry['author'].get('name') or '',
       'author_uri': entry['author'].get('uri') or '',
       'link': entry.get('link_href') or '',
       'summary': entry.get('summary') or '',
       'dates': '\x193Published:\x19o %(published)s\n%(updated)s' % {'published':entry.get('published') or '',
                                                                'updated': '' if (entry.get('updated') is None) or (entry.get('published') == entry.get('updated')) else '\x193Published:\x19o %s\n' % entry.get('updated')}
       }
        self.item_viewer.rebuild_text()
        return True
