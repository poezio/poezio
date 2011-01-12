# Copyright 2010-2011 Le Coz Florent <louiz@louiz.org>
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


"""
Defines the Roster and RosterGroup classes
"""
import logging
log = logging.getLogger(__name__)

from config import config
from contact import Contact, Resource
from sleekxmpp.xmlstream.stanzabase import JID

class Roster(object):
    def __init__(self):
        self._contact_filter = None # A tuple(function, *args)
                                    # function to filter contacts,
                                    # on search, for example
        self._contacts = {}     # key = bare jid; value = Contact()
        self._roster_groups = []

    def add_contact(self, contact, jid):
        """
        Add a contact to the contact list
        """
        self._contacts[jid] = contact

    def remove_contact(self, jid):
        """
        Remove a contact from the contact list
        """
        contact = self.get_contact_by_jid(jid)
        for group in contact._groups:
            self.remove_contact_from_group(group, contact)
        del self._contacts[jid]

    def get_contact_len(self):
        """
        Return the number of contacts in this group
        """
        return len(self._contacts.keys())

    def get_contact_by_jid(self, jid):
        """
        Returns the contact with the given bare JID
        """
        # Use only the bare jid
        jid = JID(jid)
        if jid.bare in self._contacts:
            return self._contacts[jid.bare]
        return None

    def edit_groups_of_contact(self, contact, groups):
        """
        Edit the groups the contact is in
        Add or remove RosterGroup if needed
        """
        # add the contact to each group he is in
        # If the contact hasn't any group, we put her in
        # the virtual default 'none' group
        if not len(groups):
            groups = ['none']
        for group in groups:
            if group not in contact._groups:
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
        Delete the group if this makes it empty
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
                if not group.has_contact(contact):
                    group.add_contact(contact)
                return
        folded_groups = config.get('folded_roster_groups', '', section='var').split(':')
        new_group = RosterGroup(group_name, folded=group_name in folded_groups)
        self._roster_groups.append(new_group)
        new_group.add_contact(contact)

    def get_groups(self):
        """
        Returns the list of groups
        """
        return self._roster_groups

    def get_contacts(self):
        """
        Return a list of all the contact
        """
        return [contact for contact in self._contacts.values()]

    def save_to_config_file(self):
        """
        Save various information to the config file
        e.g. the folded groups
        """
        folded_groups = ':'.join([group.name for group in self._roster_groups\
                                      if group.folded])
        log.debug('folded:%s\n' %folded_groups)
        config.set_and_save('folded_roster_groups', folded_groups, 'var')

    def __len__(self):
        """
        Return the number of line that would be printed
        for the whole roster
        """
        length = 0
        for group in self._roster_groups:
            if config.get('roster_show_offline', 'false') == 'false' and group.get_nb_connected_contacts() == 0:
                continue
            length += 1              # One for the group's line itself
            if not group.folded:
                for contact in group.get_contacts(self._contact_filter):
                    # We do not count the offline contacts (depending on config)
                    if config.get('roster_show_offline', 'false') == 'false' and\
                            contact.get_nb_resources() == 0:
                        continue
                    length += 1      # One for the contact's line
                    if not contact._folded:
                        # One for each resource, if the contact is unfolded
                        length += contact.get_nb_resources()
        return length

    def __repr__(self):
        ret = '== Roster:\nContacts:\n'
        for contact in self._contacts:
            ret += '%s\n' % (contact,)
        ret += 'Groups\n'
        for group in self._roster_groups:
            ret += '%s\n' % (group,)
        return ret + '\n'

PRESENCE_PRIORITY = {'unavailable': 0,
                     'xa': 1,
                     'away': 2,
                     'dnd': 3,
                     '': 4,
                     'available': 4}

class RosterGroup(object):
    """
    A RosterGroup is a group containing contacts
    It can be Friends/Family etc, but also can be
    Online/Offline or whatever
    """
    def __init__(self, name, folded=False):
        self._contacts = []
        self.name = name
        self.folded = folded    # if the group content is to be shown

    def is_empty(self):
        return len(self._contacts) == 0

    def has_contact(self, contact):
        """
        Return a bool, telling if the contact
        is already in the group
        """
        if contact in self._contacts:
            return True
        return False

    def remove_contact(self, contact):
        """
        Remove a Contact object from the list
        """
        try:
            self._contacts.remove(contact)
        except ValueError:
            pass

    def add_contact(self, contact):
        """
        append a Contact object to the list
        """
        assert isinstance(contact, Contact)
        assert contact not in self._contacts
        self._contacts.append(contact)

    def get_contacts(self, contact_filter):
        def compare_contact(a):
            if not a.get_highest_priority_resource():
                return 0
            show = a.get_highest_priority_resource().get_presence()
            if show not in PRESENCE_PRIORITY:
                return 5
            return PRESENCE_PRIORITY[show]
        contact_list = self._contacts if not contact_filter\
            else [contact for contact in self._contacts if contact_filter[0](contact, contact_filter[1])]
        return sorted(contact_list, key=compare_contact, reverse=True)

    def toggle_folded(self):
        self.folded = not self.folded

    def __repr__(self):
        return '<Roster_group: %s; %s>' % (self.name, self._contacts)

    def __len__(self):
        return len(self._contacts)

    def get_nb_connected_contacts(self):
        l = 0
        for contact in self._contacts:
            if contact.get_highest_priority_resource():
                l += 1
        return l

roster = Roster()
