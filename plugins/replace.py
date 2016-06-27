"""
Replace some patterns in a message before sending it.

Usage
-----
Insert a pattern in the form

.. code-block:: none

    %pattern%

in your message, and it will be replaced by the corresponding text.

The list of provided patterns is:

- **time**: Insert the current time
- **date**: Insert the current date
- **datetime**: Insert the current date and time
- **random_nick**: Insert a random nick from the current MUC
- **dice**: Insert a random number between 1 and 6

Add your own pattern
--------------------

You can easily edit this plugin to add your own patterns. For example if
don’t want to search for an insult everytime you’re angry, you can create a
curse pattern this way:

- In the init(self) method of the Plugin class, add something like

.. code-block:: python

        self.patterns['curse'] = replace_curse

- then define a function (not a method of the Plugin class) at the bottom
  of the file. For example:


.. code-block:: python

    def replace_curse(message, tab):
        return random.choice(['dumb shit', 'idiot', 'moron'])

and you can now use something like

.. code-block:: none

    Shut up, %curse%!

in your everyday-conversations.

For more convenience, you can read your nice words from a file, do whatever
you want in that function, as long as it returns a string.
"""

from poezio.plugin import BasePlugin
from poezio import tabs
import datetime
import random
import re
from slixmpp.xmlstream.stanzabase import JID

class Plugin(BasePlugin):
    def init(self):
        self.patterns = {}
        self.api.add_event_handler('conversation_say', self.replace_pattern)
        self.api.add_event_handler('muc_say', self.replace_pattern)
        self.api.add_event_handler('private_say', self.replace_pattern)
        self.patterns['time'] = replace_time
        self.patterns['date'] = replace_date
        self.patterns['datetime'] = replace_datetime
        self.patterns['random_nick'] = replace_random_user
        self.patterns['dice'] = replace_dice

    def replace_pattern(self, message, tab):
        """
        Look for a %*% pattern in the message and replace it by the result
        of the corresponding function.
        """
        body = message['body']
        for pattern in self.patterns:
            new = body
            body = re.sub('%%%s%%' % pattern,
                    lambda x: self.patterns[pattern](message, tab),
                    body)
        message['body'] = body


def replace_time(message, tab):
    return datetime.datetime.now().strftime("%X")

def replace_date(message, tab):
    return datetime.datetime.now().strftime("%x")

def replace_datetime(message, tab):
    return datetime.datetime.now().strftime("%c")

def replace_random_user(message, tab):
    if isinstance(tab, tabs.MucTab):
        return random.choice(tab.users).nick
    elif isinstance(tab, tabs.PrivateTab):
        return random.choice([JID(tab.name).resource, tab.own_nick])
    else:
        # that doesn’t make any sense. By why use this pattern in a
        # ConversationTab anyway?
        return str(tab.name)

def replace_dice(message, tab):
    return str(random.randrange(1, 7))
