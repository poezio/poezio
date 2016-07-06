"""
This plugin lets you perform simple replacements on the last message.

Usage
-----

.. note:: the ``/``, ``#``, ``!``, ``:`` and ``;`` chars can be used as separators,
         even if the examples only use ``/``


Regex replacement
~~~~~~~~~~~~~~~~~

Once the plugin is loaded, any message matching the following regex::

    ^s/(.+?)/(.*?)(/|/g)?$

will be interpreted as a regex replacement, and the substitution will be
applied to the last sent message.

For example, if you sent the message::

    This tab lists all public rooms on a MUC service. It is currently very limited but will be improved in the future. There currently is no way to search a room.

And you now want to replace “MUC” with “multi-user chat”, you input::

    s/MUC/multi-user chat

And poezio will correct the message for you.


Raw string replacement
~~~~~~~~~~~~~~~~~~~~~~

Once the plugin is loaded, any message matching the following regex::

    ^r/(.+?)/(.*?)(/|/g)?$

will be interpreted as a replacement, and the substitution will be applied
to the last send message.

This variant is useful if you don’t want to care about regular expressions
(and you do not want to have to escape stuff like space or backslashes).


"""

from poezio.plugin import BasePlugin
import re

allowed_separators = '/#!:;'
sed_re = re.compile('^([sr])(?P<sep>[%s])(.+?)(?P=sep)(.*?)((?P=sep)|(?P=sep)g)?$' % allowed_separators)

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.sed_fix)
        self.api.add_event_handler('conversation_say', self.sed_fix)
        self.api.add_event_handler('private_say', self.sed_fix)

    def sed_fix(self, msg, tab):
        if not tab.last_sent_message:
            return
        if 'correct' not in tab.commands:
            return
        body = tab.last_sent_message['body']
        match = sed_re.match(msg['body'])
        if not match:
            return
        typ, sep, remove, put, matchall = match.groups()

        replace_all = False
        if matchall == sep + 'g':
            replace_all = True

        if typ == 's':
            try:
                if replace_all:
                    new_body = re.sub(remove, put, body)
                else:
                    new_body = re.sub(remove, put, body, count=1)
            except Exception as e:
                self.api.information('Invalid regex for the autocorrect '
                                     'plugin: %s' % e, 'Error')
                return
        elif typ == 'r':
            if replace_all:
                new_body = body.replace(remove, put)
            else:
                new_body = body.replace(remove, put, 1)

        if body != new_body:
            msg['body'] = new_body
            msg['replace']['id'] = tab.last_sent_message['id']
