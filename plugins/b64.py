#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Maxime “pep” Buquet <pep@bouah.net>
#
# Distributed under terms of the GPL-3.0+ license.

"""
Usage
-----

Base64 encryption plugin.

This plugin also respects security guidelines listed in XEP-0419.

.. glossary::
    /b64
        **Usage:** ``/b64``

        This command enables encryption of outgoing messages for the current
        tab.
"""

from base64 import b64decode, b64encode
from typing import List, Optional
from slixmpp import Message, JID

from poezio.plugin_e2ee import E2EEPlugin
from poezio.tabs import (
    ChatTab,
    MucTab,
    PrivateTab,
    DynamicConversationTab,
    StaticConversationTab,
)


class Plugin(E2EEPlugin):
    """Base64 Plugin"""

    encryption_name = 'base64'
    encryption_short_name = 'b64'
    eme_ns = 'urn:xmpps:base64:0'

    # This encryption mechanism is using <body/> as a container
    replace_body_with_eme = False

    # In what tab is it ok to use this plugin. Here we want all of them
    supported_tab_types = (
        MucTab,
        PrivateTab,
        DynamicConversationTab,
        StaticConversationTab,
    )

    async def decrypt(self, message: Message, jid: Optional[JID], _tab: Optional[ChatTab]) -> None:
        """
            Decrypt base64
        """
        body = message['body']
        message['body'] = b64decode(body.encode()).decode()

    async def encrypt(self, message: Message, _jid: Optional[List[JID]], _tab: ChatTab) -> None:
        """
            Encrypt to base64
        """
        # TODO: Stop using <body/> for this. Put the encoded payload in another element.
        body = message['body']
        message['body'] = b64encode(body.encode()).decode()
