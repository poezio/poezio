"""
Display an image URL as an embedded image in some clients like Conversations.
Uses: https://xmpp.org/extensions/xep-0066.html#x-oob

Usage
-----

.. glossary::

    /embed <image_url>

        Run this command to send the <image_url> as an
        embedded image in your contact's client.
"""

from poezio import tabs
from poezio.plugin import BasePlugin
from poezio.theming import get_theme

class Plugin(BasePlugin):

    def init(self):
        for tab_t in [tabs.MucTab, tabs.ConversationTab, tabs.PrivateTab]:
            self.api.add_tab_command(tab_t, 'embed', self.embed_image_url,
                                     help='Embed an image url into the contact\'s client',
                                     usage='<image_url>')

    def embed_image_url(self, args):
        tab = self.api.current_tab()
        message = self.core.xmpp.make_message(tab.name)
        message['body'] = args
        message['oob']['url'] = args
        if isinstance(tab, tabs.MucTab):
            message['type'] = 'groupchat'
        else:
            message['type'] = 'chat'
            tab.add_message(
                message['body'],
                nickname=tab.core.own_nick,
                nick_color=get_theme().COLOR_OWN_NICK,
                identifier=message['id'],
                jid=tab.core.xmpp.boundjid,
                typ=1,
            )
        message.send()
