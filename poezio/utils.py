#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Utilities
"""

from random import choice

VOWELS = 'aiueo'
CONSONANTS = 'bcdfghjklmnpqrstvwxz'


def pronounceable(length: int = 6) -> str:
    """Generates a pronounceable name"""
    out = ''
    vowels = choice((True, False))
    for _ in range(0, length):
        out += choice(VOWELS if vowels else CONSONANTS)
        vowels = not vowels
    return out
