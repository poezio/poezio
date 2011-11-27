import os

from sleekxmpp.plugins.xep_0048 import *
from core import JID
from config import config

preferred = config.get('use_bookmarks_method', 'pep').lower()
if preferred not in ('pep', 'privatexml'):
    preferred = 'privatexml'
not_preferred = 'privatexml' if preferred is 'pep' else 'privatexml'
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

bookmarks = []

def get_by_jid(value):
    """
    Get a bookmark by bare jid
    """
    for item in bookmarks:
        if item.jid == value:
            return item

def remove(value):
    """
    Remove a bookmark
    """
    if isinstance(value, str):
        value = get_by_jid(value)
    bookmarks.remove(value)

def stanza_pep():
    storage = Storage()
    for b in filter(lambda b: b.method == 'pep', bookmarks):
        storage.append(b.stanza())
    return storage

def stanza_privatexml():
    storage = Storage()
    for b in filter(lambda b: b.method == 'privatexml', bookmarks):
        storage.append(b.stanza())
    return storage

def save_pep(xmpp):
    xmpp.plugin['xep_0048'].set_bookmarks(stanza_pep())

def save_privatexml(xmpp):
    xmpp.plugin['xep_0048'].set_bookmarks_old(stanza_privatexml())

def save_remote(xmpp, core=None):
    method = config.get('use_bookmarks_method', '')
    if method not in ('pep', 'privatexml'):
        try:
            save_privatexml(xmpp)
        except:
            if core:
                core.information('Could not save bookmarks.', 'Error')
    else:
        try:
            if method == 'pep':
                save_pep(xmpp)
            else:
                save_privatexml(xmpp)
        except:
            if core:
                core.information('Could not save bookmarks.', 'Error')

def save_local():
    all = ''
    for bookmark in filter(lambda b: b.method == "local", bookmarks):
        st = bookmark.jid
        if bookmark.nick:
            st += '/' + bookmark.nick
        st += ':'
        all += st
    config.set_and_save('rooms', all)

def save(xmpp, core=None):
    save_local()
    save_remote(xmpp, core)

def get_pep(xmpp):
    try:
        iq = xmpp.plugin['xep_0048'].get_bookmarks()
    except:
        return False
    for conf in iq.xml.iter('{storage:bookmarks}conference'):
        b = Bookmark.parse_from_element(conf, method='pep')
        if not get_by_jid(b.jid):
            bookmarks.append(b)
    return True

def get_privatexml(xmpp):
    try:
        iq = xmpp.plugin['xep_0048'].get_bookmarks_old()
    except:
        return False
    for conf in iq.xml.iter('{storage:bookmarks}conference'):
        b = Bookmark.parse_from_element(conf, method='privatexml')
        if not get_by_jid(b.jid):
            bookmarks.append(b)
    return True

def get_remote(xmpp):
    if xmpp.anon:
        return
    pep, privatexml = True, True
    for method in methods[1:]:
        if method == 'pep':
            pep = get_pep(xmpp)
        else:
            privatexml = get_privatexml(xmpp)
    if pep and not privatexml:
        config.set_and_save('use_bookmarks_method', 'pep')
    elif privatexml and not pep:
        config.set_and_save('use_bookmarks_method', 'privatexml')
    elif not pep and not privatexml:
        config.set_and_save('use_bookmarks_method', '')

def get_local():
    rooms = config.get('rooms', '')
    if not rooms:
        return
    rooms = rooms.split(':')
    for room in rooms:
        jid = JID(room)
        if jid.bare == '':
            continue
        if jid.resource != '':
            nick = jid.resource
        else:
            nick = None
        b = Bookmark(jid.bare, autojoin=True, nick=nick, method='local')
        if not get_by_jid(b.jid):
            bookmarks.append(b)
