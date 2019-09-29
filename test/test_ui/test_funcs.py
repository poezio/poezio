from poezio.ui.funcs import (
    find_first_format_char,
    parse_attrs,
    truncate_nick,
)


def test_find_char_not_present():
    assert find_first_format_char("toto") == -1


def test_find_char():
    assert find_first_format_char('a \x1A 1') == 2


def test_truncate_nick():
    assert truncate_nick("toto") == "toto"


def test_truncate_nick_wrong_size():
    assert truncate_nick("toto", -10) == "t…"


def test_truncate_nick_too_long():
    nick = "012345678901234567"
    assert truncate_nick(nick) == nick[:10] + "…"


def test_truncate_nick_no_nick():
    assert truncate_nick('') == ''


def test_parse_attrs():
    text = "\x19o\x19u\x19b\x19i\x191}\x19o\x194}"
    assert parse_attrs(text) == ['4}']


def test_parse_attrs_broken_char():
    text = "coucou\x19"
    assert parse_attrs(text) == []


def test_parse_attrs_previous():
    text = "coucou"
    previous = ['u']
    assert parse_attrs(text, previous=previous) == previous
