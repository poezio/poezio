"""
Tests for the Tabs list module
"""

from poezio.core.tabs import Tabs
from poezio.tabs import GapTab, Tab
from poezio.events import EventHandler

h = EventHandler()

class DummyTab(Tab):
    count = 0

    def __init__(self):
        self.name = 'dummy%s' % self.count
        DummyTab.count += 1

    @staticmethod
    def reset():
        DummyTab.count = 0

def test_append():
    DummyTab.reset()
    tabs = Tabs(h)
    dummy = DummyTab()
    tabs.append(dummy)
    assert tabs[0] is dummy
    assert tabs[0].nb == 0
    assert tabs['dummy0'] is dummy
    assert tabs.by_class(DummyTab) == [dummy]

    dummy2 = DummyTab()
    tabs.append(dummy2)
    assert tabs[1] is dummy2
    assert tabs[1].nb == 1
    assert tabs['dummy1'] is dummy2
    assert tabs.by_class(DummyTab) == [dummy, dummy2]

def test_delete():
    DummyTab.reset()
    tabs = Tabs(h)
    dummy = DummyTab()
    dummy2 = DummyTab()
    tabs.append(dummy)
    tabs.append(dummy2)

    tabs.delete(dummy)
    assert tabs[0] is dummy2
    assert tabs.by_class(DummyTab) == [dummy2]
    assert tabs['dummy0'] is None
    assert dummy2.nb == 0


def test_delete_restore_previous():
    DummyTab.reset()
    tabs = Tabs(h)
    dummy = DummyTab()
    dummy2 = DummyTab()
    dummy3 = DummyTab()
    dummy4 = DummyTab()
    tabs.append(dummy)
    tabs.append(dummy2)
    tabs.append(dummy3)
    tabs.append(dummy4)

    tabs.set_current_tab(dummy4)
    tabs.set_current_tab(dummy2)
    tabs.delete(dummy2)
    assert tabs.current_tab is dummy4
    assert tabs.current_index == 2
    assert dummy.nb == 0
    assert dummy3.nb == 1
    assert dummy4.nb == 2

def test_delete_other_tab():
    DummyTab.reset()
    tabs = Tabs(h)
    dummy = DummyTab()
    dummy2 = DummyTab()
    dummy3 = DummyTab()
    dummy4 = DummyTab()
    tabs.append(dummy)
    tabs.append(dummy2)
    tabs.append(dummy3)
    tabs.append(dummy4)

    tabs.set_current_tab(dummy4)
    tabs.delete(dummy2)
    assert tabs.current_tab is dummy4
    assert tabs.current_index == 2
    assert dummy.nb == 0
    assert dummy3.nb == 1
    assert dummy4.nb == 2

def test_insert_and_gaps():
    DummyTab.reset()
    tabs = Tabs(h)
    dummy = DummyTab()
    dummy2 = DummyTab()
    dummy3 = DummyTab()
    tabs.append(dummy)
    tabs.append(dummy2)
    tabs.append(dummy3)

    tabs.insert_tab(2, 1)
    assert tabs[1] is dummy3
    assert tabs[2] is dummy2

    tabs.insert_tab(1, 100, gaps=True)
    assert isinstance(tabs[1], GapTab)
    assert tabs[3] is dummy3
    assert tabs[3].nb == 3

    tabs.update_gaps(enable_gaps=False)
    assert tabs[1] is dummy2
    assert tabs[1].nb == 1

def test_replace_tabs():
    DummyTab.reset()
    tabs = Tabs(h)
    dummy = DummyTab()
    dummy2 = DummyTab()
    dummy3 = DummyTab()
    tabs.append(dummy)
    tabs.append(dummy2)
    tabs.append(dummy3)

    tabs.replace_tabs([dummy3, dummy2, dummy])
    assert tabs[0] is dummy3
    assert tabs[2] is dummy
    assert tabs[2].nb == 2

def test_prev_next():
    DummyTab.reset()
    tabs = Tabs(h)
    dummy = DummyTab()
    dummy2 = DummyTab()
    dummy3 = DummyTab()
    tabs.append(dummy)
    tabs.append(dummy2)
    tabs.append(dummy3)

    for idx in range(6):
        assert tabs.current_index == idx % 3
        tabs.next()

    for idx in range(6):
        assert (3 - idx) % 3 == tabs.current_index
        tabs.prev()

    tabs.insert_tab(1, 999, gaps=True)

    assert tabs.current_index == 0
    tabs.next()
    assert tabs.current_index == 2
    tabs.prev()
    assert tabs.current_index == 0

def test_set_current():
    DummyTab.reset()
    tabs = Tabs(h)
    dummy = DummyTab()
    dummy2 = DummyTab()
    dummy3 = DummyTab()
    tabs.append(dummy)
    tabs.append(dummy2)
    tabs.append(dummy3)

    assert tabs.current_tab is dummy
    tabs.set_current_index(2)
    assert tabs.current_tab is dummy3
    tabs.set_current_tab(dummy2)
    assert tabs.current_tab is dummy2

def test_slice():
    DummyTab.reset()
    tabs = Tabs(h)
    dummy = DummyTab()
    dummy2 = DummyTab()
    dummy3 = DummyTab()
    tabs.append(dummy)
    tabs.append(dummy2)
    tabs.append(dummy3)

    assert tabs[1:2][0] is dummy2

def test_find_by_unique_prefix():
    DummyTab.reset()
    tabs = Tabs(h)
    t1 = DummyTab()
    t2 = DummyTab()
    t3 = DummyTab()
    tabs.append(t1)
    tabs.append(t2)
    tabs.append(t3)

    t1.name = "foo"
    t2.name = "bar"
    t3.name = "fnord"

    assert tabs.find_by_unique_prefix("f") == (True, None)
    assert tabs.find_by_unique_prefix("b") == (True, t2)
    assert tabs.find_by_unique_prefix("fo") == (True, t1)
    assert tabs.find_by_unique_prefix("fn") == (True, t3)
    assert tabs.find_by_unique_prefix("fx") == (False, None)
    assert tabs.find_by_unique_prefix("x") == (False, None)
    assert tabs.find_by_unique_prefix("") == (True, None)
