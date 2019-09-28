import pytest
from datetime import datetime

from poezio.ui.types import BaseMessage, Message, XMLLog


def test_create_message():
    now = datetime.now()
    msg = Message(
        txt="coucou",
        nickname="toto",
    )
    assert now < msg.time < datetime.now()

    msg = Message(
        txt="coucou",
        nickname="toto",
        time=now,
    )
    assert msg.time == now


def test_message_offset_simple():
    msg = Message(
        txt="coucou",
        nickname="toto",
    )
    example = "10:10:10 toto> "
    assert msg.compute_offset(True, 10) == len(example)

    msg = Message(
        txt="coucou",
        nickname="toto",
        history=True,
    )
    example = "2019:09:01 10:10:10 toto> "
    assert msg.compute_offset(True, 10) == len(example)

def test_message_offset_no_nick():
    msg = Message(
        txt="coucou",
        nickname="",
    )
    example = "10:10:10 "
    assert msg.compute_offset(True, 10) == len(example)

def test_message_offset_ack():
    msg = Message(
        txt="coucou",
        nickname="toto",
        ack=1,
    )
    example = "10:10:10 V toto> "
    assert msg.compute_offset(True, 10) == len(example)

    msg = Message(
        txt="coucou",
        nickname="toto",
        ack=-1,
    )
    example = "10:10:10 X toto> "
    assert msg.compute_offset(True, 10) == len(example)


def test_message_offset_me():
    msg = Message(
        txt="/me coucou",
        nickname="toto",
    )
    example = "10:10:10 * toto "
    assert msg.compute_offset(True, 10) == len(example)


def test_message_offset_revisions():
    msg = Message(
        txt="coucou",
        nickname="toto",
        revisions=3,
    )
    example = "10:10:10 toto3> "
    assert msg.compute_offset(True, 10) == len(example)

    msg = Message(
        txt="coucou",
        nickname="toto",
        revisions=250,
    )
    example = "10:10:10 toto250> "
    assert msg.compute_offset(True, 10) == len(example)


def test_message_repr_works():
    msg1 = Message(
        txt="coucou",
        nickname="toto",
        revisions=250,
    )
    msg2 = Message(
        txt="coucou",
        nickname="toto",
        old_message=msg1
    )

    assert repr(msg2) is not None

def test_xmllog_offset():
    msg = XMLLog(
        txt='toto',
        incoming=True,
    )
    example = '10:10:10 IN  '
    assert msg.compute_offset(True, 10) == len(example)

    msg = XMLLog(
        txt='toto',
        incoming=False,
    )
    example = '10:10:10 OUT '
    assert msg.compute_offset(True, 10) == len(example)

def test_basemessage_offset():
    msg = BaseMessage(
        txt='coucou',
    )
    example = '10:10:10 '
    assert msg.compute_offset(True, 10) == len(example)
