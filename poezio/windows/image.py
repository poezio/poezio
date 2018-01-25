"""
Defines a window which contains either an image or a border.
"""

import curses
from io import BytesIO

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from poezio.windows.base_wins import Win
from poezio.theming import get_theme, to_curses_attr
from poezio.xhtml import _parse_css_color
from poezio.config import config


class ImageWin(Win):
    """
    A window which contains either an image or a border.
    """

    def __init__(self):
        self._image = None
        Win.__init__(self)
        if config.get('image_use_half_blocks'):
            self._display_avatar = self._display_avatar_half_blocks
        else:
            self._display_avatar = self._display_avatar_full_blocks

    def resize(self, height: int, width: int, y: int, x: int):
        self._resize(height, width, y, x)
        if self._image is None:
            return
        self._display_avatar(width, height)

    def refresh(self, data):
        self._win.erase()
        if data is not None and HAS_PIL:
            image_file = BytesIO(data)
            try:
                image = Image.open(image_file)
            except OSError:
                self._display_border()
            else:
                self._image = image.convert('RGB')
                self._display_avatar(self.width, self.height)
        else:
            self._display_border()
        self._refresh()

    def _display_border(self):
        self._image = None
        attribute = to_curses_attr(get_theme().COLOR_VERTICAL_SEPARATOR)
        self._win.attron(attribute)
        self._win.border(curses.ACS_VLINE, curses.ACS_VLINE, curses.ACS_HLINE,
                         curses.ACS_HLINE, curses.ACS_ULCORNER,
                         curses.ACS_URCORNER, curses.ACS_LLCORNER,
                         curses.ACS_LRCORNER)
        self._win.attroff(attribute)

    @staticmethod
    def _compute_size(image_size, width: int, height: int):
        height *= 2
        src_width, src_height = image_size
        ratio = src_width / src_height
        new_width = height * ratio
        new_height = width / ratio
        if new_width > width:
            height = int(new_height)
        elif new_height > height:
            width = int(new_width)
        return width, height

    def _display_avatar_half_blocks(self, width: int, height: int):
        original_height = height
        original_width = width
        size = self._compute_size(self._image.size, width, height)
        image2 = self._image.resize(size, resample=Image.BILINEAR)
        data = image2.tobytes()
        width, height = size
        start_y = (original_height - height // 2) // 2
        start_x = (original_width - width) // 2
        for y in range(height // 2):
            two_lines = data[(2 * y) * width * 3:(2 * y + 2) * width * 3]
            line1 = two_lines[:width * 3]
            line2 = two_lines[width * 3:]
            self.move(start_y + y, start_x)
            for x in range(0, width * 3, 3):
                r, g, b = line1[x:x + 3]
                top_color = _parse_css_color('#%02x%02x%02x' % (r, g, b))
                r, g, b = line2[x:x + 3]
                bot_color = _parse_css_color('#%02x%02x%02x' % (r, g, b))
                self.addstr('▄', to_curses_attr((bot_color, top_color)))

    def _display_avatar_full_blocks(self, width: int, height: int):
        original_height = height
        original_width = width
        width, height = self._compute_size(self._image.size, width, height)
        height //= 2
        size = width, height
        image2 = self._image.resize(size, resample=Image.BILINEAR)
        data = image2.tobytes()
        start_y = (original_height - height) // 2
        start_x = (original_width - width) // 2
        for y in range(height):
            line = data[y * width * 3:(y + 1) * width * 3]
            self.move(start_y + y, start_x)
            for x in range(0, width * 3, 3):
                r, g, b = line[x:x + 3]
                color = _parse_css_color('#%02x%02x%02x' % (r, g, b))
                self.addstr('█', to_curses_attr((color, -1)))
