"""
Module defining structures useful to the core class and related methods
"""
from dataclasses import dataclass
from typing import Any, Callable, List, Dict

__all__ = [
    'ERROR_AND_STATUS_CODES', 'DEPRECATED_ERRORS', 'POSSIBLE_SHOW', 'Status',
    'Command', 'Completion'
]

# http://xmpp.org/extensions/xep-0045.html#errorstatus
ERROR_AND_STATUS_CODES = {
    '401': 'A password is required',
    '403': 'Permission denied',
    '404': 'The room doesn’t exist',
    '405': 'Your are not allowed to create a new room',
    '406': 'A reserved nick must be used',
    '407': 'You are not in the member list',
    '409': 'This nickname is already in use or has been reserved',
    '503': 'The maximum number of users has been reached',
}

# http://xmpp.org/extensions/xep-0086.html
DEPRECATED_ERRORS = {
    '302': 'Redirect',
    '400': 'Bad request',
    '401': 'Not authorized',
    '402': 'Payment required',
    '403': 'Forbidden',
    '404': 'Not found',
    '405': 'Not allowed',
    '406': 'Not acceptable',
    '407': 'Registration required',
    '408': 'Request timeout',
    '409': 'Conflict',
    '500': 'Internal server error',
    '501': 'Feature not implemented',
    '502': 'Remote server error',
    '503': 'Service unavailable',
    '504': 'Remote server timeout',
    '510': 'Disconnected',
}

POSSIBLE_SHOW = {
    'available': None,
    'chat': 'chat',
    'away': 'away',
    'afk': 'away',
    'dnd': 'dnd',
    'busy': 'dnd',
    'xa': 'xa'
}


@dataclass
class Status:
    __slots__ = ('show', 'message')
    show: str
    message: str


class Completion:
    """
    A completion result essentially currying the input completion call.
    """
    __slots__ = ['func', 'args', 'kwargs', 'comp_list']
    def __init__(
        self,
        func: Callable[..., Any],
        comp_list: List[str],
        *args: Any,
        **kwargs: Any
    ) -> None:
        self.func = func
        self.comp_list = comp_list
        self.args = args
        self.kwargs = kwargs

    def run(self):
        return self.func(self.comp_list, *self.args, **self.kwargs)

@dataclass
class Command:
    __slots__ = ('func', 'desc', 'comp', 'short_desc', 'usage')
    func: Callable[..., Any]
    desc: str
    comp: Callable[['windows.Input'], Completion]
    short_desc: str
    usage: str
