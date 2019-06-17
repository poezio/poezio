#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2018 Maxime “pep” Buquet
# Copyright © 2019 Madhur Garg
#
# Distributed under terms of the zlib license. See the COPYING file.

"""
    Search provided string in the buffer and return all results on the screen
"""

import re
from poezio.plugin import BasePlugin
from poezio import tabs
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


class Plugin(BasePlugin):
    """Lastlog Plugin"""

    def init(self):
        for tab in tabs.ConversationTab, tabs.PrivateTab, tabs.MucTab:
            self.api.add_tab_command(
                tab,
                'lastlog',
                self.command_lastlog,
                usage='<keyword>',
                help='Search <keyword> in the buffer and returns results'
                  'on the screen')

    def command_lastlog(self, input_):
        """Define lastlog command"""

        text_buffer = self.api.current_tab()._text_buffer
        search_re = re.compile(input_, re.I)

        res = []
        add_line(text_buffer, "Lastlog:")
        for message in text_buffer.messages:
            if message.nickname is not None and \
               search_re.search(message.txt) is not None:
                res.append(message)
                add_line(text_buffer, "%s" % (message.txt))
        add_line(text_buffer, "End of Lastlog")
        self.api.current_tab().text_win.pos = 0
        self.api.current_tab().core.refresh_window()
