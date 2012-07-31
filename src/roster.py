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

from config import config
from os import path as p
from contact import Contact
from sleekxmpp.xmlstream.stanzabase import JID
from sleekxmpp.exceptions import IqError

class Roster(object):
    """
    The proxy class to get the roster from SleekXMPP.
    Adds a blacklist for the MUC domains (or else they would show here),
    and caches Contact and RosterGroup objects.
    """

    # MUC domains to blacklist from the contacts roster
    blacklist = set()

    def __init__(self):
        """
        node: the RosterSingle from SleekXMPP
        """
        self.__node = None
        self.contact_filter = None # A tuple(function, *args)
                                    # function to filter contacts,
                                    # on search, for example
        self.folded_groups = set(config.get(
                'folded_roster_groups',
                '',
                section='var').split(':'))
        self.groups = {}
        self.contacts = {}

    def __getitem__(self, key):
        """Get a Contact from his bare JID"""
        key = JID(key).bare
        if key in self.contacts and self.contacts[key] is not None:
            return self.contacts[key]
        if key in self.jids():
            contact = Contact(self.__node[key])
            self.contacts[key] = contact
            return contact

    def __setitem__(self, key, value):
        """Set the a Contact value for the bare jid key"""
        self.contacts[key] = value

    def __delitem__(self, jid):
        """Remove a contact from the roster"""
        jid = JID(jid).bare
        contact = self[jid]
        if not contact:
            return
        for group in list(self.groups.values()):
            group.remove(contact)
            if not group:
                del self.groups[group.name]
        del self.contacts[contact.bare_jid]
        if jid in self.jids():
            try:
                self.__node[jid].send_presence(ptype='unavailable')
                self.__node.remove(jid)
            except IqError:
                import traceback
                log.debug('IqError when removing %s:\n%s', jid, traceback.format_exc())

    def __iter__(self):
        """Iterate over the jids of the contacts"""
        return iter(self.contacts.values())

    def __contains__(self, key):
        """True if the bare jid is in the roster, false otherwise"""
        return JID(key).bare in self.jids()

    @property
    def jid(self):
        """Our JID"""
        return self.__node.jid

    def set_node(self, value):
        """Set the SleekXMPP RosterSingle for our roster"""
        self.__node = value

    def get_groups(self):
        """Return a list of the RosterGroups"""
        return [group for group in self.groups.values() if group]

    def get_group(self, name):
        """Return a group or create it if not present"""
        if name in self.groups:
            return self.groups[name]
        self.groups[name] = RosterGroup(name, folded=name in self.folded_groups)

    def add(self, jid):
        """Subscribe to a jid"""
        self.__node.subscribe(jid)

    def jids(self):
        """List of the contact JIDS"""
        return [key for key in self.__node.keys() if JID(key).server not in self.blacklist and key != self.jid]

    def get_contacts(self):
        """
        Return a list of all the contacts
        """
        return [self[jid] for jid in self.jids()]

    def save_to_config_file(self):
        """
        Save various information to the config file
        e.g. the folded groups
        """
        folded_groups = ':'.join([group.name for group in self.groups.values()\
                                      if group.folded])
        log.debug('folded:%s\n' %folded_groups)
        config.set_and_save('folded_roster_groups', folded_groups, 'var')

    def get_nb_connected_contacts(self):
        """
        Get the number of connected contacts
        """
        n = 0
        for contact in self:
            if contact.resources:
                n += 1
        return n

    def update_contact_groups(self, contact):
        """Regenerate the RosterGroups when receiving a contact update"""
        if not isinstance(contact, Contact):
            contact = self[contact]
        if not contact:
            return
        for name, group in self.groups.items():
            if name in contact.groups and contact not in group:
                group.add(contact)
            elif contact in group and name not in contact.groups:
                group.remove(contact)

        for group in contact.groups:
            if not group in self.groups:
                self.groups[group] = RosterGroup(group, folded=group in self.folded_groups)
                self.groups[group].add(contact)

    def __len__(self):
        """
        Return the number of line that would be printed
        for the whole roster
        """
        length = 0
        show_offline = config.get('roster_show_offline', 'false') == 'true'
        for group in self.groups.values():
            if not show_offline and group.get_nb_connected_contacts() == 0:
                continue
            if not group.name in self.folded_groups:
                for contact in group.get_contacts(self.contact_filter):
                    # We do not count the offline contacts (depending on config)
                    if not show_offline and\
                            len(contact) == 0:
                        continue
                    length += 1      # One for the contact's line
                    if not contact.folded:
                        # One for each resource, if the contact is unfolded
                        length += len(contact)
            length += 1              # One for the group's line itself
        return length

    def __repr__(self):
        ret = '== Roster:\nContacts:\n'
        for contact in self.contacts.values():
            ret += '%s\n' % (contact,)
        ret += 'Groups\n'
        for group in self.groups:
            ret += '%s\n' % (group,)
        return ret + '\n'

    def export(self, path):
        """Export a list of bare jids to a given file"""
        if p.isfile(path):
            return
        try:
            f = open(path, 'w+')
            f.writelines([i + "\n" for i in self.contacts])
            f.close()
            return True
        except IOError:
            return

PRESENCE_PRIORITY = {'unavailable': 5,
                     'xa': 4,
                     'away': 3,
                     'dnd': 2,
                     '': 1,
                     'available': 1}

def sort_jid(contact):
    return contact.bare_jid

def sort_show(contact):
    res = contact.get_highest_priority_resource()
    if not res:
        return 0
    show = res.presence
    if show not in PRESENCE_PRIORITY:
        return 0
    return PRESENCE_PRIORITY[show]

def sort_resource_nb(contact):
    return - len(contact)

def sort_name(contact):
    return contact.name.lower() or contact.bare_jid

SORTING_METHODS = {
    'jid': sort_jid,
    'show': sort_show,
    'resource': sort_resource_nb,
    'name': sort_name,
}

class RosterGroup(object):
    """
    A RosterGroup is a group containing contacts
    It can be Friends/Family etc, but also can be
    Online/Offline or whatever
    """
    def __init__(self, name, contacts=None, folded=False):
        if not contacts:
            contacts = []
        self.contacts = set(contacts)
        self.name = name
        self.folded = folded    # if the group content is to be shown

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
        contact_list = self.contacts.copy() if not contact_filter\
            else [contact for contact in self.contacts.copy() if contact_filter[0](contact, contact_filter[1])]

        for sorting in sort.split('_'):
            method = SORTING_METHODS.get(sorting, lambda x: 0)
            if sorting == 'reverse':
                contact_list = list(reversed(contact_list))
            else:
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
        return len([1 for contact in self.contacts if contact.resources])


# Shared roster object
roster = Roster()
