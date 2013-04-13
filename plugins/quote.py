"""
This plugin allows you to quote messages easily.

Installation
------------
You only have to load the plugin.

.. code-block:: none

    /load quote

Usage
-------

.. glossary::

    /quote
        **Usage:** ``/quote <timestamp>``

        Timestamp is in ``HH:MM:SS`` format, and can be completed with [tab].

        Example:

        .. code-block:: none

            /quote 21:12:23

        If there is a message at 21:12:23, it will be put in the input. If there
        isn’t, you will get a warning.
"""
from plugin import BasePlugin
from xhtml import clean_text
import common
import tabs
import re

timestamp_re = re.compile(r'^(\d\d\d\d-\d\d-\d\d )?\d\d:\d\d:\d\d$')
seconds_re = re.compile(r'^:\d\d$')

import logging
log = logging.getLogger(__name__)

class Plugin(BasePlugin):
    def init(self):
        for _class in (tabs.MucTab, tabs.ConversationTab, tabs.PrivateTab):
            self.api.add_tab_command(_class, 'quote', self.command_quote,
                    usage='<timestamp>',
                    help='Takes the message received at <timestamp> and insert it in the input, to quote it.',
                    short='Quote a message from a timestamp',
                    completion=self.completion_quote)

    def command_quote(self, args):
        args = common.shell_split(args)
        if len(args) in (1, 2):
            timestamp = args[-1]
        else:
            return self.api.run_command('/help quote')
        if re.match(timestamp_re, timestamp) is None:
            return self.api.information('Timestamp has a wrong format.', 'Warning')
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
            self.api.information('No message found for timestamp %s.' % timestamp, 'Warning')

    def find_message_with_timestamp(self, timestamp):
        # TODO: handle messages with the same
        # timestamp but not the same day
        messages = self.api.get_conversation_messages()
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
        def time_match(msg):
            return msg.str_time.endswith(time)
        messages = self.api.get_conversation_messages()
        if not messages:
            return
        text = the_input.get_text()
        args = common.shell_split(text)
        n = len(args)
        if text.endswith(' '):
            n += 1
        time = args[-1]
        if re.match(seconds_re, time) is not None:
            messages = list(filter(time_match, messages))
            for i in range(3):
                the_input.key_backspace(False)
        elif n == 2:
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
