from sleekxmpp.plugins.xep_0048 import *

class Bookmark(object):
    possible_methods = ('pep', 'privatexml', 'local')
    def __init__(self, jid, name=None, autojoin=False, nick=None, password=None, method=None):
        self.jid = jid
        self.name = name or jid
        self.autojoin = autojoin
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
