#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2018 Maxime “pep” Buquet <pep@bouah.net>
#
# Distributed under terms of the zlib license. See the COPYING file.

"""
    Search provided string in the buffer and return all results on the screen
"""

import re
from poezio.plugin import BasePlugin
from poezio.tabs import ConversationTab, PrivateTab, MucTab
from poezio.text_buffer import Message, TextBuffer


def add_line(text_buffer: TextBuffer, text: str) -> None:
    """Adds a textual entry in the TextBuffer"""
    text_buffer.add_message(
        text,
        None,  # Time
        None,  # Nickname
        None,  # Nick Color
        False,  # History
        None,  # User
        False,  # Highlight
        None,  # Identifier
        None,  # str_time
        None,  # Jid
    )


def add_message(text_buffer: TextBuffer, msg: Message) -> None:
    """Adds a message to the TextBuffer"""
    text_buffer.add_message(
        msg.txt,
        msg.time,
        None,  # Nickname
        None,  # Nick Color
        False,  # History
        None,  # User
        msg.highlight,
        msg.identifier,
        msg.str_time,
        None,  # Jid
    )


class Plugin(BasePlugin):
    """Lastlog Plugin"""

    def init(self):
        self.api.add_tab_command(
            ConversationTab, 'lastlog', self.command_lastlog,
            usage='<keyword>', help=(
                'Search <keyword> in the buffer and returns results'
                'on the screen'
            ),
        )
        self.api.add_tab_command(
            MucTab, 'lastlog', self.command_lastlog, usage='<keyword>',
            help=('Search <keyword> in the buffer and returns results'
                  'on the screen'),
        )
        self.api.add_tab_command(
            PrivateTab, 'lastlog', self.command_lastlog, usage='<keyword>',
            help=('Search <keyword> in the buffer and returns results'
                  'on the screen'),
        )

    def command_lastlog(self, input_):
        """Define lastlog command"""

        text_buffer = self.api.current_tab()._text_buffer
        search_re = re.compile(input_)

        res = []
        for message in text_buffer.messages:
            if message.nickname is not None:
                self.core.information('Foo: %s> %s' % (message.nickname, message.txt), 'Info')
            if message.nickname is not None and \
               search_re.search(message.txt) is not None:
                res.append(message)

        add_line(text_buffer, "Lastlog for '%s', %d match(es)" % (input_, len(res)))

        for message in res:
            message.nickname = None
            add_message(text_buffer, message)
