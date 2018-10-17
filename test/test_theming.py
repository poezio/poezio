"""
Test the functions in the `theming` module
"""

import pytest

from poezio.theming import dump_tuple

def test_dump_tuple():
    assert dump_tuple((1, 2)) == '1,2'
    assert dump_tuple((1, )) == '1'
    assert dump_tuple((1, 2, 'u')) == '1,2,u'


