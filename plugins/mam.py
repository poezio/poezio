#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Madhur Garg

"""
    Query and control an archive of messages stored on a server using
    XEP-0313: Message Archive Management(MAM).
"""

import re
import slixmpp

from datetime import datetime
from datetime import timedelta
from poezio.config import config
from poezio.plugin import BasePlugin
from poezio.decorators import command_args_parser
from poezio import tabs
from poezio.mam import MAM
from poezio.text_buffer import Message, TextBuffer


class Plugin(BasePlugin):
    """MAM Plugin"""

    def init(self):
        for tab in tabs.ConversationTab, tabs.PrivateTab, tabs.MucTab:
            self.api.add_tab_command(
                tab,
                'mam',
                self.command_mam,
                usage='[start_timestamp] [end_timestamp]',
                help='Query and control an archive of messages using MAM')

    @command_args_parser.quoted(0, 2)
    def command_mam(self, args):
        """Define mam command"""

        tab = self.api.current_tab()
        jid = config.get('jid')
        password = config.get('password')
        eval_password = config.get('eval_password')
        if not password:
            password = eval_password
        remote_jid = tab.jid
        end = datetime.now()
        end = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')
        start = datetime.strptime(end, '%Y-%m-%dT%H:%M:%SZ')
        # Default start date is 10 days past the current day.
        start = start + timedelta(days=-10)
        start = datetime.strftime(start, '%Y-%m-%dT%H:%M:%SZ')
        # Format for start and end timestamp is [dd:mm:yyyy]
        if len(args) == 1:
            try:
                start = datetime.strptime(args[0], '%d:%m:%Y')
                start = datetime.strftime(start, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                pass
        elif len(args) == 2:
            try:
                start = datetime.strptime(args[0], '%d:%m:%Y')
                start = datetime.strftime(start, '%Y-%m-%dT%H:%M:%SZ')
                end = datetime.strptime(args[1], '%d:%m:%Y')
                end = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                pass

        MAM(jid, password, remote_jid, start, end, tab)
