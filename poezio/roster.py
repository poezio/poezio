# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.
"""
Defines the Roster and RosterGroup classes
"""
import logging
log = logging.getLogger(__name__)

from poezio.config import config
from poezio.contact import Contact
from poezio.roster_sorting import SORTING_METHODS, GROUP_SORTING_METHODS

from os import path as p
from datetime import datetime
from poezio.common import safeJID
from slixmpp.exceptions import IqError, IqTimeout


class Roster:
    """
    The proxy class to get the roster from slixmpp.
    Caches Contact and RosterGroup objects.
    """

    DEFAULT_FILTER = (lambda x, y: None, None)

    def __init__(self):
        """
        node: the RosterSingle from slixmpp
        """
        self.__node = None

        # A tuple(function, *args) function to filter contacts
        # on search, for example
        self.contact_filter = self.DEFAULT_FILTER
        self.folded_groups = set(
            config.get('folded_roster_groups', section='var').split(':'))
        self.groups = {}
        self.contacts = {}
        self.length = 0
        self.connected = 0

        # Used for caching roster infos
        self.last_built = datetime.now()
        self.last_modified = datetime.now()

    def modified(self):
        self.last_modified = datetime.now()

    @property
    def needs_rebuild(self):
        return self.last_modified >= self.last_built

    def __getitem__(self, key):
        """Get a Contact from his bare JID"""
        key = safeJID(key).bare
        if key in self.contacts and self.contacts[key] is not None:
            return self.contacts[key]
        if key in self.jids():
            contact = Contact(self.__node[key])
            self.contacts[key] = contact
            return contact

    def __setitem__(self, key, value):
        """Set the a Contact value for the bare jid key"""
        self.contacts[key] = value

    def remove(self, jid):
        """Send a removal iq to the server"""
        jid = safeJID(jid).bare
        if self.__node[jid]:
            try:
                self.__node[jid].send_presence(ptype='unavailable')
                self.__node.remove(jid)
            except (IqError, IqTimeout):
                log.debug('IqError when removing %s:', jid, exc_info=True)

    def __delitem__(self, jid):
        """Remove a contact from the roster view"""
        jid = safeJID(jid).bare
        contact = self[jid]
        if not contact:
            return
        del self.contacts[contact.bare_jid]

        for group in list(self.groups.values()):
            group.remove(contact)
            if not group:
                del self.groups[group.name]
        self.modified()

    def __iter__(self):
        """Iterate over the jids of the contacts"""
        return iter(self.contacts.values())

    def __contains__(self, key):
        """True if the bare jid is in the roster, false otherwise"""
        return safeJID(key).bare in self.jids()

    @property
    def jid(self):
        """Our JID"""
        return self.__node.jid

    def get_and_set(self, jid):
        contact = self.contacts.get(jid)
        if contact is None:
            contact = Contact(self.__node[jid])
            self.contacts[jid] = contact
            return contact
        return contact

    def set_node(self, value):
        """Set the slixmpp RosterSingle for our roster"""
        self.__node = value

    def get_groups(self, sort=''):
        """Return a list of the RosterGroups"""
        group_list = sorted(
            (group for group in self.groups.values() if group),
            key=lambda x: x.name.lower() if x.name else '')

        for sorting in sort.split(':'):
            if sorting == 'reverse':
                group_list = list(reversed(group_list))
            else:
                method = GROUP_SORTING_METHODS.get(sorting, lambda x: 0)
                group_list = sorted(group_list, key=method)
        return group_list

    def get_group(self, name):
        """Return a group or create it if not present"""
        if name in self.groups:
            return self.groups[name]
        self.groups[name] = RosterGroup(
            name, folded=name in self.folded_groups)

    def add(self, jid):
        """Subscribe to a jid"""
        self.__node.subscribe(jid)

    def jids(self):
        """List of the contact JIDS"""
        l = []
        for key in self.__node.keys():
            contact = self.get_and_set(key)
            if key != self.jid and (contact and self.exists(contact)):
                l.append(key)
        self.update_size(l)
        return l

    def update_size(self, jids=None):
        if jids is None:
            jids = self.jids()
        self.length = len(jids)

    def get_contacts(self):
        """
        Return a list of all the contacts
        """
        return [self[jid] for jid in self.jids()]

    def get_contacts_sorted_filtered(self, sort=''):
        """
        Return a list of all the contacts sorted with a criteria
        """
        contact_list = []
        for contact in self.get_contacts():
            if contact.bare_jid != self.jid:
                if self.contact_filter is not self.DEFAULT_FILTER:
                    if self.contact_filter[0](contact, self.contact_filter[1]):
                        contact_list.append(contact)
                else:
                    contact_list.append(contact)
        contact_list = sorted(contact_list, key=SORTING_METHODS['name'])

        for sorting in sort.split(':'):
            if sorting == 'reverse':
                contact_list = list(reversed(contact_list))
            else:
                method = SORTING_METHODS.get(sorting, lambda x: 0)
                contact_list = sorted(contact_list, key=method)
        return contact_list

    def save_to_config_file(self):
        """
        Save various information to the config file
        e.g. the folded groups
        """
        folded_groups = ':'.join([group.name for group in self.groups.values()\
                                      if group.folded])
        log.debug('folded:%s\n', folded_groups)
        return config.silent_set('folded_roster_groups', folded_groups, 'var')

    def get_nb_connected_contacts(self):
        """
        Get the number of connected contacts
        """
        return self.connected

    def update_contact_groups(self, contact):
        """Regenerate the RosterGroups when receiving a contact update"""
        if not isinstance(contact, Contact):
            contact = self.get_and_set(contact)
        if not contact:
            return
        for name, group in self.groups.items():
            if name in contact.groups and contact not in group:
                group.add(contact)
            elif contact in group and name not in contact.groups:
                group.remove(contact)

        for group in contact.groups:
            if group not in self.groups:
                self.groups[group] = RosterGroup(
                    group, folded=group in self.folded_groups)
                self.groups[group].add(contact)

    def __len__(self):
        """
        Return the number of contacts
        (used to return the display size, but now we have
        the display cache in RosterWin for that)
        """
        return self.length

    def __repr__(self):
        ret = '== Roster:\nContacts:\n'
        for contact in self.contacts.values():
            ret += '%s\n' % (contact, )
        ret += 'Groups\n'
        for group in self.groups:
            ret += '%s\n' % (group, )
        return ret + '\n'

    def export(self, path):
        """Export a list of bare jids to a given file"""
        if p.isfile(path):
            return False
        try:
            f = open(path, 'w+', encoding='utf-8')
            f.writelines([
                str(i) + "\n" for i in self.contacts
                if self[i] and (self[i].subscription == "both" or self[i].ask)
            ])
            f.close()
            return True
        except OSError:
            return False

    def exists(self, contact):
        if not contact:
            return False
        for group in contact.groups:
            if contact not in self.groups.get(group, tuple()):
                return False
        return True


class RosterGroup:
    """
    A RosterGroup is a group containing contacts
    It can be Friends/Family etc, but also can be
    Online/Offline or whatever
    """

    def __init__(self, name, contacts=None, folded=False):
        if not contacts:
            contacts = []
        self.contacts = set(contacts)
        self.name = name if name is not None else ''
        self.folded = folded  # if the group content is to be shown

    def __iter__(self):
        """Iterate over the contacts"""
        return iter(self.contacts)

    def __repr__(self):
        return '<Roster_group: %s; %s>' % (self.name, self.contacts)

    def __len__(self):
        """Number of contacts in the group"""
        return len(self.contacts)

    def __contains__(self, contact):
        """
        Return a bool, telling if the contact is in the group
        """
        return contact in self.contacts

    def add(self, contact):
        """Add a contact to the group"""
        self.contacts.add(contact)

    def remove(self, contact):
        """Remove a contact from the group if present"""
        if contact in self.contacts:
            self.contacts.remove(contact)

    def get_contacts(self, contact_filter=None, sort=''):
        """Return the group contacts, filtered and sorted"""
        if contact_filter is Roster.DEFAULT_FILTER or contact_filter is None:
            contact_list = self.contacts.copy()
        else:
            contact_list = [
                contact for contact in self.contacts.copy()
                if contact_filter[0](contact, contact_filter[1])
            ]
        contact_list = sorted(contact_list, key=SORTING_METHODS['name'])

        for sorting in sort.split(':'):
            if sorting == 'reverse':
                contact_list = list(reversed(contact_list))
            else:
                method = SORTING_METHODS.get(sorting, lambda x: 0)
                contact_list = sorted(contact_list, key=method)
        return contact_list

    def toggle_folded(self):
        """Fold/unfold the group in the roster"""
        self.folded = not self.folded
        if self.folded:
            if self.name not in roster.folded_groups:
                roster.folded_groups.add(self.name)
        else:
            if self.name in roster.folded_groups:
                roster.folded_groups.remove(self.name)

    def get_nb_connected_contacts(self):
        """Return the number of connected contacts"""
        return len([1 for contact in self.contacts if len(contact)])


def create_roster():
    "Create the global roster object"
    global roster
    roster = Roster()


# Shared roster object
roster = None
