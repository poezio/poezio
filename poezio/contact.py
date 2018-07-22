# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.
"""
Defines the Resource and Contact classes, which are used in
the roster.
"""

from collections import defaultdict
import logging
from typing import Dict, Iterator, List, Optional, Union

from poezio.common import safeJID
from slixmpp import JID

log = logging.getLogger(__name__)


class Resource:
    """
    Defines a roster item.
    It's a precise resource.
    """

    def __init__(self, jid, data):
        """
        data: the dict to use as a source
        """
        # Full JID
        self._jid = jid  # type: str
        self._data = data  # type: Dict[str, Union[str, int]]

    @property
    def jid(self) -> str:
        return self._jid

    @property
    def priority(self) -> int:
        return self._data.get('priority') or 0

    @property
    def presence(self) -> str:
        return self._data.get('show') or ''

    @property
    def status(self) -> str:
        return self._data.get('status') or ''

    def __repr__(self) -> str:
        return '<%s>' % self._jid

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Resource):
            return False
        return self.jid == value.jid and self._data == value._data


class Contact:
    """
    This a way to gather multiple resources from the same bare JID.
    This class contains zero or more Resource object and useful methods
    to get the resource with the highest priority, etc
    """

    def __init__(self, item):
        """
        item: a slixmpp RosterItem pointing to that contact
        """
        self.__item = item
        self.folded_states = defaultdict(lambda: True)  # type: Dict[str, bool]
        self._name = ''
        self.avatar = None
        self.error = None
        self.tune = {}  # type: Dict[str, str]
        self.gaming = {}  # type: Dict[str, str]
        self.mood = ''
        self.activity = ''

    @property
    def groups(self) -> List[str]:
        """Name of the groups the contact is in"""
        return self.__item['groups'] or ['none']

    @property
    def bare_jid(self) -> JID:
        """The bare jid of the contact"""
        return self.__item.jid

    @property
    def name(self):
        """The name of the contact or an empty string."""
        return self.__item['name'] or self._name or ''

    @name.setter
    def name(self, value):
        """Set the name of the contact with user nickname"""
        self._name = value

    @property
    def ask(self):
        if self.__item['pending_out']:
            return 'asked'

    @property
    def pending_in(self):
        """We received a subscribe stanza from this contact."""
        return self.__item['pending_in']

    @pending_in.setter
    def pending_in(self, value):
        self.__item['pending_in'] = value

    @property
    def pending_out(self):
        """We sent a subscribe stanza to this contact."""
        return self.__item['pending_out']

    @pending_out.setter
    def pending_out(self, value):
        self.__item['pending_out'] = value

    @property
    def resources(self) -> Iterator[Resource]:
        """List of the available resources as Resource objects"""
        return (Resource('%s%s' % (self.bare_jid, ('/' + key)
                                   if key else ''), self.__item.resources[key])
                for key in self.__item.resources.keys())

    @property
    def subscription(self) -> str:
        return self.__item['subscription']

    def __contains__(self, value):
        return value in self.__item.resources or safeJID(
            value).resource in self.__item.resources

    def __len__(self) -> int:
        """Number of resources"""
        return len(self.__item.resources)

    def __bool__(self) -> bool:
        """This contact exists even when he has no resources"""
        return True

    def __getitem__(self, key) -> Optional[Resource]:
        """Return the corresponding Resource object, or None"""
        res = safeJID(key).resource
        resources = self.__item.resources
        item = resources.get(res, None) or resources.get(key, None)
        return Resource(key, item) if item else None

    def subscribe(self):
        """Subscribe to this JID"""
        self.__item.subscribe()

    def authorize(self):
        """Authorize this JID"""
        self.__item.authorize()

    def unauthorize(self):
        """Unauthorize this JID"""
        self.__item.unauthorize()

    def unsubscribe(self):
        """Unsubscribe from this JID"""
        self.__item.unsubscribe()

    def get(self, key: str,
            default: Optional[Resource] = None) -> Optional[Resource]:
        """Same as __getitem__, but with a configurable default"""
        return self[key] or default

    def get_resources(self) -> List[Resource]:
        """Return all resources, sorted by priority """
        compare_resources = lambda x: x.priority
        return sorted(self.resources, key=compare_resources, reverse=True)

    def get_highest_priority_resource(self) -> Optional[Resource]:
        """Return the resource with the highest priority"""
        resources = self.get_resources()
        if resources:
            return resources[0]
        return None

    def folded(self, group_name='none') -> bool:
        """
        Return the Folded state of a contact for this group
        """
        return self.folded_states[group_name]

    def toggle_folded(self, group='none'):
        """
        Fold if it's unfolded, and vice versa
        """
        self.folded_states[group] = not self.folded_states[group]

    def __repr__(self) -> str:
        ret = '<Contact: %s' % self.bare_jid
        for resource in self.resources:
            ret += '\n\t\t%s' % resource
        return ret + ' />\n'
