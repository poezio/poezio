"""
Replace a pattern from a message you're about to send, by the result of a
function.  For example you can insert the current time in your sentence by
writing %time% in it.
"""

from plugin import BasePlugin
import tabs
import datetime
import random
from sleekxmpp.xmlstream.stanzabase import JID

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
            while True:
                # we don't use a replace on all occurence, otherwise the
                # result would be the same for all occurence of the pattern
                # and that's not desirable in some of them (for example the
                # ones that provide random results)
                new = body.replace('%%%s%%' % pattern,
                                   self.patterns[pattern](message, tab), 1)
                if new == body:
                    break
                body = new
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
