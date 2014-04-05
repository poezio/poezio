"""
Module defining structures useful to the core class and related methods
"""
import collections
from gettext import gettext as _

# http://xmpp.org/extensions/xep-0045.html#errorstatus
ERROR_AND_STATUS_CODES = {
    '401': _('A password is required'),
    '403': _('Permission denied'),
    '404': _('The room doesn’t exist'),
    '405': _('Your are not allowed to create a new room'),
    '406': _('A reserved nick must be used'),
    '407': _('You are not in the member list'),
    '409': _('This nickname is already in use or has been reserved'),
    '503': _('The maximum number of users has been reached'),
    }

# http://xmpp.org/extensions/xep-0086.html
DEPRECATED_ERRORS = {
    '302': _('Redirect'),
    '400': _('Bad request'),
    '401': _('Not authorized'),
    '402': _('Payment required'),
    '403': _('Forbidden'),
    '404': _('Not found'),
    '405': _('Not allowed'),
    '406': _('Not acceptable'),
    '407': _('Registration required'),
    '408': _('Request timeout'),
    '409': _('Conflict'),
    '500': _('Internal server error'),
    '501': _('Feature not implemented'),
    '502': _('Remote server error'),
    '503': _('Service unavailable'),
    '504': _('Remote server timeout'),
    '510': _('Disconnected'),
}

possible_show = {'available':None,
                 'chat':'chat',
                 'away':'away',
                 'afk':'away',
                 'dnd':'dnd',
                 'busy':'dnd',
                 'xa':'xa'
                 }

Status = collections.namedtuple('Status', 'show message')
Command = collections.namedtuple('Command', 'func desc comp short usage')
