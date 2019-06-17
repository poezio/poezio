"""
Defines a window which contains either an image or a border.
"""

import curses
from io import BytesIO

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    class Image:
        class Image:
            pass
    HAS_PIL = False

try:
    import gi
    gi.require_version('Rsvg', '2.0')
    from gi.repository import Rsvg
    import cairo
    HAS_RSVG = True
except (ImportError, ValueError, AttributeError):
    HAS_RSVG = False

from poezio.windows.base_wins import Win
from poezio.theming import get_theme, to_curses_attr
from poezio.xhtml import _parse_css_color
from poezio.config import config

from typing import Tuple, Optional, Callable


MAX_SIZE = 16


def render_svg(svg: bytes) -> Optional[Image.Image]:
    if not HAS_RSVG:
        return None
    try:
        handle = Rsvg.Handle.new_from_data(svg)
        dimensions = handle.get_dimensions()
        biggest_dimension = max(dimensions.width, dimensions.height)
        scale = MAX_SIZE / biggest_dimension
        translate_x = (biggest_dimension - dimensions.width) / 2
        translate_y = (biggest_dimension - dimensions.height) / 2

        surface = cairo.ImageSurface(cairo.Format.ARGB32, MAX_SIZE, MAX_SIZE)
        context = cairo.Context(surface)
        context.scale(scale, scale)
        context.translate(translate_x, translate_y)
        handle.render_cairo(context)
        data = surface.get_data()
        image = Image.frombytes('RGBA', (MAX_SIZE, MAX_SIZE), data.tobytes())
        # This is required because Cairo uses a BGRA (in host endianness)
        # format, and PIL an ABGR (in byte order) format.  Yes, this is
        # confusing.
        b, g, r, a = image.split()
        return Image.merge('RGB', (r, g, b))
    except Exception:
        return None


class ImageWin(Win):
    """
    A window which contains either an image or a border.
    """

    __slots__ = ('_image', '_display_avatar')

    def __init__(self) -> None:
        self._image = None  # type: Optional[Image.Image]
        Win.__init__(self)
        if config.get('image_use_half_blocks'):
            self._display_avatar = self._display_avatar_half_blocks  # type: Callable[[int, int], None]
        else:
            self._display_avatar = self._display_avatar_full_blocks

    def resize(self, height: int, width: int, y: int, x: int) -> None:
        self._resize(height, width, y, x)
        if self._image is None:
            return
        self._display_avatar(width, height)

    def refresh(self, data: Optional[bytes]) -> None:
        self._win.erase()
        if data is not None and HAS_PIL:
            image_file = BytesIO(data)
            try:
                try:
                    image = Image.open(image_file)
                except OSError:
                    # TODO: Make the caller pass the MIME type, so we don’t
                    # have to try all renderers like that.
                    image = render_svg(data)
                    if image is None:
                        raise
            except OSError:
                self._display_border()
            else:
                self._image = image.convert('RGB')
                self._display_avatar(self.width, self.height)
        else:
            self._display_border()
        self._refresh()

    def _display_border(self) -> None:
        self._image = None
        attribute = to_curses_attr(get_theme().COLOR_VERTICAL_SEPARATOR)
        self._win.attron(attribute)
        self._win.border(curses.ACS_VLINE, curses.ACS_VLINE, curses.ACS_HLINE,
                         curses.ACS_HLINE, curses.ACS_ULCORNER,
                         curses.ACS_URCORNER, curses.ACS_LLCORNER,
                         curses.ACS_LRCORNER)
        self._win.attroff(attribute)

    @staticmethod
    def _compute_size(image_size: Tuple[int, int], width: int, height: int) -> Tuple[int, int]:
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

    def _display_avatar_half_blocks(self, width: int, height: int) -> None:
        if self._image is None:
            return
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

    def _display_avatar_full_blocks(self, width: int, height: int) -> None:
        if self._image is None:
            return
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
