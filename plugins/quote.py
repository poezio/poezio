"""
This plugin allows you to quote messages easily.

Usage
-----

.. glossary::

    /quote
        **Usage:** ``/quote <message>``

        The message must exist. You can use autocompletion to get the message
        you want to quote easily.

        Example:

        .. code-block:: none

            /quote "Pouet"

        If the message "Pouet" exists, it will be put in the input. If not you
        will get a warning.

Options
-------

.. glossary::
    :sorted:

    before_quote

        **Default value:** ``[empty]``

        Text to insert before the quote. ``%(nick)s`` and ``%(time)s`` can
        be used to insert the nick of the user who sent the message or the
        time of the message.

    after_quote

        **Default value:** ``[empty]``

        Text to insert after the quote. ``%(nick)s`` and ``%(time)s`` can
        be used to insert the nick of the user who sent the message or the
        time of the message.
"""

from poezio.core.structs import Completion
from poezio.plugin import BasePlugin
from poezio.xhtml import clean_text
from poezio import common
from poezio import tabs

import logging
log = logging.getLogger(__name__)

class Plugin(BasePlugin):
    def init(self):
        for _class in (tabs.MucTab, tabs.ConversationTab, tabs.PrivateTab):
            self.api.add_tab_command(_class, 'quote', self.command_quote,
                    usage='<message>',
                    help='Quote the message you typed if it exists.',
                    short='Quote a message.',
                    completion=self.completion_quote)

    def command_quote(self, args):
        args = common.shell_split(args)
        if len(args) == 1:
            message = args[-1]
        else:
            return self.api.run_command('/help quote')
        message = self.find_message(message)
        if message:
            before = self.config.get('before_quote', '') % {'nick': message.nickname or '',
                                                            'time': message.str_time}
            after = self.config.get('after_quote', '') % {'nick': message.nickname or '',
                                                           'time': message.str_time}
            self.core.insert_input_text('%(before)s%(quote)s%(after)s' % {'before': before.replace('\\n', '\n').replace('[SP]', ' '),
                                                                          'quote': clean_text(message.txt),
                                                                          'after': after.replace('\\n', '\n').replace('[SP]', ' ')})
        else:
            self.api.information('No message found', 'Warning')

    def find_message(self, txt):
        messages = self.api.get_conversation_messages()
        if not messages:
            return None
        for message in messages[::-1]:
            if clean_text(message.txt) == txt:
                return message
        return None

    def completion_quote(self, the_input):
        def message_match(msg):
            return input_message.lower() in clean_text(msg.txt).lower()
        messages = self.api.get_conversation_messages()
        if not messages:
            return
        text = the_input.get_text()
        args = common.shell_split(text)
        if not text.endswith(' '):
            input_message = args[-1]
            messages = list(filter(message_match, messages))
        elif len(args) > 1:
            return False
        return Completion(the_input.auto_completion, [clean_text(msg.txt) for msg in messages[::-1]], '')

