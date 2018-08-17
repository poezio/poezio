"""
Standalone functions used by the modules
"""

import string
from typing import Optional, List
from poezio.windows.base_wins import FORMAT_CHAR, format_chars

DIGITS = string.digits + '-'


def find_first_format_char(text: str,
                           chars: Optional[List[str]] = None) -> int:
    to_find = chars or format_chars
    pos = -1
    for char in to_find:
        p = text.find(char)
        if p == -1:
            continue
        if pos == -1 or p < pos:
            pos = p
    return pos


def truncate_nick(nick: str, size=10) -> str:
    if size < 1:
        size = 1
    if nick and len(nick) > size:
        return nick[:size] + '…'
    return nick


def parse_attrs(text: str, previous: Optional[List[str]] = None) -> List[str]:
    next_attr_char = text.find(FORMAT_CHAR)
    if previous:
        attrs = previous
    else:
        attrs = []
    while next_attr_char != -1 and text:
        if next_attr_char + 1 < len(text):
            attr_char = text[next_attr_char + 1].lower()
        else:
            attr_char = '\0'
        if attr_char == 'o':
            attrs = []
        elif attr_char == 'u':
            attrs.append('u')
        elif attr_char == 'b':
            attrs.append('b')
        elif attr_char == 'i':
            attrs.append('i')
        if attr_char in DIGITS and attr_char:
            color_str = text[next_attr_char + 1:text.find('}', next_attr_char)]
            if color_str:
                attrs.append(color_str + '}')
            text = text[next_attr_char + len(color_str) + 2:]
        else:
            text = text[next_attr_char + 2:]
        next_attr_char = text.find(FORMAT_CHAR)
    return attrs
