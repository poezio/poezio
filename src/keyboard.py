# -*- coding:utf-8 -*-
#
# Copyright 2010 Le Coz Florent <louizatakk@fedoraproject.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

"""
Functions to interact with the keyboard
Mainly, read keys entered and return a string (most
of the time ONE char, but may be longer if it's a keyboard
shortcut, like ^A, M-a or KEY_RESIZE)
"""

from common import debug

def get_next_byte(s):
    """
    Read the next byte of the utf-8 char
    """
    try:
        c = s.getkey()
    except:
        return (None, "KEY_RESIZE")
    if len(c) >= 4:
        return (None, c)
    return (ord(c), c)

def read_char(s):
    """
    Read one utf-8 char
    see http://en.wikipedia.org/wiki/UTF-8#Description
    """
    (first, char) = get_next_byte(s)
    if first == None: # Keyboard special, like KEY_HOME etc
        return char
    if first == 127 or first == 8:
        return "KEY_BACKSPACE"
    if first < 127:  # ASCII char on one byte
        if first <= 26:         # transform Ctrl+* keys
            char =  "^"+chr(first + 64)
        if first == 27:
            (first, c) = get_next_byte(s)
            char = "M-"+c
    if 194 <= first:
        debug('1\n')
        (code, c) = get_next_byte(s) # 2 bytes char
        char += c
    if 224 <= first:
        debug('2\n')
        (code, c) = get_next_byte(s) # 3 bytes char
        char += c
    if 240 <= first:
        debug('3\n')
        (code, c) = get_next_byte(s) # 4 bytes char
        char += c
    return char
