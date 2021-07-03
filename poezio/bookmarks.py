"""
Bookmarks module

Therein the bookmark class is defined, representing one conference room.
This object is used to generate elements for both local and remote
bookmark storage. It can also parse xml Elements.

This module also defines several functions for retrieving and updating
bookmarks, both local and remote.

Poezio start scenario:

- upon initial connection, poezio will disco#info the server
- the available storage methods will be stored in the available_storage dict
    (either 'pep' or 'privatexml')
- if only one is available, poezio will set the use_bookmarks_method config option
    to it. If both are, it will be set to 'privatexml' (or if it was previously set, the
    value will be kept).
- it will then query the preferred storages for bookmarks and cache them locally
    (Bookmark objects with a method='remote' attribute)

Adding a remote bookmark:

- New Bookmark object added to the list with storage='remote'
- All bookmarks are sent to the storage selected in use_bookmarks_method
    if there was an error, the user is notified.


"""

import functools
import logging
from typing import (
    Callable,
    List,
    Optional,
    Union,
)

from slixmpp import (
    InvalidJID,
    JID,
)
from slixmpp.exceptions import IqError, IqTimeout
from slixmpp.plugins.xep_0048 import Bookmarks, Conference, URL
from poezio.connection import Connection
from poezio.config import config

log = logging.getLogger(__name__)


class Bookmark:
    def __init__(self,
                 jid: Union[JID, str],
                 name: Optional[str] = None,
                 autojoin=False,
                 nick: Optional[str] = None,
                 password: Optional[str] = None,
                 method='local') -> None:
        try:
            if isinstance(jid, JID):
                self._jid = jid
            else:
                self._jid = JID(jid)
        except InvalidJID:
            log.debug('Invalid JID %r provided for bookmark', jid)
            raise
        self.name = name or str(self.jid)
        self.autojoin = autojoin
        self.nick = nick
        self.password = password
        self._method = method

    @property
    def jid(self) -> JID:
        """Jid getter"""
        return self._jid

    @jid.setter
    def jid(self, jid: JID) -> None:
        try:
            if isinstance(jid, JID):
                self._jid = jid
            else:
                self._jid = JID(jid)
        except InvalidJID:
            log.debug('Invalid JID %r provided for bookmark', jid)
            raise

    @property
    def method(self) -> str:
        return self._method

    @method.setter
    def method(self, value: str):
        if value not in ('local', 'remote'):
            log.debug('Could not set bookmark storing method: %s', value)
            return
        self._method = value

    def __repr__(self) -> str:
        return '<%s%s|%s>' % (self.jid, ('/' + self.nick)
                              if self.nick else '', self.method)

    def stanza(self) -> Conference:
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

    def local(self) -> str:
        """Generate a str for local storage"""
        local = str(self.jid)
        if self.nick:
            local += '/%s' % self.nick
        local += ':'
        if self.password:
            config.set_and_save('password', self.password, section=self.jid)
        return local

    @functools.singledispatch
    @staticmethod
    def parse(el):
        """
        Generate a Bookmark object from a <conference/> element
        (this is a fallback for raw XML Elements)
        """
        jid = el.get('jid')
        name = el.get('name')
        autojoin = True if el.get('autojoin',
                                  'false').lower() in ('true', '1') else False
        nick = None
        for n in el.iter('nick'):
            nick = n.text
        password = None
        for p in el.iter('password'):
            password = p.text

        return Bookmark(jid, name, autojoin, nick, password, method='remote')

    @staticmethod
    @parse.register(Conference)
    def parse_from_stanza(el):
        """
        Parse a Conference element into a Bookmark object
        """
        jid = el['jid']
        autojoin = el['autojoin']
        password = el['password']
        nick = el['nick']
        name = el['name']
        return Bookmark(jid, name, autojoin, nick, password, method='remote')


class BookmarkList:
    def __init__(self):
        self.bookmarks: List[Bookmark] = []
        preferred = config.getstr('use_bookmarks_method').lower()
        if preferred not in ('pep', 'privatexml'):
            preferred = 'privatexml'
        self.preferred = preferred
        self.available_storage = {
            'privatexml': False,
            'pep': False,
        }

    def __getitem__(self, key: Union[str, JID, int]) -> Optional[Bookmark]:
        if isinstance(key, (str, JID)):
            for i in self.bookmarks:
                if key == i.jid:
                    return i
        elif isinstance(key, int):
            return self.bookmarks[key]
        return None

    def __contains__(self, key) -> bool:
        if isinstance(key, (str, JID)):
            for bookmark in self.bookmarks:
                if bookmark.jid == key:
                    return True
        else:
            return key in self.bookmarks
        return False

    def remove(self, key):
        if isinstance(key, (str, JID)):
            for i in self.bookmarks[:]:
                if i.jid == key:
                    self.bookmarks.remove(i)
        else:
            self.bookmarks.remove(key)

    def __iter__(self):
        return iter(self.bookmarks)

    def local(self) -> List[Bookmark]:
        return [bm for bm in self.bookmarks if bm.method == 'local']

    def remote(self) -> List[Bookmark]:
        return [bm for bm in self.bookmarks if bm.method == 'remote']

    def set(self, new: List[Bookmark]):
        self.bookmarks = new

    def append(self, bookmark: Bookmark):
        bookmark_exists = self[bookmark.jid]
        if not bookmark_exists:
            self.bookmarks.append(bookmark)
        else:
            self.bookmarks.remove(bookmark_exists)
            self.bookmarks.append(bookmark)

    def set_bookmarks_method(self, value: str):
        if self.available_storage.get(value):
            self.preferred = value
            config.set_and_save('use_bookmarks_method', value)

    async def save_remote(self, xmpp: Connection):
        """Save the remote bookmarks."""
        if not any(self.available_storage.values()):
            return
        method = 'xep_0049' if self.preferred == 'privatexml' else 'xep_0223'

        if method:
            return await xmpp.plugin['xep_0048'].set_bookmarks(
                stanza_storage(self.bookmarks),
                method=method,
            )

    def save_local(self):
        """Save the local bookmarks."""
        local = ''.join(bookmark.local() for bookmark in self
                        if bookmark.method == 'local')
        config.set_and_save('rooms', local)

    async def save(self, xmpp: Connection, core=None):
        """Save all the bookmarks."""
        self.save_local()
        if config.getbool('use_remote_bookmarks'):
            try:
                result = await self.save_remote(xmpp)
                if core is not None:
                    core.information('Bookmarks saved', 'Info')
                return result
            except (IqError, IqTimeout):
                if core is not None:
                    core.information(
                        'Could not save remote bookmarks.',
                        'Error'
                    )
                raise

    async def get_pep(self, xmpp: Connection):
        """Add the remotely stored bookmarks via pep to the list."""
        iq = await xmpp.plugin['xep_0048'].get_bookmarks(method='xep_0223')
        for conf in iq['pubsub']['items']['item']['bookmarks'][
                'conferences']:
            if isinstance(conf, URL):
                continue
            bookm = Bookmark.parse(conf)
            self.append(bookm)
        return iq

    async def get_privatexml(self, xmpp: Connection):
        """
        Fetch the remote bookmarks stored via privatexml.
        """

        iq = await xmpp.plugin['xep_0048'].get_bookmarks(method='xep_0049')
        for conf in iq['private']['bookmarks']['conferences']:
            bookm = Bookmark.parse(conf)
            self.append(bookm)
        return iq

    async def get_remote(self, xmpp: Connection, information: Callable):
        """Add the remotely stored bookmarks to the list."""
        if xmpp.anon or not any(self.available_storage.values()):
            information('No remote bookmark storage available', 'Warning')
            return
        if self.preferred == 'pep':
            return await self.get_pep(xmpp)
        else:
            return await self.get_privatexml(xmpp)

    def get_local(self):
        """Add the locally stored bookmarks to the list."""
        rooms = config.getlist('rooms')
        if not rooms:
            return
        for room in rooms:
            try:
                jid = JID(room)
            except InvalidJID:
                continue
            if jid.bare == '':
                continue
            if jid.resource != '':
                nick = jid.resource
            else:
                nick = None
            passwd = config.get_by_tabname(
                'password', jid.bare, fallback=False) or None
            b = Bookmark(
                jid.bare,
                jid.user,
                autojoin=True,
                nick=nick,
                password=passwd,
                method='local')
            self.append(b)


def stanza_storage(bookmarks: Union[BookmarkList, List[Bookmark]]) -> Bookmarks:
    """Generate a <storage/> stanza with the conference elements."""
    storage = Bookmarks()
    for b in (b for b in bookmarks if b.method == 'remote'):
        storage.append(b.stanza())
    return storage
