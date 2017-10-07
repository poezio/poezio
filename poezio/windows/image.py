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
from poezio.theming import to_curses_attr
from poezio.xhtml import _parse_css_color

class ImageWin(Win):
    """
    A window which contains either an image or a border.
    """
    def __init__(self):
        self._image = None
        Win.__init__(self)

    def resize(self, height: int, width: int, y: int, x: int):
        self._resize(height, width, y, x)
        if self._image is None:
            return
        _display_avatar(width, height)

    def refresh(self, data):
        self._win.clear()
        if data is None or not HAS_PIL:
            self._image = None
            self._display_border()
        else:
            image_file = BytesIO(data)
            self._image = Image.open(image_file).convert('RGB')
            self._display_avatar(self.width, self.height)
        self._refresh()

    def _display_border(self):
        self._win.border(curses.ACS_VLINE, curses.ACS_VLINE,
                         curses.ACS_HLINE, curses.ACS_HLINE,
                         curses.ACS_ULCORNER, curses.ACS_URCORNER,
                         curses.ACS_LLCORNER, curses.ACS_LRCORNER)

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

    def _display_avatar(self, width: int, height: int):
        original_height = height
        original_width = width
        size = self._compute_size(self._image.size, width, height)
        image2 = self._image.resize(size, resample=Image.BILINEAR)
        data = image2.tobytes()
        width, height = size
        start_y = (original_height - height // 2) // 2
        start_x = (original_width - width) // 2
        for y in range(height // 2):
            two_lines = data[(2 * y) * width * 3: (2 * y + 2) * width * 3]
            line1 = two_lines[:width * 3]
            line2 = two_lines[width * 3:]
            self.move(start_y + y, start_x)
            for x in range(width):
                r, g, b = line1[x * 3: (x + 1) * 3]
                top_color = _parse_css_color('#%02x%02x%02x' % (r, g, b))
                r, g, b = line2[x * 3: (x + 1) * 3]
                bot_color = _parse_css_color('#%02x%02x%02x' % (r, g, b))
                self.addstr('▄', to_curses_attr((bot_color, top_color)))
