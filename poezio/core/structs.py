"""
Module defining structures useful to the core class and related methods
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, List, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from poezio import windows

__all__ = [
    'Command',
    'Completion',
    'POSSIBLE_SHOW',
    'Status',
]

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
    comp: Optional[Callable[['windows.Input'], Completion]]
    short_desc: str
    usage: str
