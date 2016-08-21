"""
Test of the poopt module
"""

import pytest

from poezio.poopt import cut_text

def test_cut_text():

    text = '12345678901234567890'
    assert cut_text(text, 5) == [(0, 5), (5, 10), (10, 15), (15, 20)]
