from plugin import BasePlugin, PluginConfig
from xhtml import clean_text
import common

import re

timestamp_re = re.compile(r'^(\d\d\d\d-\d\d-\d\d )?\d\d:\d\d:\d\d$')

import logging
log = logging.getLogger(__name__)

class Plugin(BasePlugin):
    def init(self):
        self.add_command('quote', self.command_quote, "Usage: /quote <timestamp>\nQuote: takes the message received at <timestamp> and insert it in the input, to quote it.", self.completion_quote)

    def command_quote(self, args):
        args = common.shell_split(args)
        if len(args) in (1, 2):
            timestamp = args[-1]
        else:
            return self.core.command_help('quote')
        if re.match(timestamp_re, timestamp) is None:
            return self.core.information('Timestamp has a wrong format.', 'Warning')
        message = self.find_message_with_timestamp(timestamp)
        if message:
            before = self.config.get('before_quote', '') % {'nick': message.nickname or '',
                                                            'time': message.str_time}
            after = self.config.get('after_quote', '') % {'nick': message.nickname or '',
                                                           'time': message.str_time}
            self.core.insert_input_text('%(before)s%(quote)s%(after)s' % {'before': before.replace('\\n', '\n').replace('[SP]', ' '),
                                                                          'quote': clean_text(message.txt),
                                                                          'after': after.replace('\\n', '\n').replace('[SP]', ' ')})
        else:
            self.core.information('No message found for timestamp %s.' % timestamp, 'Warning')

    def find_message_with_timestamp(self, timestamp):
        # TODO: handle messages with the same
        # timestamp but not the same day
        # TODO: complete nicknames we are on the first argument and
        # it doesn’t start with a digit
        messages = self.core.get_conversation_messages()
        if not messages:
            return None
        for message in messages[::-1]:
            if message.str_time == timestamp:
                return message
        return None

    def completion_quote(self, the_input):
        def nick_match(msg):
            if not msg.nickname:
                return nick == ''
            return msg.nickname.lower().startswith(nick.lower())
        messages = self.core.get_conversation_messages()
        if not messages:
            return
        text = the_input.get_text()
        args = common.shell_split(text)
        n = len(args)
        if text.endswith(' '):
            n += 1
        if n == 2:
            try:
                if args[1][0] not in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '0'):
                    return False
            except:
                pass
        nick = ''
        if n == 3:
            nick = args[1]
        messages = list(filter(nick_match, messages))
        return the_input.auto_completion([msg.str_time for msg in messages[::-1]], '')
