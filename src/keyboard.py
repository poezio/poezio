# -*- coding: utf-8 -*-
# Copyright 2010-2011 Le Coz Florent <louiz@louiz.org>
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

import time

last_timeout = time.time()

def get_next_byte(s):
    """
    Read the next byte of the utf-8 char
    ncurses seems to return a string of the byte
    encoded in latin-1. So what we get is NOT what we typed
    unless we do the conversion…
    """
    try:
        c = s.getkey()
    except:
        return (None, None)
    if len(c) >= 4:
        return (None, c)
    return (ord(c), c.encode('latin-1')) # returns a number and a bytes object

def read_char(s):
    """
    Read one utf-8 char
    see http://en.wikipedia.org/wiki/UTF-8#Description
    """
    global last_timeout
    s.timeout(1000)
    (first, char) = get_next_byte(s)
    if first is None and char is None:
        last_timeout = time.time()
        return None
    if not isinstance(first, int): # Keyboard special, like KEY_HOME etc
        return char
    if first == 127 or first == 8:
        return "KEY_BACKSPACE"
    if first < 127:  # ASCII char on one byte
        if first <= 26:         # transform Ctrl+* keys
            char = chr(first + 64)
            # if char == 'M' and time.time() - last_char_time < 0.0005:
            #     char = 'J'
            return  "^"+char
        if first == 27:
            second = read_char(s)
            res = 'M-%s' % (second,)
            return res
    if 194 <= first:
        (code, c) = get_next_byte(s) # 2 bytes char
        char += c
    if 224 <= first:
        (code, c) = get_next_byte(s) # 3 bytes char
        char += c
    if 240 <= first:
        (code, c) = get_next_byte(s) # 4 bytes char
        char += c
    try:
        return char.decode('utf-8') # return all the concatened byte objets, decoded
    except UnicodeDecodeError:
        return None

if __name__ == '__main__':
    import curses
    s = curses.initscr()
    curses.curs_set(1)
    curses.noecho()
    curses.nonl()
    s.keypad(True)
    curses.noecho()
    while True:
        s.addstr('%s\n' % read_char(s))
