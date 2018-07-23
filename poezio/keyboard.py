#!/usr/bin/env python3
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

import curses
import curses.ascii
import logging
from typing import Callable, List, Optional, Tuple

log = logging.getLogger(__name__)

# A callback that will handle the next key entered by the user. For
# example if the user presses Ctrl+j, we set a callbacks, and the
# next key pressed by the user will be passed to this callback
# instead of the normal process of executing global keybard
# shortcuts or inserting text in the current output.  The callback
# is always reset to None afterwards (to resume the normal
# processing of keys)
continuation_keys_callback = None  # type: Optional[Callable]


def get_next_byte(s) -> Tuple[Optional[int], Optional[bytes]]:
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
    return (ord(c), c.encode('latin-1'))  # returns a number and a bytes object


def get_char_list(s) -> List[str]:
    ret_list = []  # type: List[str]
    while True:
        try:
            key = s.get_wch()
        except curses.error:
            # No input, this means a timeout occurs.
            return ret_list
        except ValueError:  # invalid input
            log.debug('Invalid character entered.')
            return ret_list
        # Set to non-blocking. We try to read more bytes. If there are no
        # more data to read, it will immediately timeout and return with the
        # data we have so far
        s.timeout(0)
        if isinstance(key, int):
            ret_list.append(curses.keyname(key).decode())
        else:
            if curses.ascii.isctrl(key):
                key = curses.unctrl(key).decode()
                # Here special cases for alt keys, where we get a ^[ and then a second char
                if key == '^[':
                    try:
                        part = s.get_wch()
                        if part == '[':
                            # CTRL+arrow and meta+arrow keys have a long format
                            part += s.get_wch() + s.get_wch() + s.get_wch(
                            ) + s.get_wch()
                    except curses.error:
                        pass
                    except ValueError:  # invalid input
                        log.debug('Invalid character entered.')
                    else:
                        key = 'M-%s' % part
                    # and an even more special case for keys like
                    # ctrl+arrows, where we get ^[, then [, then a third
                    # char.
                    if key == 'M-[':
                        try:
                            part = s.get_wch()
                        except curses.error:
                            pass
                        except ValueError:
                            log.debug('Invalid character entered.')
                        else:
                            key = '%s-%s' % (key, part)
            if key == '\x7f' or key == '\x08':
                key = '^?'
            elif key == '\r':
                key = '^M'
            ret_list.append(key)


class Keyboard:
    def __init__(self):
        self.escape = False

    def escape_next_key(self):
        """
        The next key pressed by the user should be escaped. e.g. if the user
        presses ^N, keyboard.get_user_input() will return ["^", "N"] instead
        of ["^N"]. This will display ^N in the input, instead of
        interpreting the key binding.
        """
        self.escape = True

    def get_user_input(self, s) -> List[str]:
        """
        Returns a list of all the available characters to read (for example it
        may contain a whole text if there’s some lag, or the user pasted text,
        or the user types really really fast).  Also it can return None, meaning
        that it’s time to do some other checks (because this function is
        blocking, we need to get out of it every now and then even if nothing
        was entered).
        """
        # Disable the timeout
        s.timeout(-1)
        ret_list = get_char_list(s)
        if not ret_list:
            return ret_list
        if len(ret_list) != 1:
            if ret_list[-1] == '^M':
                ret_list.pop(-1)
            ret_list = [char if char != '^M' else '^J' for char in ret_list]
        if self.escape:
            # Modify the first char of the list into its escaped version (i.e one or more char)
            key = ret_list.pop(0)
            for char in key[::-1]:
                ret_list.insert(0, char)
            self.escape = False
        return ret_list


if __name__ == '__main__':
    import sys
    keyboard = Keyboard()
    s = curses.initscr()
    curses.noecho()
    curses.cbreak()
    s.keypad(1)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, 2, -1)
    s.attron(curses.A_BOLD | curses.color_pair(1))
    s.addstr('Type Ctrl-c to close\n')
    s.attroff(curses.A_BOLD | curses.color_pair(1))

    pressed_chars = []
    while True:

        try:
            chars = keyboard.get_user_input(s)
            for char in chars if chars else '':
                s.addstr('%s ' % (char))
            pressed_chars.append(chars)

        except KeyboardInterrupt:
            break
    curses.echo()
    curses.cbreak()
    curses.curs_set(1)
    curses.endwin()
    for char_list in pressed_chars:
        if char_list:
            print(' '.join((char for char in char_list)), end=' ')
    print()
    sys.exit(0)
