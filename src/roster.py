# Copyright 2010 Le Coz Florent <louizatakk@fedoraproject.org>
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

from contact import Contact

from common import debug

class Roster(object):
    def __init__(self):
        self._contacts = {}     # key = jid; value = Contact()
        self._roster_groups = []

    def add_contact(self, contact, jid):
        """
        Add a contact to the contact list
        """
        assert jid not in self._contacts
        self._contacts[jid] = contact

    def get_contact_len(self):
        return len(self._contacts.keys())

    def get_contact_by_jid(self, jid):
        if jid in self._contacts:
            return self._contacts[jid]
        return None

    def edit_groups_of_contact(self, contact, groups):
        """
        Edit the groups the contact is in
        Add or remove RosterGroup if needed
        """
        # add the contact to each group he is in
        if not len(groups):
            groups = ['none']
        for group in groups:
            if group in contact._groups:
                continue
            else:
                # create the group if it doesn't exist yet
                contact._groups.append(group)
                self.add_contact_to_group(group, contact)
        # remove the contact from each group he is not in
        for group in contact._groups:
            if group not in groups:
                # the contact is not in the group anymore
                self.remove_contact_from_group(group, contact)

    def remove_contact_from_group(self, group_name, contact):
        """
        Remove the contact from the group.
        Remove also the group if this makes it empty
        """
        for group in self._roster_groups:
            if group.name == group_name:
                group.remove_contact(contact)
                if group.is_empty():
                    self._roster_groups.remove(group)
                return

    def add_contact_to_group(self, group_name, contact):
        """
        Add the contact to the group.
        Create the group if it doesn't already exist
        """
        for group in self._roster_groups:
            if group.name == group_name:
                group.add_contact(contact)
                return
        new_group = RosterGroup(group_name)
        self._roster_groups.append(new_group)
        new_group.add_contact(contact)

    def get_groups(self):
        return self._roster_groups

    def __len__(self):
        """
        Return the number of line that would be printed
        """
        l = 0
        for group in self._roster_groups:
            l += 1
            if not group.folded:
                for contact in group.get_contacts():
                    l += 1
        return l

    def __repr__(self):
        ret = '== Roster:\nContacts:\n'
        for contact in self._contacts:
            ret += '%s\n' % (contact,)
        ret += 'Groups\n'
        for group in self._roster_groups:
            ret += '%s\n' % (group,)
        return ret + '\n'

class RosterGroup(object):
    """
    A RosterGroup is a group containing contacts
    It can be Friends/Family etc, but also can be
    Online/Offline or whatever
    """
    def __init__(self, name, folded=False):
        # debug('New group: %s \n' % name)
        self._contacts = []
        self.name = name
        self.folded = folded    # if the group content is to be shown
    def is_empty(self):
        return len(self._contacts) == 0

    def remove_contact(self, contact):
        """
        Remove a Contact object to the list
        """
        assert isinstance(contact, Contact)
        assert contact in self._contacts
        self._contacts.remove(contact)

    def add_contact(self, contact):
        """
        append a Contact object to the list
        """
        assert isinstance(contact, Contact)
        assert contact not in self._contacts
        self._contacts.append(contact)

    def get_contacts(self):
        return self._contacts

    def __repr__(self):
        return '<Roster_group: %s; %s>' % (self.name, self._contacts)
