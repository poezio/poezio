"""
This plugin lets you perform simple replacements on the last message.

Installation
------------

Load the plugin::

    /load autocorrect

Usage
-----

.. note:: This plugin only performs *simple* replacements, not with
    regular expressions, despite the syntax. Although it would be
    possible, that would be even less useful.

Once the plugin is loaded, any message matching the following regex::

    ^s/(.+?)/(.*?)(/|/g)?$

will be interpreted as a replacement, and the substitution will be
applied to the last sent message.

For example, if you sent the message::

    This tab lists all public rooms on a MUC service. It is currently very limited but will be improved in the future. There currently is no way to search a room.

And you now want to replace “MUC” with “multi-user chat”, you input::

    s/MUC/multi-user chat

And poezio will correct the message for you.
"""

from plugin import BasePlugin
import re

sed_re = re.compile('^s/(.+?)/(.*?)(/|/g)?$')

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.sed_fix)
        self.api.add_event_handler('conversation_say', self.sed_fix)
        self.api.add_event_handler('private_say', self.sed_fix)

    def sed_fix(self, msg, tab):
        if not tab.last_sent_message:
            return
        body = tab.last_sent_message['body']
        match = sed_re.match(msg['body'])
        if not match:
            return
        remove, put, matchall = match.groups()

        replace_all = False
        if matchall == '/g':
            replace_all = True

        if replace_all:
            new_body = body.replace(remove, put)
        else:
            new_body = body.replace(remove, put, 1)

        if body != new_body:
            msg['body'] = new_body
            msg['replace']['id'] = tab.last_sent_message['id']
