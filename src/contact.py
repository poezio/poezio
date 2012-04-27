# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Defines the Resource and Contact classes, which are used in
the roster
"""

import logging
log = logging.getLogger(__name__)

from sleekxmpp.xmlstream.stanzabase import JID

class Resource(object):
    """
    Defines a roster item.
    It's a precise resource.
    """
    def __init__(self, jid, data):
        self._jid = JID(jid)         # Full jid
        self._data = data

    @property
    def jid(self):
        return self._jid

    @property
    def priority(self):
        return self._data['priority']

    @property
    def presence(self):
        return self._data['show']

    @property
    def status(self):
        return self._data['status']

    def __repr__(self):
        return '<%s>' % self._jid

class Contact(object):
    """
    This a way to gather multiple resources from the same bare JID.
    This class contains zero or more Resource object and useful methods
    to get the resource with the highest priority, etc
    """
    def __init__(self, item):
        """
        item: a SleekXMPP RosterItem pointing to that contact
        """
        self.__item = item
        self.folded = True      # Folded by default

    @property
    def groups(self):
        """Name of the groups the contact is in"""
        return self.__item['groups'] or ['none']

    @property
    def resources(self):
        """Resources of the contact"""
        return self._resources

    @property
    def bare_jid(self):
        """The bare_jid or the contact"""
        return self.__item.jid

    @property
    def name(self):
        return self.__item['name'] or ''

    @property
    def ask(self):
        if self.__item['pending_out']:
            return 'asked'

    @property
    def pending_in(self):
        return self.__item['pending_in']

    @pending_in.setter
    def pending_in(self, value):
        self.__item['pending_in'] = value

    @property
    def pending_out(self):
        return self.__item['pending_out']

    @pending_out.setter
    def pending_out(self, value):
        self.__item['pending_out'] = value

    @property
    def resources(self):
        """List of the available resources as Resource objects"""
        return [Resource('%s/%s' % (self.bare_jid, key), self.__item.resources[key])
                for key in self.__item.resources]

    @property
    def subscription(self):
        return self.__item['subscription']

    def __contains__(self, value):
        return value in self.__item.resources or JID(value).resource in self.__item.resources

    def __len__(self):
        """Number of resources"""
        return len(self.__item.resources)

    def __bool__(self):
        """This contacts exists even when he has no resources"""
        return True

    def __getitem__(self, key):
        """Return the corresponding Resource object, or None"""
        res = JID(key).resource
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

    def get(self, key, default=None):
        """Same as __getitem__, but with a configurable default"""
        return self[key] or default

    def get_resources(self):
        """Return all resources, sorted by priority """
        compare_resources = lambda x: x.priority
        return sorted(self.resources, key=compare_resources)

    def get_highest_priority_resource(self):
        """Return the resource with the highest priority"""
        resources = self.get_resources()
        if resources:
            return resources[-1]
        return None

    def toggle_folded(self):
        """
        Fold if it's unfolded, and vice versa
        """
        self.folded = not self.folded

    def __repr__(self):
        ret = '<Contact: %s' % self.bare_jid
        for resource in self.resources:
            ret += '\n\t\t%s' % resource
        return ret + ' />\n'
