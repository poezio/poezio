import os
import logging
from sys import version_info

from sleekxmpp.plugins.xep_0048 import *
from common import safeJID
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
        return '<%s%s%s>' % (self.jid, ('/'+self.nick) if self.nick else '', '|autojoin' if self.autojoin else '')

    def stanza(self):
        """
        Generate a <conference/> stanza from the instance
        """
        el = Conference()
        el['name'] = self.name
        el['jid'] = self.jid
        el['autojoin'] = 'true' if self.autojoin else 'false'
        if self.nick:
            el['nick'] = self.nick
        if self.password:
            el['password'] = self.password
        return el

    def local(self):
        """Generate a str for local storage"""
        local = self.jid
        if self.nick:
            local += '/%s' % self.nick
        local += ':'
        if self.password:
            config.set_and_save('password', self.password, section=self.jid)
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
    storage = Bookmarks()
    for b in filter(lambda b: b.method == method, bookmarks):
        storage.append(b.stanza())
    return storage

def save_pep(xmpp):
    """Save the remote bookmarks via PEP."""
    xmpp.plugin['xep_0048'].set_bookmarks(stanza_storage('pep'),
            method='xep_0223')

def save_privatexml(xmpp):
    """"Save the remote bookmarks with privatexml."""
    xmpp.plugin['xep_0048'].set_bookmarks(stanza_storage('privatexml'),
            method='xep_0049')

def save_remote(xmpp, method=preferred):
    """Save the remote bookmarks."""
    method = "privatexml" if method != 'pep'  else 'pep'

    try:
        if method is 'privatexml':
            xmpp.plugin['xep_0048'].set_bookmarks(stanza_storage('privatexml'),
                    method='xep_0049')
        else:
            xmpp.plugin['xep_0048'].set_bookmarks(stanza_storage('pep'),
                    method='xep_0223')
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
        iq = xmpp.plugin['xep_0048'].get_bookmarks(method='xep_0223', block=True)
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
        iq = xmpp.plugin['xep_0048'].get_bookmarks(method='xep_0049', block=True)
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
    method = config.get('use_bookmarks_method', '')
    if not method:
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
    else:
        if method == 'pep':
            get_pep(xmpp)
        else:
            get_privatexml(xmpp)

def get_local():
    """Add the locally stored bookmarks to the list."""
    rooms = config.get('rooms', '')
    if not rooms:
        return
    rooms = rooms.split(':')
    for room in rooms:
        jid = safeJID(room)
        if jid.bare == '':
            continue
        if jid.resource != '':
            nick = jid.resource
        else:
            nick = None
        passwd = config.get_by_tabname('password', '', jid.bare, fallback=False) or None
        b = Bookmark(jid.bare, autojoin=True, nick=nick, password=passwd, method='local')
        if not get_by_jid(b.jid):
            bookmarks.append(b)
