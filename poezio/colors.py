from typing import Tuple, Dict, List
import curses
import hashlib
import math

from . import hsluv

Palette = Dict[float, int]

# BT.601 (YCbCr) constants, see XEP-0392
K_R = 0.299
K_G = 0.587
K_B = 1 - K_R - K_G


def ncurses_color_to_rgb(color: int) -> Tuple[float, float, float]:
    if color <= 15:
        try:
            (r, g, b) = curses.color_content(color)
        except:  # fallback in faulty terminals (e.g. xterm)
            (r, g, b) = curses.color_content(color % 8)
        r = r / 1000 * 5
        g = g / 1000 * 5
        b = b / 1000 * 5
    elif color <= 231:
        color = color - 16
        b = color % 6
        color = color // 6
        g = color % 6
        color = color // 6
        r = color % 6
    else:
        color -= 232
        r = g = b = color / 24 * 5
    return r / 5, g / 5, b / 5


def generate_ccg_palette(curses_palette: List[int],
                         reference_y: float) -> Palette:
    cbcr_palette = {}  # type: Dict[float, Tuple[float, int]]
    for curses_color in curses_palette:
        r, g, b = ncurses_color_to_rgb(curses_color)
        # drop grayscale
        if r == g == b:
            continue
        h, _, y = hsluv.rgb_to_hsluv((r, g, b))
        # this is to keep the code compatible with earlier versions of XEP-0392
        y = y / 100
        key = round(h)
        try:
            existing_y, *_ = cbcr_palette[key]
        except KeyError:
            pass
        else:
            if abs(existing_y - reference_y) <= abs(y - reference_y):
                continue
        cbcr_palette[key] = y, curses_color
    return {
        angle: curses_color
        for angle, (_, curses_color) in cbcr_palette.items()
    }


def text_to_angle(text: str) -> float:
    hf = hashlib.sha1()
    hf.update(text.encode("utf-8"))
    hue = int.from_bytes(hf.digest()[:2], "little")
    return hue / 65535 * 360


def ccg_palette_lookup(palette: Palette, angle: float) -> int:
    # try quick lookup first
    try:
        return palette[round(angle)]
    except KeyError:
        pass

    best_metric = float("inf")
    best = None
    for anglep, color in palette.items():
        metric = abs(anglep - angle)
        if metric < best_metric:
            best_metric = metric
            best = color

    return best


def ccg_text_to_color(palette, text: str) -> int:
    angle = text_to_angle(text)
    return ccg_palette_lookup(palette, angle)
