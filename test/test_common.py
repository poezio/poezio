"""
Test the functions in the `common` module
"""

import time
import pytest
import datetime
from slixmpp import JID
from datetime import timedelta
from poezio.common import (_datetime_tuple as datetime_tuple, get_utc_time,
                           get_local_time, shell_split, _find_argument_quoted
                           as find_argument_quoted, _find_argument_unquoted as
                           find_argument_unquoted, parse_str_to_secs,
                           parse_secs_to_str, safeJID, unique_prefix_of)

def test_utc_time():
    delta = timedelta(seconds=-3600)
    d = datetime.datetime.now()
    time.timezone = -3600; time.altzone = -3600
    assert get_utc_time(local_time=d) == d + delta

def test_local_time():
    delta = timedelta(seconds=-3600)
    d = datetime.datetime.now()
    time.timezone = -3600
    time.altzone = -3600
    assert get_local_time(d) == d - delta

def test_shell_split():
    assert shell_split('"sdf 1" "toto 2"') == ['sdf 1', 'toto 2']
    assert shell_split('toto "titi"') == ['toto', 'titi']
    assert shell_split('toto ""') == ['toto', '']
    assert shell_split('to"to titi "a" b') == ['to"to', 'titi', 'a', 'b']
    assert shell_split('"toto titi" toto ""') == ['toto titi', 'toto', '']
    assert shell_split('toto "titi') == ['toto', 'titi']

def test_argument_quoted():
    assert find_argument_quoted(4, 'toto titi tata') == 3
    assert find_argument_quoted(4, '"toto titi" tata') == 0
    assert find_argument_quoted(8, '"toto" "titi tata"') == 1
    assert find_argument_quoted(8, '"toto" "titi tata') == 1
    assert find_argument_quoted(3, '"toto" "titi tata') == 0
    assert find_argument_quoted(18, '"toto" "titi tata" ') == 2

def test_argument_unquoted():
    assert find_argument_unquoted(2, 'toto titi tata') == 0
    assert find_argument_unquoted(3, 'toto titi tata') == 0
    assert find_argument_unquoted(6, 'toto titi tata') == 1
    assert find_argument_unquoted(4, 'toto titi tata') == 3
    assert find_argument_unquoted(25, 'toto titi tata') == 3

def test_parse_str_to_secs():
    assert parse_str_to_secs("1d3m1h") == 90180
    assert parse_str_to_secs("1d3mfaiiiiil") == 0

def test_parse_secs_to_str():
    assert parse_secs_to_str(3601) == '1h1s'
    assert parse_secs_to_str(0) == '0s'

    with pytest.raises(TypeError):
        parse_secs_to_str('toto')

def test_safeJID():
    assert safeJID('toto@titi/tata') == JID('toto@titi/tata')
    assert safeJID('toto@…') == JID('')

def test_unique_prefix_of__no_shared_prefix():
    assert unique_prefix_of("a", "b") == "a"
    assert unique_prefix_of("foo", "bar") == "f"
    assert unique_prefix_of("foo", "") == "f"

def test_unique_prefix_of__equal():
    assert unique_prefix_of("foo", "foo") == "foo"

def test_unique_prefix_of__a_prefix():
    assert unique_prefix_of("foo", "foobar") == "foo"

def test_unique_prefix_of__b_prefix():
    assert unique_prefix_of("foobar", "foo") == "foob"

def test_unique_prefix_of__normal_shared_prefix():
    assert unique_prefix_of("foobar", "foobaz") == "foobar"
    assert unique_prefix_of("fnord", "funky") == "fn"
    assert unique_prefix_of("asbestos", "aspergers") == "asb"
