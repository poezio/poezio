import curses
import hashlib
import math

# BT.601 (YCbCr) constants, see XEP-0392
K_R = 0.299
K_G = 0.587
K_B = 1 - K_R - K_G


def ncurses_color_to_rgb(color):
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


def rgb_to_ycbcr(r, g, b):
    y = K_R * r + K_G * g + K_B * b
    cr = (r - y) / (1 - K_R) / 2
    cb = (b - y) / (1 - K_B) / 2
    return y, cb, cr


def generate_ccg_palette(curses_palette, reference_y):
    cbcr_palette = {}
    for curses_color in curses_palette:
        r, g, b = ncurses_color_to_rgb(curses_color)
        # drop grayscale
        if r == g == b:
            continue
        y, cb, cr = rgb_to_ycbcr(r, g, b)
        key = round(cbcr_to_angle(cb, cr), 2)
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


def text_to_angle(text):
    hf = hashlib.sha1()
    hf.update(text.encode("utf-8"))
    hue = int.from_bytes(hf.digest()[:2], "little")
    return hue / 65535 * math.pi * 2


def angle_to_cbcr_edge(angle):
    cr = math.sin(angle)
    cb = math.cos(angle)
    if abs(cr) > abs(cb):
        factor = 0.5 / abs(cr)
    else:
        factor = 0.5 / abs(cb)
    return cb * factor, cr * factor


def cbcr_to_angle(cb, cr):
    magn = math.sqrt(cb**2 + cr**2)
    if magn > 0:
        cr /= magn
        cb /= magn
    return math.atan2(cr, cb) % (2 * math.pi)


def ccg_palette_lookup(palette, angle):
    # try quick lookup first
    try:
        color = palette[round(angle, 2)]
    except KeyError:
        pass
    else:
        return color

    best_metric = float("inf")
    best = None
    for anglep, color in palette.items():
        metric = abs(anglep - angle)
        if metric < best_metric:
            best_metric = metric
            best = color

    return best


def ccg_text_to_color(palette, text):
    angle = text_to_angle(text)
    return ccg_palette_lookup(palette, angle)
