"""
Test the functions in the `theming` module
"""

import pytest

from poezio.theming import dump_tuple, read_tuple

def test_read_tuple():
    assert read_tuple('1,-1,u') == ((1, -1), 'u')
    assert read_tuple('1,2') == ((1, 2), '\0')

    with pytest.raises(IndexError):
        read_tuple('1')

    with pytest.raises(ValueError):
        read_tuple('toto')

def test_dump_tuple():
    assert dump_tuple((1, 2)) == '1,2'
    assert dump_tuple((1, )) == '1'
    assert dump_tuple((1, 2, 'u')) == '1,2,u'


