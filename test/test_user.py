"""
Tests for the User class
"""

import pytest
from datetime import datetime
from slixmpp import JID
from poezio.user import User


@pytest.fixture
def user1():
    return User(
        nick='nick1',
        affiliation='member',
        show='xa',
        status='My Status!',
        role='moderator',
        jid=JID('foo@muc/nick1'),
        color='red',
    )


def test_new_user(user1):
    assert user1.last_talked == datetime(1, 1, 1)
    assert user1.jid == JID('foo@muc/nick1')
    assert user1.chatstate is None
    assert user1.affiliation == 'member'
    assert user1.show == 'xa'
    assert user1.status == 'My Status!'
    assert user1.role == 'moderator'
    assert user1.nick == 'nick1'
    assert user1.color == (196, -1)
    assert str(user1) == '>nick1<'


def test_change_nick(user1):
    user1.change_nick('nick2')
    assert user1.nick == 'nick2'


def test_change_color(user1):
    user1.change_color('blue')
    assert user1.color == (21, -1)
