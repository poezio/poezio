import os
import logging
from sys import version_info

from sleekxmpp.plugins.xep_0048 import *
from core import JID
from config import config

log = logging.getLogger(__name__)

def iter(xml, tag=''):
    if version_info[1] >= 2:
        return xml.iter(tag)
    else:
        return xml.getiterator(tag)

preferred = config.get('use_bookmarks_method', 'pep').lower()
if preferred not in ('pep', 'privatexml'):
    preferred = 'privatexml'
not_preferred = 'privatexml' if preferred == 'pep' else 'privatexml'
methods = ('local', preferred, not_preferred)


class Bookmark(object):
    possible_methods = methods

    def __init__(self, jid, name=None, autojoin=False, nick=None, password=None, method='privatexml'):
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
            log.debug('Could not set bookmark storing method: %s', value)
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

    def local(self):
        """Generate a str for local storage"""
        local = self.jid
        if self.nick:
            local += '/%s' % self.nick
        local += ':'
        return local

    def parse_from_element(el, method=None):
        """
        Generate a Bookmark object from a <conference/> element
        """
        jid = el.get('jid')
        name = el.get('name')
        autojoin = True if el.get('autojoin', 'false').lower() in ('true', '1') else False
        nick = None
        for n in iter(el, 'nick'):
            nick = nick.text
        password = None
        for p in iter(el, 'password'):
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
    Remove a bookmark (with its jid or directly the Bookmark object).
    """
    if isinstance(value, str):
        value = get_by_jid(value)
    bookmarks.remove(value)

def stanza_storage(method):
    """Generate a <storage/> stanza with the conference elements."""
    storage = Storage()
    for b in filter(lambda b: b.method == method, bookmarks):
        storage.append(b.stanza())
    return storage

def save_pep(xmpp):
    """Save the remote bookmarks via PEP."""
    xmpp.plugin['xep_0048'].set_bookmarks(stanza_storage('pep'))

def save_privatexml(xmpp):
    """"Save the remote bookmarks with privatexml."""
    xmpp.plugin['xep_0048'].set_bookmarks_old(stanza_storage('privatexml'))

def save_remote(xmpp, method="privatexml"):
    """Save the remote bookmarks."""
    method = "privatexml" if method != 'pep'  else 'pep'

    try:
        if method is 'privatexml':
            xmpp.plugin['xep_0048'].set_bookmarks_old(stanza_storage('privatexml'))
        else:
            xmpp.plugin['xep_0048'].set_bookmarks(stanza_storage('pep'))
    except:
        import traceback
        log.debug("Could not save the bookmarks:\n%s" % traceback.format_exc())
        return False
    return True

def save_local():
    """Save the local bookmarks."""
    all = ''.join(bookmark.local() for bookmark in bookmarks if bookmark.method is 'local')
    config.set_and_save('rooms', all)

def save(xmpp, core=None):
    """Save all the bookmarks."""
    save_local()
    if config.get('use_remote_bookmarks', 'true').lower() != 'false':
        preferred = config.get('use_bookmarks_method', 'privatexml')
        if not save_remote(xmpp, method=preferred) and core:
            core.information('Could not save bookmarks.', 'Error')
            return False
        elif core:
            core.information('Bookmarks saved', 'Info')
    return True

def get_pep(xmpp):
    """Add the remotely stored bookmarks via pep to the list."""
    try:
        iq = xmpp.plugin['xep_0048'].get_bookmarks()
    except:
        return False
    for conf in iter(iq.xml, '{storage:bookmarks}conference'):
        b = Bookmark.parse_from_element(conf, method='pep')
        if not get_by_jid(b.jid):
            bookmarks.append(b)
    return True

def get_privatexml(xmpp):
    """Add the remotely stored bookmarks via privatexml to the list."""
    try:
        iq = xmpp.plugin['xep_0048'].get_bookmarks_old()
    except:
        return False
    for conf in iter(iq.xml, '{storage:bookmarks}conference'):
        b = Bookmark.parse_from_element(conf, method='privatexml')
        if not get_by_jid(b.jid):
            bookmarks.append(b)
    return True

def get_remote(xmpp):
    """Add the remotely stored bookmarks to the list."""
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
    """Add the locally stored bookmarks to the list."""
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
