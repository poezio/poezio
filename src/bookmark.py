import os

from sleekxmpp.plugins.xep_0048 import *
from core import JID
from config import config

preferred = config.get('use_bookmarks_method', 'pep').lower()
if preferred not in ('pep', 'privatexml'):
    preferred = 'pep'
not_preferred = 'pep' if preferred is 'privatexml' else 'privatexml'
methods = ('local', preferred, not_preferred)


class Bookmark(object):

    possible_methods = methods

    def __init__(self, jid, name=None, autojoin=False, nick=None, password=None, method=None):
        self.jid = jid
        self.name = name or jid
        self.autojoin = autojoin
        if not nick:
            default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
            nick = config.get('default_nick', '') or default
        self.nick = nick
        self.password = password
        self._method = method

    @property
    def method(self):
        return self._method

    @method.setter
    def method(self, value):
        if value not in self.possible_methods:
            return
        self._method = value

    def __repr__(self):
        return '<%s>' % self.jid

    def stanza(self):
        """
        Generate a <conference/> stanza from the instance
        """
        el = Conference()
        el['name'] = self.name
        el['jid'] = self.jid
        el['autojoin'] = 'true' if self.autojoin else 'false'
        if self.nick:
            n = Nick().xml
            n.text = self.nick
            el.append(n)
        if self.password:
            p = Password().xml
            p.text = self.password
            el.append(p)
        return el

    def parse_from_element(el, method=None):
        """
        Generate a Bookmark object from a <conference/> element
        """
        jid = el.get('jid')
        name = el.get('name')
        autojoin = True if el.get('autojoin', False) == 'true' else False
        nick = None
        for n in el.iter('nick'):
            nick = nick.text
        password = None
        for p in el.iter('password'):
            password = p.text

        return Bookmark(jid, name, autojoin, nick, password, method)

