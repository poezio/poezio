# Copyright 2010 Le Coz Florent <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

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

    def get_jid(self):
        return self._jid

    def __repr__(self):
        return '%s' % self._jid

    def set_priority(self, priority):
        assert isinstance(priority, int)
        self._priority = priority

    def get_priority(self):
        return self._priority

    def set_presence(self, pres):
        self._presence = pres

    def get_presence(self):
        return self._presence

    def get_status(self):
        return self._status

    def set__status(self, s):
        self._status = s

class Contact(object):
    """
    This a way to gather multiple resources from the same bare JID.
    This class contains zero or more esource class and useful methods
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

    def get_bare_jid(self):
        """
        Just get the bare_jid or the contact
        """
        return self._jid

    def get_highest_priority_resource(self):
        """
        There must be, at any time, at least ONE resource.
        And they always should be ordered by priority.
        """
        ret = None
        for resource in self._resources:
            if not ret or ret.get_priority() < resource.get_priority():
                ret = resource
        return ret

    def add_resource(self, resource):
        """
        Called, for example, when a new resource get offline
        (the first, or any subsequent one)
        """
        # TODO sort by priority
        self._resources.append(resource)

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
            if resource.get_jid().full == fulljid:
                self._resources.remove(resource)
                return
        assert False

    def get_resource_by_fulljid(self, fulljid):
        """
        Return the resource with the given fulljid
        """
        for resource in self._resources:
            if resource.get_jid().full == fulljid:
                return resource
        return None
    def toggle_folded(self):
        """
        Fold if it's unfolded, and vice versa
        """
        self._folded = not self._folded

    def set_name(self, name):
        self._display_name = name

    def get_name(self):
        return self._display_name

    def set_ask(self, ask):
        self._ask = ask

    def get_ask(self):
        return self._ask

    def set_subscription(self, sub):
        self._subscription = sub

    def get_subscription(self, sub):
        return self._subscription

    def get_nb_resources(self):
        """
        Get the number of connected resources
        """
        return len(self._resources)

    def get_resources(self):
        """
        Return all resources
        """
        compare_resources = lambda x: x.get_priority()
        return sorted(self._resources, key=compare_resources)

    def __repr__(self):
        ret = '<Contact: %s' % self._jid
        for resource in self._resources:
            ret += '\n\t\t%s'%resource
        return ret + ' />\n'
