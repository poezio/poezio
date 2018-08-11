"""
Tabs management module

Provide a class holding the current tabs of the application.
Supported list modification operations:
    - Appending a tab
    - Deleting a tab (and going back to the previous one)
    - Inserting a tab from a position to another
    - Replacing the whole tab list with another (used for rearranging the
      list from outside)

This class holds a cursor to the current tab, which allows:
    - Going left (prev()) or right (next()) in the list, cycling
    - Getting a reference to the current tab
    - Setting the current tab by index or reference

It supports the poezio "gap tab" concept, aka empty tabs taking a space in the
tab list in order to avoid shifting the tab numbers when closing a tab.
Example tab list: [0|1|2|3|4]
We then close the tab 3: [0|1|2|4]
The tab has been closed and replaced with a "gap tab", which the user cannot
switch to, but which avoids shifting numbers (in the case above, the list would
have become [0|1|2|3], with the tab "4" renumbered to "3" if gap tabs are
disabled.
"""

from typing import List, Dict, Type, Optional, Union
from collections import defaultdict
from poezio import tabs
from poezio.events import EventHandler


class Tabs:
    """
    Tab list class
    """
    __slots__ = [
        '_current_index',
        '_current_tab',
        '_tabs',
        '_tab_types',
        '_tab_names',
        '_previous_tab',
        '_events',
    ]

    def __init__(self, events: EventHandler):
        """
        Initialize the Tab List. Even though the list is initially
        empty, all methods are only valid once append() has been called
        once. Otherwise, mayhem is expected.
        """
        # cursor
        self._current_index = 0  # type: int
        self._current_tab = None  # type: Optional[tabs.Tab]

        self._previous_tab = None  # type: Optional[tabs.Tab]
        self._tabs = []  # type: List[tabs.Tab]
        self._tab_types = defaultdict(
            list)  # type: Dict[Type[tabs.Tab], List[tabs.Tab]]
        self._tab_names = dict()  # type: Dict[str, tabs.Tab]
        self._events = events  # type: EventHandler

    def __len__(self):
        return len(self._tabs)

    def __iter__(self):
        return iter(self._tabs)

    def __getitem__(self, index: Union[int, str]):
        if isinstance(index, int):
            return self._tabs[index]
        return self.by_name(index)

    def first(self) -> tabs.Tab:
        """Return the Roster tab"""
        return self._tabs[0]

    @property
    def current_index(self) -> int:
        """Current tab index"""
        return self._current_index

    def set_current_index(self, value: int) -> bool:
        """Set the current tab index"""
        if 0 <= value < len(self._tabs):
            tab = self._tabs[value]
            return self.set_current_tab(tab)
        return False

    @property
    def current_tab(self) -> Optional[tabs.Tab]:
        """Current tab"""
        return self._current_tab

    def set_current_tab(self, tab: tabs.Tab) -> bool:
        """Set the current tab"""
        if (not isinstance(tab, tabs.GapTab)
                and 0 <= tab.nb < len(self._tabs)):
            self._store_previous()
            self._current_index = tab.nb
            self._current_tab = tab
            self._events.trigger(
                'tab_change',
                old_tab=self._previous_tab,
                new_tab=self._current_tab)
            return True
        return False

    def get_tabs(self) -> List[tabs.Tab]:
        """Return the tab list"""
        return self._tabs

    def by_name(self, name: str) -> tabs.Tab:
        """Get a tab with a specific name"""
        return self._tab_names.get(name)

    def by_class(self, cls: Type[tabs.Tab]) -> List[tabs.Tab]:
        """Get all the tabs of a class"""
        return self._tab_types.get(cls, [])

    def find_match(self, name: str) -> Optional[tabs.Tab]:
        """Get a tab using extended matching (tab.matching_name())"""

        def transform(tab_index):
            """Wrap the value of the range around the current index"""
            return (tab_index + self._current_index + 1) % len(self._tabs)

        for i in map(transform, range(len(self._tabs) - 1)):
            for tab_name in self._tabs[i].matching_names():
                if tab_name[1] and name in tab_name[1].lower():
                    return self._tabs[i]
        return None

    def by_name_and_class(self, name: str,
                          cls: Type[tabs.Tab]) -> Optional[tabs.Tab]:
        """Get a tab with its name and class"""
        cls_tabs = self._tab_types.get(cls, [])
        for tab in cls_tabs:
            if tab.name == name:
                return tab
        return None

    def _rebuild(self):
        self._tab_types = defaultdict(list)
        self._tab_names = dict()
        for tab in self._tabs:
            for cls in _get_tab_types(tab):
                self._tab_types[cls].append(tab)
            self._tab_names[tab.name] = tab
        self._update_numbers()

    def replace_tabs(self, new_tabs: List[tabs.Tab]) -> bool:
        """
        Replace the current tab list with another, and
        rebuild the mappings.
        """
        if self._current_tab not in new_tabs:
            return False
        self._tabs = new_tabs
        self._rebuild()
        return True

    def _inc_cursor(self):
        self._current_index = (self._current_index + 1) % len(self._tabs)
        self._current_tab = self._tabs[self._current_index]

    def _dec_cursor(self):
        self._current_index = (self._current_index - 1) % len(self._tabs)
        self._current_tab = self._tabs[self._current_index]

    def _store_previous(self):
        self._previous_tab = self._current_tab

    def next(self):
        """Go to the right of the tab list (circular)"""
        self._store_previous()
        self._inc_cursor()
        while isinstance(self.current_tab, tabs.GapTab):
            self._inc_cursor()
        self._events.trigger(
            'tab_change',
            old_tab=self._previous_tab,
            new_tab=self._current_tab)

    def prev(self):
        """Go to the left of the tab list (circular)"""
        self._store_previous()
        self._dec_cursor()
        while isinstance(self.current_tab, tabs.GapTab):
            self._dec_cursor()
        self._events.trigger(
            'tab_change',
            old_tab=self._previous_tab,
            new_tab=self._current_tab)

    def append(self, tab: tabs.Tab):
        """
        Add a tab to the list
        """
        if not self._tabs:
            tab.nb = 0
            self._current_tab = tab
        else:
            tab.nb = self._tabs[-1].nb + 1
        self._tabs.append(tab)
        for cls in _get_tab_types(tab):
            self._tab_types[cls].append(tab)
        self._tab_names[tab.name] = tab

    def delete(self, tab: tabs.Tab, gap=False):
        """Remove a tab"""
        if isinstance(tab, tabs.RosterInfoTab):
            return

        if gap:
            self._tabs[tab.nb] = tabs.GapTab(None)
        else:
            self._tabs.remove(tab)

        is_current = tab is self.current_tab

        for cls in _get_tab_types(tab):
            self._tab_types[cls].remove(tab)
        del self._tab_names[tab.name]

        if gap:
            self._collect_trailing_gaptabs()
        else:
            self._update_numbers()

        if tab is self._previous_tab:
            self._previous_tab = None
        if is_current:
            self.restore_previous_tab()
        self._validate_current_index()

    def restore_previous_tab(self):
        """Restore the previous tab"""

        if self._previous_tab:
            if not self.set_current_tab(self._previous_tab):
                self.set_current_index(0)
        else:
            self.set_current_index(0)

    def _validate_current_index(self):
        if not 0 <= self._current_index < len(
                self._tabs) or not self.current_tab:
            self.prev()

    def _collect_trailing_gaptabs(self):
        """Remove trailing gap tabs if any"""
        i = len(self._tabs) - 1
        while isinstance(self._tabs[i], tabs.GapTab):
            self._tabs.pop()
            i -= 1

    def _update_numbers(self):
        for i, tab in enumerate(self._tabs):
            tab.nb = i
        self._current_index = self._current_tab.nb

    # Moving tabs around #

    def update_gaps(self, enable_gaps: bool):
        """
        Remove the present gaps from the list if enable_gaps is False.
        """
        if not enable_gaps:
            self._tabs = [tab for tab in self._tabs if tab]
            self._update_numbers()

    def _insert_nogaps(self, old_pos: int, new_pos: int) -> bool:
        """
        Move tabs without creating gaps
        old_pos: old position of the tab
        new_pos: desired position of the tab
        """
        tab = self._tabs[old_pos]
        if new_pos < old_pos:
            self._tabs.pop(old_pos)
            self._tabs.insert(new_pos, tab)
        elif new_pos > old_pos:
            self._tabs.insert(new_pos, tab)
            self._tabs.remove(tab)
        else:
            return False
        return True

    def _insert_gaps(self, old_pos: int, new_pos: int) -> bool:
        """
        Move tabs and create gaps in the eventual remaining space
        old_pos: old position of the tab
        new_pos: desired position of the tab
        """
        tab = self._tabs[old_pos]
        target = None if new_pos >= len(self._tabs) else self._tabs[new_pos]
        if not target:
            if new_pos < len(self._tabs):
                old_tab = self._tabs[old_pos]
                self._tabs[new_pos], self._tabs[
                    old_pos] = old_tab, tabs.GapTab(self)
            else:
                self._tabs.append(self._tabs[old_pos])
                self._tabs[old_pos] = tabs.GapTab(self)
        else:
            if new_pos > old_pos:
                self._tabs.insert(new_pos, tab)
                self._tabs[old_pos] = tabs.GapTab(self)
            elif new_pos < old_pos:
                self._tabs[old_pos] = tabs.GapTab(self)
                self._tabs.insert(new_pos, tab)
            else:
                return False
            i = self._tabs.index(tab)
            done = False
            # Remove the first Gap on the right in the list
            # in order to prevent global shifts when there is empty space
            while not done:
                i += 1
                if i >= len(self._tabs):
                    done = True
                elif not self._tabs[i]:
                    self._tabs.pop(i)
                    done = True
        self._collect_trailing_gaptabs()
        return True

    def insert_tab(self, old_pos: int, new_pos=99999, gaps=False) -> bool:
        """
        Insert a tab at a position, changing the number of the following tabs
        returns False if it could not move the tab, True otherwise
        """
        if (old_pos <= 0 or old_pos >= len(self._tabs) or new_pos <= 0
                or new_pos == old_pos or not self._tabs[old_pos]):
            return False
        if gaps:
            result = self._insert_gaps(old_pos, new_pos)
        else:
            result = self._insert_nogaps(old_pos, new_pos)
        self._update_numbers()
        return result


def _get_tab_types(tab: tabs.Tab) -> List[Type[tabs.Tab]]:
    """Return all parent classes of a tab type"""
    types = []
    current_cls = tab.__class__
    while current_cls != tabs.Tab:
        types.append(current_cls)
        current_cls = current_cls.__bases__[0]
    return types
