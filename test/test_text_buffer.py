"""
Tests for the TextBuffer class
"""
from pytest import fixture

from poezio.text_buffer import (
    TextBuffer,
    HistoryGap,
)

from poezio.ui.types import (
    Message,
    BaseMessage,
    MucOwnJoinMessage,
    MucOwnLeaveMessage,
)


@fixture(scope='function')
def buf2048():
    return TextBuffer(2048)

@fixture(scope='function')
def msgs_nojoin():
    msg1 = Message('1', 'q')
    msg2 = Message('2', 's')
    leave = MucOwnLeaveMessage('leave')
    return [msg1, msg2, leave]


@fixture(scope='function')
def msgs_noleave():
    join = MucOwnJoinMessage('join')
    msg3 = Message('3', 'd')
    msg4 = Message('4', 'f')
    return [join, msg3, msg4]

@fixture(scope='function')
def msgs_doublejoin():
    join = MucOwnJoinMessage('join')
    msg1 = Message('1', 'd')
    msg2 = Message('2', 'f')
    join2 = MucOwnJoinMessage('join')
    return [join, msg1, msg2, join2]

def test_last_message(buf2048):
    msg = BaseMessage('toto')
    buf2048.add_message(BaseMessage('titi'))
    buf2048.add_message(msg)
    assert buf2048.last_message is msg


def test_message_nb_limit():
    buf = TextBuffer(5)
    for i in range(10):
        buf.add_message(BaseMessage("%s" % i))
    assert len(buf.messages) == 5


def test_find_gap(buf2048, msgs_noleave):
    msg1 = Message('1', 'q')
    msg2 = Message('2', 's')
    leave = MucOwnLeaveMessage('leave')
    join = MucOwnJoinMessage('join')
    msg3 = Message('3', 'd')
    msg4 = Message('4', 'f')
    msgs = [msg1, msg2, leave, join, msg3, msg4]
    for msg in msgs:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert gap.leave_message == leave
    assert gap.join_message == join
    assert gap.last_timestamp_before_leave == msg2.time
    assert gap.first_timestamp_after_join == msg3.time


def test_find_gap_doublejoin(buf2048, msgs_doublejoin):
    for msg in msgs_doublejoin:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert gap.leave_message == msgs_doublejoin[2]
    assert gap.join_message == msgs_doublejoin[3]


def test_find_gap_doublejoin_no_msg(buf2048):
    join1 = MucOwnJoinMessage('join')
    join2 = MucOwnJoinMessage('join')
    for msg in [join1, join2]:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert gap.leave_message is join1
    assert gap.join_message is join2


def test_find_gap_already_filled(buf2048):
    msg1 = Message('1', 'q')
    msg2 = Message('2', 's')
    leave = MucOwnLeaveMessage('leave')
    msg5 = Message('5', 'g')
    msg6 = Message('6', 'h')
    join = MucOwnJoinMessage('join')
    msg3 = Message('3', 'd')
    msg4 = Message('4', 'f')
    msgs = [msg1, msg2, leave, msg5, msg6, join, msg3, msg4]
    for msg in msgs:
        buf2048.add_message(msg)
    assert buf2048.find_last_gap_muc() is None


def test_find_gap_noleave(buf2048, msgs_noleave):
    for msg in msgs_noleave:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert gap.leave_message is None
    assert gap.last_timestamp_before_leave is None
    assert gap.join_message == msgs_noleave[0]
    assert gap.first_timestamp_after_join == msgs_noleave[1].time


def test_find_gap_nojoin(buf2048, msgs_nojoin):
    for msg in msgs_nojoin:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert gap.leave_message == msgs_nojoin[-1]
    assert gap.join_message is None
    assert gap.last_timestamp_before_leave == msgs_nojoin[1].time


def test_get_gap_index(buf2048):
    msg1 = Message('1', 'q')
    msg2 = Message('2', 's')
    leave = MucOwnLeaveMessage('leave')
    join = MucOwnJoinMessage('join')
    msg3 = Message('3', 'd')
    msg4 = Message('4', 'f')
    msgs = [msg1, msg2, leave, join, msg3, msg4]
    for msg in msgs:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert buf2048.get_gap_index(gap) == 3


def test_get_gap_index_doublejoin(buf2048, msgs_doublejoin):
    for msg in msgs_doublejoin:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert buf2048.get_gap_index(gap) == 3


def test_get_gap_index_doublejoin_no_msg(buf2048):
    join1 = MucOwnJoinMessage('join')
    join2 = MucOwnJoinMessage('join')
    for msg in [join1, join2]:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert buf2048.get_gap_index(gap) == 1


def test_get_gap_index_nojoin(buf2048, msgs_nojoin):
    for msg in msgs_nojoin:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert buf2048.get_gap_index(gap) == 3


def test_get_gap_index_noleave(buf2048, msgs_noleave):
    for msg in msgs_noleave:
        buf2048.add_message(msg)
    gap = buf2048.find_last_gap_muc()
    assert buf2048.get_gap_index(gap) == 0


def test_add_history_messages(buf2048):
    msg1 = Message('1', 'q')
    msg2 = Message('2', 's')
    leave = MucOwnLeaveMessage('leave')
    join = MucOwnJoinMessage('join')
    msg3 = Message('3', 'd')
    msg4 = Message('4', 'f')
    msgs = [msg1, msg2, leave, join, msg3, msg4]
    for msg in msgs:
        buf2048.add_message(msg)
    msg5 = Message('5', 'g')
    msg6 = Message('6', 'h')
    gap = buf2048.find_last_gap_muc()
    buf2048.add_history_messages([msg5, msg6], gap=gap)
    assert buf2048.messages == [msg1, msg2, leave, msg5, msg6, join, msg3, msg4]


def test_add_history_empty(buf2048):
    msg1 = Message('1', 'q')
    msg2 = Message('2', 's')
    msg3 = Message('3', 'd')
    msg4 = Message('4', 'f')
    buf2048.add_message(msg1)
    buf2048.add_history_messages([msg2, msg3, msg4])
    assert buf2048.messages == [msg2, msg3, msg4, msg1]

