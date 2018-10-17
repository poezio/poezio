# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.
"""
Define the variables (colors and some other stuff) that are
used when drawing the interface.

Colors are numbers from -1 to 7 (if only 8 colors are supported) or -1 to 255
if 256 colors are available.
If only 8 colors are available, all colors > 8 are converted using the
table_256_to_16 dict.

XHTML-IM colors are converted to -1 -> 255 colors if available, or directly to
-1 -> 8 if we are in 8-color-mode.

A pair_color is a background-foreground pair. All possible pairs are not created
at startup, because that would create 256*256 pairs, and almost all of them
would never be used.

A theme should define color tuples, like ``(200, -1)``, and when they are to
be used by poezio's interface, they will be created once, and kept in a list for
later usage.
A color tuple is of the form ``(foreground, background, optional)``
A color of -1 means the default color. So if you do not want to have
a background color, use ``(x, -1)``.
The optional third value of the tuple defines additional information. It
is a string and can contain one or more of these characters:

- ``b``: bold
- ``u``: underlined
- ``x``: blink

For example, ``(200, 208, 'bu')`` is bold, underlined and pink foreground on
orange background.

A theme file is a python file containing one object named 'theme', which is an
instance of a class (derived from the Theme class) defined in that same file.
For example, in pinkytheme.py:

.. code-block:: python

    import theming
    class PinkyTheme(theming.Theme):
        COLOR_NORMAL_TEXT = (200, -1)

    theme = PinkyTheme()

if the command '/theme pinkytheme' is issued, we import the pinkytheme.py file
and set the global variable 'theme' to pinkytheme.theme.

And in poezio's code we just use ``theme.COLOR_NORMAL_TEXT`` etc

Since a theme inherites from the Theme class (defined here), if a color is not defined in a
theme file, the color is the default one.

Some values in that class are a list of color tuple.
For example ``[(1, -1), (2, -1), (3, -1)]``
Such a list SHOULD contain at least one color tuple.
It is used for example to define color gradient, etc.
"""

import logging
log = logging.getLogger(__name__)

try:
    from poezio.config import config
except ImportError:
    if __name__ != "__main__":
        raise

import curses
import functools
import os
from typing import Dict, List, Union, Tuple, Optional
from pathlib import Path
from os import path
from poezio import colors, xdg, libpoezio

from importlib import machinery
finder = machinery.PathFinder()


class Theme:
    """
    The theme class, from which all themes should inherit.
    All of the following values can be replaced in subclasses, in
    order to create a new theme.

    Do not edit this file if you want to change the theme to suit your
    needs. Create a new theme and share it if you think it can be useful
    for others.
    """

    @classmethod
    def color_role(cls, role: str):
        role_mapping = {
            'moderator': cls.COLOR_USER_MODERATOR,
            'participant': cls.COLOR_USER_PARTICIPANT,
            'visitor': cls.COLOR_USER_VISITOR,
            'none': cls.COLOR_USER_NONE,
            '': cls.COLOR_USER_NONE
        }
        return role_mapping.get(role, cls.COLOR_USER_NONE)

    @classmethod
    def char_affiliation(cls, affiliation: str):
        affiliation_mapping = {
            'owner': cls.CHAR_AFFILIATION_OWNER,
            'admin': cls.CHAR_AFFILIATION_ADMIN,
            'member': cls.CHAR_AFFILIATION_MEMBER,
            'none': cls.CHAR_AFFILIATION_NONE
        }
        return affiliation_mapping.get(affiliation, cls.CHAR_AFFILIATION_NONE)

    @classmethod
    def color_show(cls, show: str):
        show_mapping = {
            'xa': cls.COLOR_STATUS_XA,
            'none': cls.COLOR_STATUS_NONE,
            'dnd': cls.COLOR_STATUS_DND,
            'away': cls.COLOR_STATUS_AWAY,
            'chat': cls.COLOR_STATUS_CHAT,
            '': cls.COLOR_STATUS_ONLINE,
            'available': cls.COLOR_STATUS_ONLINE,
            'unavailable': cls.COLOR_STATUS_UNAVAILABLE,
        }
        return show_mapping.get(show, cls.COLOR_STATUS_NONE)

    @classmethod
    def char_subscription(cls, sub: str, keep: str = 'incomplete'):
        sub_mapping = {
            'from': cls.CHAR_ROSTER_FROM,
            'both': cls.CHAR_ROSTER_BOTH,
            'none': cls.CHAR_ROSTER_NONE,
            'to': cls.CHAR_ROSTER_TO,
        }
        if keep == 'incomplete' and sub == 'both':
            return ''
        if keep in ('both', 'none', 'to', 'from'):
            return sub_mapping[sub] if sub == keep else ''
        return sub_mapping.get(sub, '')

    # Message text color
    COLOR_NORMAL_TEXT = (-1, -1)
    COLOR_INFORMATION_TEXT = (5, -1)  # TODO
    COLOR_WARNING_TEXT = (1, -1)

    # Color of the commands in the help message
    COLOR_HELP_COMMANDS = (208, -1)

    # "reverse" is a special value, available only for this option. It just
    # takes the nick colors and reverses it. A theme can still specify a
    # fixed color if need be.
    COLOR_HIGHLIGHT_NICK = "reverse"

    # Color of the participant JID in a MUC
    COLOR_MUC_JID = (4, -1)

    # User list color
    COLOR_USER_VISITOR = (239, -1)
    COLOR_USER_PARTICIPANT = (4, -1)
    COLOR_USER_NONE = (0, -1)
    COLOR_USER_MODERATOR = (1, -1)

    # nickname colors
    COLOR_REMOTE_USER = (5, -1)

    # The character printed in color (COLOR_STATUS_*) before the nickname
    # in the user list
    CHAR_STATUS = '|'

    # The characters used for the chatstates in the user list
    # in a MUC
    CHAR_CHATSTATE_ACTIVE = 'A'
    CHAR_CHATSTATE_COMPOSING = 'X'
    CHAR_CHATSTATE_PAUSED = 'p'

    # These characters are used for the affiliation in the user list
    # in a MUC
    CHAR_AFFILIATION_OWNER = '~'
    CHAR_AFFILIATION_ADMIN = '&'
    CHAR_AFFILIATION_MEMBER = '+'
    CHAR_AFFILIATION_NONE = '-'

    # XML Tab
    CHAR_XML_IN = 'IN '
    CHAR_XML_OUT = 'OUT'
    COLOR_XML_IN = (1, -1)
    COLOR_XML_OUT = (2, -1)

    # Color for the /me message
    COLOR_ME_MESSAGE = (6, -1)

    # Color for the number of revisions of a message
    COLOR_REVISIONS_MESSAGE = (3, -1, 'b')

    # Color for various important text. For example the "?" before JIDs in
    # the roster that require an user action.
    COLOR_IMPORTANT_TEXT = (3, 5, 'b')

    # Separators
    COLOR_VERTICAL_SEPARATOR = (4, -1)
    COLOR_NEW_TEXT_SEPARATOR = (2, -1)
    COLOR_MORE_INDICATOR = (6, 4)

    # Time
    CHAR_TIME_LEFT = ''
    CHAR_TIME_RIGHT = ''
    COLOR_TIME_STRING = (-1, -1)

    # Tabs
    COLOR_TAB_NORMAL = (7, 4)
    COLOR_TAB_NONEMPTY = (7, 4)
    COLOR_TAB_SCROLLED = (5, 4)
    COLOR_TAB_JOINED = (82, 4)
    COLOR_TAB_CURRENT = (7, 6)
    COLOR_TAB_COMPOSING = (7, 5)
    COLOR_TAB_NEW_MESSAGE = (7, 5)
    COLOR_TAB_HIGHLIGHT = (7, 3)
    COLOR_TAB_PRIVATE = (7, 2)
    COLOR_TAB_ATTENTION = (7, 1)
    COLOR_TAB_DISCONNECTED = (7, 8)

    COLOR_VERTICAL_TAB_NORMAL = (4, -1)
    COLOR_VERTICAL_TAB_NONEMPTY = (4, -1)
    COLOR_VERTICAL_TAB_JOINED = (82, -1)
    COLOR_VERTICAL_TAB_SCROLLED = (66, -1)
    COLOR_VERTICAL_TAB_CURRENT = (7, 4)
    COLOR_VERTICAL_TAB_NEW_MESSAGE = (5, -1)
    COLOR_VERTICAL_TAB_COMPOSING = (5, -1)
    COLOR_VERTICAL_TAB_HIGHLIGHT = (3, -1)
    COLOR_VERTICAL_TAB_PRIVATE = (2, -1)
    COLOR_VERTICAL_TAB_ATTENTION = (1, -1)
    COLOR_VERTICAL_TAB_DISCONNECTED = (8, -1)

    # yapf: disable

    # Nickname colors
    # A list of colors randomly attributed to nicks in MUCs
    # Setting more colors makes it harder to have two nicks with the same color,
    # avoiding confusions.
    LIST_COLOR_NICKNAMES = [
            (1, -1), (2, -1), (3, -1), (4, -1), (5, -1), (6, -1), (9, -1),
            (10, -1), (11, -1), (12, -1), (13, -1), (14, -1), (19, -1),
            (20, -1), (21, -1), (22, -1), (23, -1), (24, -1), (25, -1),
            (26, -1), (27, -1), (28, -1), (29, -1), (30, -1), (31, -1),
            (32, -1), (33, -1), (34, -1), (35, -1), (36, -1), (37, -1),
            (38, -1), (39, -1), (40, -1), (41, -1), (42, -1), (43, -1),
            (44, -1), (45, -1), (46, -1), (47, -1), (48, -1), (49, -1),
            (50, -1), (51, -1), (54, -1), (55, -1), (56, -1), (57, -1),
            (58, -1), (60, -1), (61, -1), (62, -1), (63, -1), (64, -1),
            (65, -1), (66, -1), (67, -1), (68, -1), (69, -1), (70, -1),
            (71, -1), (72, -1), (73, -1), (74, -1), (75, -1), (76, -1),
            (77, -1), (78, -1), (79, -1), (80, -1), (81, -1), (82, -1),
            (83, -1), (84, -1), (85, -1), (86, -1), (87, -1), (88, -1),
            (89, -1), (90, -1), (91, -1), (92, -1), (93, -1), (94, -1),
            (95, -1), (96, -1), (97, -1), (98, -1), (99, -1), (100, -1),
            (101, -1), (103, -1), (104, -1), (105, -1), (106, -1), (107, -1),
            (108, -1), (109, -1), (110, -1), (111, -1), (112, -1), (113, -1),
            (114, -1), (115, -1), (116, -1), (117, -1), (118, -1), (119, -1),
            (120, -1), (121, -1), (122, -1), (123, -1), (124, -1), (125, -1),
            (126, -1), (127, -1), (128, -1), (129, -1), (130, -1), (131, -1),
            (132, -1), (133, -1), (134, -1), (135, -1), (136, -1), (137, -1),
            (138, -1), (139, -1), (140, -1), (141, -1), (142, -1), (143, -1),
            (144, -1), (145, -1), (146, -1), (147, -1), (148, -1), (149, -1),
            (150, -1), (151, -1), (152, -1), (153, -1), (154, -1), (155, -1),
            (156, -1), (157, -1), (158, -1), (159, -1), (160, -1), (161, -1),
            (162, -1), (163, -1), (164, -1), (165, -1), (166, -1), (167, -1),
            (168, -1), (169, -1), (170, -1), (171, -1), (172, -1), (173, -1),
            (174, -1), (175, -1), (176, -1), (177, -1), (178, -1), (179, -1),
            (180, -1), (181, -1), (182, -1), (183, -1), (184, -1), (185, -1),
            (186, -1), (187, -1), (188, -1), (189, -1), (190, -1), (191, -1),
            (192, -1), (193, -1), (196, -1), (197, -1), (198, -1), (199, -1),
            (200, -1), (201, -1), (202, -1), (203, -1), (204, -1), (205, -1),
            (206, -1), (207, -1), (208, -1), (209, -1), (210, -1), (211, -1),
            (212, -1), (213, -1), (214, -1), (215, -1), (216, -1), (217, -1),
            (218, -1), (219, -1), (220, -1), (221, -1), (222, -1), (223, -1),
            (224, -1), (225, -1), (226, -1), (227, -1)]
    # XEP-0392 consistent color generation palette placeholder
    # it’s generated on first use when accessing the ccg_palette property
    CCG_PALETTE = None  # type: Optional[Dict[float, int]]
    CCG_Y = 0.5**0.45

    # yapf: enable

    # This is your own nickname
    COLOR_OWN_NICK = (254, -1)

    COLOR_LOG_MSG = (5, -1)
    # This is for in-tab error messages
    COLOR_ERROR_MSG = (9, 7, 'b')
    # Status color
    COLOR_STATUS_XA = (16, 90)
    COLOR_STATUS_NONE = (16, 4)
    COLOR_STATUS_DND = (16, 1)
    COLOR_STATUS_AWAY = (16, 3)
    COLOR_STATUS_CHAT = (16, 2)
    COLOR_STATUS_UNAVAILABLE = (-1, 247)
    COLOR_STATUS_ONLINE = (16, 4)

    # Bars
    COLOR_WARNING_PROMPT = (16, 1, 'b')
    COLOR_INFORMATION_BAR = (7, 4)
    COLOR_TOPIC_BAR = (7, 4)
    COLOR_SCROLLABLE_NUMBER = (220, 4, 'b')
    COLOR_SELECTED_ROW = (-1, 33)
    COLOR_PRIVATE_NAME = (-1, 4)
    COLOR_CONVERSATION_NAME = (2, 4)
    COLOR_CONVERSATION_RESOURCE = (121, 4)
    COLOR_GROUPCHAT_NAME = (7, 4)
    COLOR_COLUMN_HEADER = (36, 4)
    COLOR_COLUMN_HEADER_SEL = (4, 36)

    # Strings for special messages (like join, quit, nick change, etc)
    # Special messages
    CHAR_JOIN = '--->'
    CHAR_QUIT = '<---'
    CHAR_KICK = '-!-'
    CHAR_NEW_TEXT_SEPARATOR = '- '
    CHAR_OK = '✔'
    CHAR_ERROR = '✖'
    CHAR_EMPTY = ' '
    CHAR_ACK_RECEIVED = CHAR_OK
    CHAR_NACK = CHAR_ERROR
    CHAR_COLUMN_ASC = ' ▲'
    CHAR_COLUMN_DESC = ' ▼'
    CHAR_ROSTER_ERROR = CHAR_ERROR
    CHAR_ROSTER_TUNE = '♪'
    CHAR_ROSTER_ASKED = '?'
    CHAR_ROSTER_ACTIVITY = 'A'
    CHAR_ROSTER_MOOD = 'M'
    CHAR_ROSTER_GAMING = 'G'
    CHAR_ROSTER_FROM = '←'
    CHAR_ROSTER_BOTH = '↔'
    CHAR_ROSTER_TO = '→'
    CHAR_ROSTER_NONE = '⇹'

    COLOR_CHAR_ACK = (2, -1)
    COLOR_CHAR_NACK = (1, -1)

    COLOR_ROSTER_GAMING = (6, -1)
    COLOR_ROSTER_MOOD = (2, -1)
    COLOR_ROSTER_ACTIVITY = (3, -1)
    COLOR_ROSTER_TUNE = (6, -1)
    COLOR_ROSTER_ERROR = (1, -1)
    COLOR_ROSTER_SUBSCRIPTION = (-1, -1)

    COLOR_JOIN_CHAR = (4, -1)
    COLOR_QUIT_CHAR = (1, -1)
    COLOR_KICK_CHAR = (1, -1)

    # Vertical tab list color
    COLOR_VERTICAL_TAB_NUMBER = (34, -1)

    # Info messages color (the part before the ">")
    INFO_COLORS = {
        'info': (5, -1),
        'error': (16, 1),
        'warning': (1, -1),
        'roster': (2, -1),
        'help': (10, -1),
        'headline': (11, -1, 'b'),
        'tune': (6, -1),
        'gaming': (6, -1),
        'mood': (2, -1),
        'activity': (3, -1),
        'default': (7, -1),
    }

    @property
    def ccg_palette(self):
        prepare_ccolor_palette(self)
        return self.CCG_PALETTE


# This is the default theme object, used if no theme is defined in the conf
theme = Theme()

load_path = []  # type: List[str]


def dump_tuple(tup: Union[Tuple[int, int], Tuple[int, int, str]]) -> str:
    """
    Dump a tuple to a string of fg,bg,attr (optional)
    """
    return ','.join(str(i) for i in tup)


@functools.lru_cache(maxsize=128)
def to_curses_attr(
        colors: Union[Tuple[int, int], Tuple[int, int, str]]) -> int:
    """
    Takes a color tuple (as defined at the top of this file) and
    returns a valid curses attr that can be passed directly to attron() or attroff()
    """
    attrs = '' if len(colors) < 3 else colors[2]
    return libpoezio.to_curses_attr(colors[0], colors[1], attrs)

def get_theme() -> Theme:
    """
    Returns the current theme
    """
    return theme


def update_themes_dir(option: Optional[str] = None,
                      value: Optional[str] = None):
    global load_path
    load_path = []

    # import from the git sources
    default_dir = path.join(
        path.dirname(path.dirname(__file__)), 'data/themes')
    if path.exists(default_dir):
        load_path.append(default_dir)

    # import from the user-defined prefs
    themes_dir_str = config.get('themes_dir')
    themes_dir = Path(themes_dir_str).expanduser(
    ) if themes_dir_str else xdg.DATA_HOME / 'themes'
    try:
        themes_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log.exception('Unable to create the themes dir (%s):', themes_dir)
    else:
        load_path.append(str(themes_dir))

    # system-wide import
    try:
        import poezio_themes
    except ImportError:
        pass
    else:
        if poezio_themes.__path__:
            load_path.append(list(poezio_themes.__path__)[0])

    log.debug('Theme load path: %s', load_path)


def prepare_ccolor_palette(theme: Theme) -> None:
    """
    Prepare the Consistent Color Generation (XEP-0392) palette for a theme.
    """
    if theme.CCG_PALETTE is not None:
        return None

    if any(bg != -1 for fg, bg in theme.LIST_COLOR_NICKNAMES):
        # explicitly disable CCG, can’t handle dynamic background colors
        theme.CCG_PALETTE = {}
        return None

    theme.CCG_PALETTE = colors.generate_ccg_palette(
        [
            fg for fg, _ in theme.LIST_COLOR_NICKNAMES
            # exclude grayscale
            if fg < 232
        ],
        theme.CCG_Y,
    )
    return None


def reload_theme() -> Optional[str]:
    theme_name = config.get('theme')
    global theme
    if theme_name == 'default' or not theme_name.strip():
        theme = Theme()
        return None
    new_theme = None
    exc = None
    try:
        loader = finder.find_module(theme_name, load_path)
        if not loader:
            return 'Failed to load the theme %s' % theme_name
        new_theme = loader.load_module()
    except Exception as e:
        log.error('Failed to load the theme %s', theme_name, exc_info=True)
        exc = e

    if not new_theme:
        return 'Failed to load theme: %s' % exc

    if hasattr(new_theme, 'theme'):
        theme = new_theme.theme
        prepare_ccolor_palette(theme)
        return None
    return 'No theme present in the theme file'


if __name__ == '__main__':
    # Display some nice text with nice colors
    s = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    s.addstr('%s colors detected\n\n' % curses.COLORS, to_curses_attr((3, -1)))
    for i in range(curses.COLORS):
        s.addstr('%s ' % i, to_curses_attr((i, -1)))
    s.addstr('\n')
    s.refresh()
    try:
        s.getkey()
    except KeyboardInterrupt:
        pass
    finally:
        curses.endwin()
        print()
