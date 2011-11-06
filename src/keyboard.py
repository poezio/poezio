# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Functions to interact with the keyboard
Mainly, read keys entered and return a string (most
of the time ONE char, but may be longer if it's a keyboard
shortcut, like ^A, M-a or KEY_RESIZE)
"""

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

def read_char(s, timeout=1000):
    """
    Read one utf-8 char
    see http://en.wikipedia.org/wiki/UTF-8#Description
    """
    s.timeout(timeout) # The timeout for timed events to be checked every second
    ret_list = []
    # The list of all chars. For example if you paste a text, the list the chars pasted
    # so that they can be handled at once.
    (first, char) = get_next_byte(s)
    while first is not None or char is not None:
        if not isinstance(first, int): # Keyboard special, like KEY_HOME etc
            return [char]
        if first == 127 or first == 8:
            return ["KEY_BACKSPACE"]
        s.timeout(0)            # we are now getting the missing utf-8 bytes to get a whole char
        if first < 127:  # ASCII char on one byte
            if first <= 26:         # transform Ctrl+* keys
                char = chr(first + 64)
                ret_list.append("^"+char)
                (first, char) = get_next_byte(s)
                continue
            if first == 27:
                second = read_char(s, 0)
                if second is None: # if escape was pressed, a second char
                                   # has to be read. But it timed out.
                    return None
                res = 'M-%s' % (second[0],)
                ret_list.append(res)
                (first, char) = get_next_byte(s)
                continue
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
            ret_list.append(char.decode('utf-8')) # return all the concatened byte objets, decoded
        except UnicodeDecodeError:
            return None
        # s.timeout(1)            # timeout to detect a paste of many chars
        (first, char) = get_next_byte(s)
    if not ret_list:
        # nothing at all was read, that’s a timed event timeout
        return None
    if len(ret_list) != 1:
        if ret_list[-1] == '^M':
            ret_list.pop(-1)
        return [char if char != '^M' else '^J' for char in ret_list]
    return ret_list

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
