# poezio emoji_ascii plugin
#
# Will translate received Emoji to :emoji: for better display on text terminals,
# and outgoing :emoji: into Emoji on the wire.
#
# Requires emojis.json.gz (MIT licensed) from:
#
#     git clone https://github.com/vdurmont/emoji-java
#     gzip -9 < ./src/main/resources/emojis.json > poezio/plugins/emojis.json.gz

# TODOs:
# 1. it messes up your log files (doesn't log original message, logs mutilated :emoji: instead)
# 2. Doesn't work on outgoing direct messages
# 3. Doesn't detect pastes, corrupts jabber:x:foobar
# 4. no auto-completion of emoji aliases
# 5. coloring of converted Emojis to be able to differentiate them from incoming ASCII

import gzip
import json
import os
import re

from poezio.plugin import BasePlugin

class Plugin(BasePlugin):
    emoji_to_ascii = {}
    ascii_to_emoji = {}
    emoji_pattern = None
    alias_pattern = None

    def init(self):
        emoji_map_file_name = os.path.abspath(os.path.dirname(__file__) + '/emojis.json.gz')
        emoji_map_data = gzip.open(emoji_map_file_name, 'r').read().decode('utf-8')
        emoji_map = json.loads(emoji_map_data)
        for e in emoji_map:
            self.emoji_to_ascii[e['emoji']] = ':%s:' % e['aliases'][0]
            for alias in e['aliases']:
                # work around :iq: and similar country code misdetection
                flag = re.match('^[a-z][a-z]$', alias) and "flag" in e["tags"]
                if not flag:
                    self.ascii_to_emoji[':%s:' % alias] = e['emoji']
        self.emoji_pattern = re.compile('|'.join(self.emoji_to_ascii.keys()).replace('*', '\*'))
        self.alias_pattern = re.compile('|'.join(self.ascii_to_emoji.keys()).replace('+', '\+'))

        self.api.add_event_handler('muc_msg', self.emoji2alias)
        self.api.add_event_handler('conversation_msg', self.emoji2alias)
        self.api.add_event_handler('private_msg', self.emoji2alias)

        self.api.add_event_handler('muc_say', self.alias2emoji)
        self.api.add_event_handler('private_say', self.alias2emoji)
        self.api.add_event_handler('conversation_say', self.alias2emoji)


    def emoji2alias(self, msg, tab):
        msg['body'] = self.emoji_pattern.sub(lambda m: self.emoji_to_ascii[m.group()], msg['body'])

    def alias2emoji(self, msg, tab):
        msg['body'] = self.alias_pattern.sub(lambda m: self.ascii_to_emoji[m.group()], msg['body'])
