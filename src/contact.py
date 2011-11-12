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
    def __init__(self, jid):
        self._jid = JID(jid)         # Full jid
        self._status = ''
        self._presence = 'unavailable'
        self._priority = 0

    @property
    def jid(self):
        return self._jid

    def __repr__(self):
        return '%s' % self._jid

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        assert isinstance(value, int)
        self._priority = value

    @property
    def presence(self):
        return self._presence

    @presence.setter
    def presence(self, value):
        self._presence = value

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value

class Contact(object):
    """
    This a way to gather multiple resources from the same bare JID.
    This class contains zero or more Resource object and useful methods
    to get the resource with the highest priority, etc
    """
    def __init__(self, bare_jid):
        self._jid = bare_jid
        self._resources = []
        self._folded = True      # Folded by default
        self._display_name = None
        self._subscription = 'none'
        self._ask = None
        self._groups = []       # a list of groups the contact is in

    @property
    def groups(self):
        """Groups the contact is in"""
        return self._groups

    @property
    def bare_jid(self):
        """The bare_jid or the contact"""
        return self._jid

    def get_highest_priority_resource(self):
        """
        Return the resource with the highest priority
        """
        ret = None
        for resource in self._resources:
            if not ret or ret.priority < resource.priority:
                ret = resource
        return ret

    def add_resource(self, resource):
        """
        Called, for example, when a new resource get offline
        (the first, or any subsequent one)
        """
        def f(o):
            return o.priority
        self._resources.append(resource)
        self._resources = sorted(self._resources, key=f, reverse=True)

    def remove_resource(self, resource):
        """
        Called, for example, when one resource goes offline.
        """
        self._resources.remove(resource)

    def remove_resource_by_fulljid(self, fulljid):
        """
        Like 'remove_resource' but just by knowing the full jid
        """
        for resource in self._resources:
            if resource.jid == fulljid:
                self._resources.remove(resource)
                return
        assert False

    def get_resource_by_fulljid(self, fulljid):
        """
        Return the resource with the given fulljid
        """
        for resource in self._resources:
            if resource.jid.full == fulljid:
                return resource
        return None

    def toggle_folded(self):
        """
        Fold if it's unfolded, and vice versa
        """
        self._folded = not self._folded

    @property
    def name(self):
        return self._display_name

    @name.setter
    def name(self, value):
        self._display_name = value

    @property
    def ask(self):
        return self._ask

    @ask.setter
    def ask(self, value):
        self._ask = value

    @property
    def subscription(self):
        return self._subscription

    @subscription.setter
    def subscription(self, value):
        self._subscription = value

    def get_nb_resources(self):
        """
        Get the number of connected resources
        """
        return len(self._resources)

    def get_resources(self):
        """
        Return all resources, sorted by priority
        """
        compare_resources = lambda x: x.priority
        return sorted(self._resources, key=compare_resources)

    def __repr__(self):
        ret = '<Contact: %s' % self._jid
        for resource in self._resources:
            ret += '\n\t\t%s' % resource
        return ret + ' />\n'
