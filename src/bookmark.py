"""
Bookmarks module

Therein the bookmark class is defined, representing one conference room.
This object is used to generate elements for both local and remote
bookmark storage. It can also parse xml Elements.

This module also defines several functions for retrieving and updating
bookmarks, both local and remote.
"""

import functools
import logging
from sys import version_info

from slixmpp.plugins.xep_0048 import Bookmarks, Conference, URL
from common import safeJID
from config import config

log = logging.getLogger(__name__)

def xml_iter(xml, tag=''):
    if version_info[1] >= 2:
        return xml.iter(tag)
    else:
        return xml.getiterator(tag)

preferred = config.get('use_bookmarks_method').lower()
if preferred not in ('pep', 'privatexml'):
    preferred = 'privatexml'
not_preferred = 'privatexml' if preferred == 'pep' else 'pep'
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
        return '<%s%s%s%s>' % (self.jid, ('/'+self.nick) if self.nick else '', '|autojoin' if self.autojoin else '', '|%s' % self.password if self.password else '')

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

    @staticmethod
    def parse_from_stanza(el, method=None):
        jid = el['jid']
        autojoin = el['autojoin']
        password = el['password']
        nick = el['nick']
        name = el['name']
        return Bookmark(jid, name, autojoin, nick, password, method)

    @staticmethod
    def parse_from_element(el, method=None):
        """
        Generate a Bookmark object from a <conference/> element
        """
        if isinstance(el, Conference):
            return Bookmark.parse_from_stanza(el, method)
        jid = el.get('jid')
        name = el.get('name')
        autojoin = True if el.get('autojoin', 'false').lower() in ('true', '1') else False
        nick = None
        for n in xml_iter(el, 'nick'):
            nick = n.text
        password = None
        for p in xml_iter(el, 'password'):
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
    for b in (b for b in bookmarks if b.method == method):
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

def save_remote(xmpp, callback, method=preferred):
    """Save the remote bookmarks."""
    method = 'privatexml' if method != 'pep' else 'pep'

    if method is 'privatexml':
        xmpp.plugin['xep_0048'].set_bookmarks(stanza_storage('privatexml'),
                                              method='xep_0049',
                                              callback=callback)
    else:
        xmpp.plugin['xep_0048'].set_bookmarks(stanza_storage('pep'),
                                              method='xep_0223',
                                              callback=callback)

def save_local():
    """Save the local bookmarks."""
    local = ''.join(bookmark.local() for bookmark in bookmarks if bookmark.method is 'local')
    config.set_and_save('rooms', local)

def save(xmpp, core=None):
    """Save all the bookmarks."""
    save_local()
    def _cb(core, iq):
        if iq["type"] == "error":
            core.information('Could not save bookmarks.', 'Error')
        elif core:
            core.information('Bookmarks saved', 'Info')
    if config.get('use_remote_bookmarks'):
        preferred = config.get('use_bookmarks_method')
        cb = functools.partial(_cb, core)
        save_remote(xmpp, cb, method=preferred)

def get_pep(xmpp, available_methods, callback):
    """Add the remotely stored bookmarks via pep to the list."""
    def _cb(iq):
        if iq["type"] == "error":
            available_methods["pep"] = False
        else:
            available_methods["pep"] = True
            for conf in iq['pubsub']['items']['item']['bookmarks']['conferences']:
                if isinstance(conf, URL):
                    continue
                b = Bookmark.parse_from_element(conf, method='pep')
                if not get_by_jid(b.jid):
                    bookmarks.append(b)
        if callback:
            callback()

    xmpp.plugin['xep_0048'].get_bookmarks(method='xep_0223', callback=_cb)

def get_privatexml(xmpp, available_methods, callback):
    """Add the remotely stored bookmarks via privatexml to the list.
    If both is True, we want to have the result of both methods (privatexml and pep) before calling pep"""
    def _cb(iq):
        if iq["type"] == "error":
            available_methods["privatexml"] = False
        else:
            available_methods["privatexml"] = True
            for conf in iq['private']['bookmarks']['conferences']:
                b = Bookmark.parse_from_element(conf, method='privatexml')
                if not get_by_jid(b.jid):
                    bookmarks.append(b)
        if callback:
            callback()

    xmpp.plugin['xep_0048'].get_bookmarks(method='xep_0049', callback=_cb)

def get_remote(xmpp, callback):
    """Add the remotely stored bookmarks to the list."""
    if xmpp.anon:
        return
    method = config.get('use_bookmarks_method')
    if not method:
        available_methods = {}
        def _save_and_call_callback():
            # If both methods returned a result, we can now call the given callback
            if callback and "privatexml" in available_methods and "pep" in available_methods:
                save_bookmarks_method(available_methods)
                if callback:
                    callback()
        for method in methods[1:]:
            if method == 'pep':
                get_pep(xmpp, available_methods, _save_and_call_callback)
            else:
                get_privatexml(xmpp, available_methods, _save_and_call_callback)
    else:
        if method == 'pep':
            get_pep(xmpp, {}, callback)
        else:
            get_privatexml(xmpp, {}, callback)

def save_bookmarks_method(available_methods):
    pep, privatexml = available_methods["pep"], available_methods["privatexml"]
    if pep and not privatexml:
        config.set_and_save('use_bookmarks_method', 'pep')
    elif privatexml and not pep:
        config.set_and_save('use_bookmarks_method', 'privatexml')
    elif not pep and not privatexml:
        config.set_and_save('use_bookmarks_method', '')

def get_local():
    """Add the locally stored bookmarks to the list."""
    rooms = config.get('rooms')
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
        passwd = config.get_by_tabname('password', jid.bare, fallback=False) or None
        b = Bookmark(jid.bare, autojoin=True, nick=nick, password=passwd, method='local')
        if not get_by_jid(b.jid):
            bookmarks.append(b)
