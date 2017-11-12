"""
Defines the roster sorting methods used in roster.py
(for contacts/groups)
"""

########################### Contacts sorting ############################

PRESENCE_PRIORITY = {
    'unavailable': 5,
    'xa': 4,
    'away': 3,
    'dnd': 2,
    '': 1,
    'available': 1
}


def sort_jid(contact):
    """Sort by contact JID"""
    return contact.bare_jid


def sort_show(contact):
    """Sort by show (from high availability to low)"""
    res = contact.get_highest_priority_resource()
    if not res:
        return 5
    show = res.presence
    if show not in PRESENCE_PRIORITY:
        return 0
    return PRESENCE_PRIORITY[show]


def sort_resource_nb(contact):
    """Sort by number of connected resources"""
    return -len(contact)


def sort_name(contact):
    """Sort by name (case insensitive)"""
    return contact.name.lower() or contact.bare_jid


def sort_sname(contact):
    """Sort by name (case sensitive)"""
    return contact.name or contact.bare_jid


def sort_online(contact):
    """Sort by connected/disconnected"""
    result = sort_show(contact)
    return 0 if result < 5 else 1


SORTING_METHODS = {
    'jid': sort_jid,
    'sname': sort_sname,
    'show': sort_show,
    'resource': sort_resource_nb,
    'name': sort_name,
    'online': sort_online,
}

######################## Roster Groups sorting ##########################


def sort_group_name(group):
    """Sort by name (case insensitive)"""
    return group.name.lower()


def sort_group_sname(group):
    """Sort by name (case-sensitive)"""
    return group.name


def sort_group_folded(group):
    """Sort by folded/unfolded"""
    return group.folded


def sort_group_connected(group):
    """Sort by number of connected contacts"""
    return -group.get_nb_connected_contacts()


def sort_group_size(group):
    """Sort by group size"""
    return -len(group)


def sort_group_none(group):
    """Put the none group at the end, if any"""
    return 0 if group.name != 'none' else 1


GROUP_SORTING_METHODS = {
    'name': sort_group_name,
    'fold': sort_group_folded,
    'connected': sort_group_connected,
    'size': sort_group_size,
    'none': sort_group_none,
    'sname': sort_group_sname,
}
