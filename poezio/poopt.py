# Copyright 2017 Emmanuel Gil Peyrot <linkmauve@linkmauve.fr>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.
'''This is a template module just for instruction. And poopt.'''

from typing import List, Tuple

# CFFI codepath.
from cffi import FFI

ffi = FFI()
ffi.cdef("""
    typedef long wchar_t;
    int wcwidth(wchar_t c);
""")
libc = ffi.dlopen(None)

# Cython codepath.
#cdef extern from "wchar.h":
#    ctypedef Py_UCS4 wchar_t
#    int wcwidth(wchar_t c)


# Just checking if the return value is -1.  In some (all?) implementations,
# wcwidth("😆") returns -1 while it should return 2.  In these cases, we
# return 1 instead because this is by far the most probable real value.
# Since the string is received from python, and the unicode character is
# extracted with mbrtowc(), and supposing these two compononents are not
# bugged, and since poezio’s code should never pass '\t', '\n' or their
# friends, a return value of -1 from wcwidth() is considered to be a bug in
# wcwidth() (until proven otherwise). xwcwidth() is here to work around
# this bug.
def xwcwidth(c: str) -> int:
    character = ord(c)
    res = libc.wcwidth(character)
    if res == -1 and c != '\x19':
        return 1
    return res


# cut_text: takes a string and returns a tuple of int.
#
# Each two int tuple is a line, represented by the ending position it
# (where it should be cut).  Not that this position is calculed using the
# position of the python string characters, not just the individual bytes.
#
# For example,
# poopt_cut_text("vivent les réfrigérateurs", 6);
# will return [(0, 6), (7, 10), (11, 17), (17, 22), (22, 24)], meaning that
# the lines are
# "vivent", "les", "réfrig", "érateu" and "rs"
def cut_text(string: str, width: int) -> List[Tuple[int, int]]:
    '''cut_text(text, width)

    Return a list of two-tuple, the first int is the starting position of the line and the second is its end.'''

    # The list of tuples that we return
    retlist = []

    # The start position (in the python-string) of the next line
    #: unsigned int
    start_pos = 0

    # The position of the last space seen in the current line. This is used
    # to cut on spaces instead of cutting inside words, if possible (aka if
    # there is a space)
    #: int
    last_space = -1
    # The number of columns taken by chars between start_pos and last_space
    #: size_t
    cols_until_space = 0

    # Number of columns taken to display the current line so far
    #: size_t
    columns = 0

    #: wchar_t
    #wc = 0

    # The position, considering unicode chars (aka, the position in the
    # python string). This is used to determine the position in the python
    # string at which we should cut */
    #: unsigned int
    #spos = -1

    in_special_character = False
    for spos, wc in enumerate(string):
        # Special case to skip poezio special characters that are contained
        # in the python string, but should not be counted as chars because
        # they will not be displayed. Those are the formatting chars (to
        # insert colors or things like that in the string)
        if in_special_character:
            # Skip everything until the end of this format marker, but
            # without increasing the number of columns of the current
            # line. Because these chars are not printed.
            if wc in ('u', 'a', 'i', 'b', 'o', '}'):
                in_special_character = False
            continue
        if wc == '\x19':
            in_special_character = True
            continue

        # This is one condition to end the line: an explicit \n is found
        if wc == '\n':
            spos += 1
            retlist.append((start_pos, spos))

            # And then initiate a new line
            start_pos = spos
            last_space = -1
            columns = 0
            continue

        # Get the number of columns needed to display this character. May be 0, 1 or 2
        cols = xwcwidth(wc)

        # This is the second condition to end the line: we have consumed
        # enough columns to fill a whole line
        if columns + cols > width:
            # If possible, cut on a space
            if last_space != -1:
                retlist.append((start_pos, last_space))
                start_pos = last_space + 1
                last_space = -1
                columns -= (cols_until_space + 1)
            else:
                # Otherwise, cut in the middle of a word
                retlist.append((start_pos, spos))
                start_pos = spos
                columns = 0
        # We save the position of the last space seen in this line, and the
        # number of columns we have until now. This helps us keep track of
        # the columns to count when we will use that space as a cutting
        # point, later
        if wc == ' ':
            last_space = spos
            cols_until_space = columns
        # We advanced from one char, increment spos by one and add the
        # char's columns to the line's columns
        columns += cols
    # We are at the end of the string, append the last line, not finished
    retlist.append((start_pos, spos + 1))
    return retlist


# wcswidth: An emulation of the POSIX wcswidth(3) function using xwcwidth.
def wcswidth(string: str) -> int:
    '''wcswidth(s)

    The wcswidth() function returns the number of columns needed to represent the wide-character string pointed to by s. Raise UnicodeError if an invalid unicode value is passed'''

    columns = 0
    for wc in string:
        columns += xwcwidth(wc)
    return columns


# cut_by_columns: takes a python string and a number of columns, returns a
# python string truncated to take at most that many columns
# For example cut_by_columns(n, "エメルカ") will return:
# - n == 5 -> "エメ" (which takes only 4 columns since we can't cut the
#   next character in half)
# - n == 2 -> "エ"
# - n == 1 -> ""
# - n == 42 -> "エメルカ"
# - etc
def cut_by_columns(string: str, limit: int) -> str:
    '''cut_by_columns(string, limit)

    returns a string truncated to take at most limit columns'''

    spos = 0
    columns = 0
    for wc in string:
        if columns == limit:
            break
        cols = xwcwidth(wc)
        if columns + cols > limit:
            break
        spos += 1
        columns += cols
    return string[:spos]
