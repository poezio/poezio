# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.
"""
Various methods to convert
shell colors to poezio colors,
xhtml code to shell colors,
poezio colors to xhtml code
"""

import hashlib
import re
from base64 import b64encode, b64decode
from os import path
from urllib.parse import unquote
from pathlib import Path

from io import BytesIO
from xml import sax
from xml.sax import saxutils
from typing import List, Dict, Optional, Union, Tuple

from slixmpp.xmlstream import ET
from poezio.config import config
from poezio.colors import ncurses_color_to_rgb

digits = '0123456789'  # never trust the modules

XHTML_NS = 'http://www.w3.org/1999/xhtml'

# HTML named colors
colors = {
    'aliceblue': 231,
    'antiquewhite': 231,
    'aqua': 51,
    'aquamarine': 122,
    'azure': 231,
    'beige': 231,
    'bisque': 230,
    'black': 232,
    'blanchedalmond': 230,
    'blue': 21,
    'blueviolet': 135,
    'brown': 124,
    'burlywood': 223,
    'cadetblue': 109,
    'chartreuse': 118,
    'chocolate': 172,
    'coral': 209,
    'cornflowerblue': 111,
    'cornsilk': 231,
    'crimson': 197,
    'cyan': 51,
    'darkblue': 19,
    'darkcyan': 37,
    'darkgoldenrod': 178,
    'darkgray': 247,
    'darkgreen': 28,
    'darkgrey': 247,
    'darkkhaki': 186,
    'darkmagenta': 127,
    'darkolivegreen': 65,
    'darkorange': 214,
    'darkorchid': 134,
    'darkred': 124,
    'darksalmon': 216,
    'darkseagreen': 151,
    'darkslateblue': 61,
    'darkslategray': 59,
    'darkslategrey': 59,
    'darkturquoise': 44,
    'darkviolet': 128,
    'deeppink': 199,
    'deepskyblue': 45,
    'dimgray': 241,
    'dimgrey': 241,
    'dodgerblue': 39,
    'firebrick': 160,
    'floralwhite': 231,
    'forestgreen': 34,
    'fuchsia': 201,
    'gainsboro': 252,
    'ghostwhite': 231,
    'gold': 226,
    'goldenrod': 214,
    'gray': 244,
    'green': 34,
    'greenyellow': 191,
    'grey': 244,
    'honeydew': 231,
    'hotpink': 212,
    'indianred': 174,
    'indigo': 55,
    'ivory': 231,
    'khaki': 229,
    'lavender': 231,
    'lavenderblush': 231,
    'lawngreen': 118,
    'lemonchiffon': 230,
    'lightblue': 195,
    'lightcoral': 217,
    'lightcyan': 231,
    'lightgoldenrodyellow': 230,
    'lightgray': 251,
    'lightgreen': 157,
    'lightgrey': 251,
    'lightpink': 224,
    'lightsalmon': 216,
    'lightseagreen': 43,
    'lightskyblue': 153,
    'lightslategray': 109,
    'lightslategrey': 109,
    'lightsteelblue': 189,
    'lightyellow': 231,
    'lime': 46,
    'limegreen': 77,
    'linen': 231,
    'magenta': 201,
    'maroon': 124,
    'mediumaquamarine': 115,
    'mediumblue': 20,
    'mediumorchid': 170,
    'mediumpurple': 141,
    'mediumseagreen': 78,
    'mediumslateblue': 105,
    'mediumspringgreen': 49,
    'mediumturquoise': 80,
    'mediumvioletred': 163,
    'midnightblue': 18,
    'mintcream': 231,
    'mistyrose': 231,
    'moccasin': 230,
    'navajowhite': 230,
    'navy': 19,
    'oldlace': 231,
    'olive': 142,
    'olivedrab': 106,
    'orange': 214,
    'orangered': 202,
    'orchid': 213,
    'palegoldenrod': 229,
    'palegreen': 157,
    'paleturquoise': 195,
    'palevioletred': 211,
    'papayawhip': 231,
    'peachpuff': 230,
    'peru': 179,
    'pink': 224,
    'plum': 219,
    'powderblue': 195,
    'purple': 127,
    'red': 196,
    'rosybrown': 181,
    'royalblue': 69,
    'saddlebrown': 130,
    'salmon': 216,
    'sandybrown': 216,
    'seagreen': 72,
    'seashell': 231,
    'sienna': 131,
    'silver': 250,
    'skyblue': 153,
    'slateblue': 104,
    'slategray': 109,
    'slategrey': 109,
    'snow': 231,
    'springgreen': 48,
    'steelblue': 74,
    'tan': 187,
    'teal': 37,
    'thistle': 225,
    'tomato': 209,
    'turquoise': 86,
    'violet': 219,
    'wheat': 230,
    'white': 255,
    'whitesmoke': 255,
    'yellow': 226,
    'yellowgreen': 149
}  # type: Dict[str, int]

whitespace_re = re.compile(r'\s+')

xhtml_attr_re = re.compile(r'\x19-?\d[^}]*}|\x19[buaio]')
xhtml_data_re = re.compile(r'data:image/([a-z]+);base64,(.+)')
poezio_color_double = re.compile(r'(?:\x19\d+}|\x19\d)+(\x19\d|\x19\d+})')
poezio_format_trim = re.compile(r'(\x19\d+}|\x19\d|\x19[buaio]|\x19o)+\x19o')

xhtml_simple_attr_re = re.compile(r'\x19\d')


def get_body_from_message_stanza(message,
                                 use_xhtml=False,
                                 extract_images_to: Optional[Path] = None
                                 ) -> str:
    """
    Returns a string with xhtml markups converted to
    poezio colors if there's an xhtml_im element, or
    the body (without any color) otherwise
    """
    if not use_xhtml:
        return message['body']
    xhtml = message.xml.find('{http://jabber.org/protocol/xhtml-im}html')
    if xhtml is None:
        return message['body']
    xhtml_body = xhtml.find('{http://www.w3.org/1999/xhtml}body')
    if xhtml_body is None:
        return message['body']
    content = xhtml_to_poezio_colors(xhtml_body, tmp_dir=extract_images_to)
    content = content if content else message['body']
    return content or " "


def rgb_to_html(rgb: Tuple[float, float, float]) -> str:
    """Get the RGB HTML value"""
    r, g, b = rgb
    return '#%02X%02X%02X' % (round(r * 255), round(g * 255), round(b * 255))


def ncurses_color_to_html(color: int) -> str:
    """
    Takes an int between 0 and 256 and returns
    a string of the form #XXXXXX representing an
    html color.
    """
    return rgb_to_html(ncurses_color_to_rgb(color))


def _parse_css_color(name: str) -> int:
    if name[0] == '#':
        name = name[1:]
        length = len(name)
        if length != 3 and length != 6:
            return -1
        value = int(name, 16)
        if length == 6:
            r = value >> 16
            g = (value >> 8) & 0xff
            b = value & 0xff
            if r == g == b:
                return int(232 + 0.0941 * r)
            mult = 0.0235
        else:
            r = value >> 8
            g = (value >> 4) & 0xf
            b = value & 0xf
            if r == g == b:
                return int(232 + 1.54 * r)
            mult = 0.3984
        return 6 * 6 * int(mult * r) + 6 * int(mult * g) + int(mult * b) + 16
    if name in colors:
        return colors[name]
    return -1


def _parse_css(css: str) -> str:
    shell = ''
    rules = css.split(';')
    for rule in rules:
        if ':' not in rule:
            continue
        key, value = rule.split(':', 1)
        key = key.strip()
        value = value.strip()
        if key == 'background-color':
            pass  #shell += '\x191'
        elif key == 'color':
            color = _parse_css_color(value)
            if color != -1:
                shell += '\x19%d}' % color
        elif key == 'font-style':
            shell += '\x19i'
        elif key == 'font-weight':
            shell += '\x19b'
        elif key == 'margin-left':
            shell += '    '
        elif key == 'text-align':
            pass
        elif key == 'text-decoration':
            if value == 'underline':
                shell += '\x19u'
            elif value == 'blink':
                shell += '\x19a'
    return shell


def _trim(string: str) -> str:
    return re.sub(whitespace_re, ' ', string)


def get_hash(data: bytes) -> str:
    # Currently using SHA-256, this might change in the future.
    # base64 gives shorter hashes than hex, so use that.
    return b64encode(hashlib.sha256(data).digest()).rstrip(b'=').replace(
        b'/', b'-').decode()


class XHTMLHandler(sax.ContentHandler):
    def __init__(self, force_ns=False,
                 tmp_image_dir: Optional[Path] = None) -> None:
        self.builder = []  # type: List[str]
        self.formatting = []  # type: List[str]
        self.attrs = []  # type: List[Dict[str, str]]
        self.list_state = []  #  type: List[Union[str, int]]
        self.is_pre = False
        self.a_start = 0
        # do not care about xhtml-in namespace
        self.force_ns = force_ns

        self.tmp_image_dir = Path(tmp_image_dir) if tmp_image_dir else None
        self.enable_css_parsing = config.get('enable_css_parsing')

    @property
    def result(self) -> str:
        sanitized = re.sub(poezio_color_double, r'\1',
                           ''.join(self.builder).strip())
        return re.sub(poezio_format_trim, '\x19o', sanitized)

    def append_formatting(self, formatting: str):
        self.formatting.append(formatting)
        self.builder.append(formatting)

    def pop_formatting(self):
        self.formatting.pop()
        self.builder.append('\x19o' + ''.join(self.formatting))

    def characters(self, characters: str):
        self.builder.append(characters if self.is_pre else _trim(characters))

    def startElementNS(self, name, _, attrs):
        if name[0] != XHTML_NS and not self.force_ns:
            return

        builder = self.builder
        attrs = {
            name: value
            for ((ns, name), value) in attrs.items() if ns is None
        }
        self.attrs.append(attrs)

        if 'style' in attrs and self.enable_css_parsing:
            style = _parse_css(attrs['style'])
            self.append_formatting(style)

        name = name[1]
        if name == 'a':
            self.append_formatting('\x19u')
            self.a_start = len(self.builder)
        elif name == 'blockquote':
            builder.append('“')
        elif name == 'br':
            builder.append('\n')
        elif name == 'cite':
            self.append_formatting('\x19u')
        elif name == 'em':
            self.append_formatting('\x19i')
        elif name == 'img':
            if re.match(xhtml_data_re,
                        attrs['src']) and self.tmp_image_dir is not None:
                type_, data = [
                    i for i in re.split(xhtml_data_re, attrs['src']) if i
                ]
                bin_data = b64decode(unquote(data))
                filename = get_hash(bin_data) + '.' + type_
                filepath = self.tmp_image_dir / filename
                if not path.exists(filepath):
                    try:
                        self.tmp_image_dir.mkdir(parents=True, exist_ok=True)
                        with open(filepath, 'wb') as fd:
                            fd.write(bin_data)
                        builder.append('[file stored as %s]' % filename)
                    except Exception as e:
                        builder.append('[Error while saving image: %s]' % e)
                else:
                    builder.append('[file stored as %s]' % filename)
            else:
                builder.append(_trim(attrs['src']))
            if 'alt' in attrs:
                builder.append(' (%s)' % _trim(attrs['alt']))
        elif name == 'ul':
            self.list_state.append('ul')
        elif name == 'ol':
            self.list_state.append(1)
        elif name == 'li':
            try:
                state = self.list_state[-1]
            except IndexError:
                state = 'ul'
            if state == 'ul':
                builder.append('\n• ')
            else:
                builder.append('\n%d) ' % state)
                state += 1
                self.list_state[-1] = state
        elif name == 'p':
            builder.append('\n')
        elif name == 'pre':
            builder.append('\n')
            self.is_pre = True
        elif name == 'strong':
            self.append_formatting('\x19b')

    def endElementNS(self, name, _):
        if name[0] != XHTML_NS and not self.force_ns:
            return

        builder = self.builder
        attrs = self.attrs.pop()
        name = name[1]

        if name == 'a':
            self.pop_formatting()
            # do not display the link twice
            text_elements = [
                x for x in self.builder[self.a_start:]
                if not x.startswith('\x19')
            ]
            link_text = ''.join(text_elements).strip()
            if 'href' in attrs and attrs['href'] != link_text:
                builder.append(' (%s)' % _trim(attrs['href']))
        elif name == 'blockquote':
            builder.append('”')
        elif name in ('cite', 'em', 'strong'):
            self.pop_formatting()
        elif name in ('ol', 'p', 'ul'):
            builder.append('\n')
        elif name == 'pre':
            builder.append('\n')
            self.is_pre = False

        if 'style' in attrs and self.enable_css_parsing:
            self.pop_formatting()

        if 'title' in attrs:
            builder.append(' [' + attrs['title'] + ']')


def xhtml_to_poezio_colors(xml, force=False,
                           tmp_dir: Optional[Path] = None) -> str:
    if isinstance(xml, str):
        xml = xml.encode('utf8')
    elif not isinstance(xml, bytes):
        xml = ET.tostring(xml)

    handler = XHTMLHandler(force_ns=force, tmp_image_dir=tmp_dir)
    parser = sax.make_parser()
    parser.setFeature(sax.handler.feature_namespaces, True)
    parser.setContentHandler(handler)
    parser.parse(BytesIO(xml))
    return handler.result


def clean_text(s: str) -> str:
    """
    Remove all xhtml-im attributes (\x19etc) from the string with the
    complete color format, i.e \x19xxx}
    """
    s = re.sub(xhtml_attr_re, "", s)
    return s


def clean_text_simple(string: str) -> str:
    """
    Remove all \x19 from the string formatted with simple colors:
    \x198
    """
    pos = string.find('\x19')
    while pos != -1:
        string = string[:pos] + string[pos + 2:]
        pos = string.find('\x19')
    return string


def convert_simple_to_full_colors(text: str) -> str:
    """
    takes a \x19n formatted string and returns
    a \x19n} formatted one.
    """
    # TODO, have a single list of this. This is some sort of
    # duplicate from windows.format_chars
    mapping = str.maketrans({
        '\x0E': '\x19b',
        '\x0F': '\x19o',
        '\x10': '\x19u',
        '\x11': '\x191',
        '\x12': '\x192',
        '\x13': '\x193',
        '\x14': '\x194',
        '\x15': '\x195',
        '\x16': '\x196',
        '\x17': '\x197',
        '\x18': '\x198',
        '\x19': '\x199',
        '\x1A': '\x19i'
    })
    text = text.translate(mapping)

    def add_curly_bracket(match):
        return match.group(0) + '}'

    return re.sub(xhtml_simple_attr_re, add_curly_bracket, text)


number_to_color_names = {
    1: 'red',
    2: 'green',
    3: 'yellow',
    4: 'blue',
    5: 'violet',
    6: 'turquoise',
    7: 'white'
}  # type: Dict[int, str]


def format_inline_css(_dict: Dict[str, str]) -> str:
    return ''.join(('%s: %s;' % (key, value) for key, value in _dict.items()))


def poezio_colors_to_html(string: str) -> str:
    """
    Convert poezio colors to html
    (e.g. \x191}: <span style='color: red'>)
    """
    # Maintain a list of the current css attributes used
    # And check if a tag is open (by design, we only open
    # spans tag, and they cannot be nested.
    current_attrs = {}  # type: Dict[str, str]
    tag_open = False
    next_attr_char = string.find('\x19')
    build = ["<body xmlns='http://www.w3.org/1999/xhtml'><p>"]

    def check_property(key, value):
        nonlocal tag_open
        if current_attrs.get(key, None) == value:
            return
        current_attrs[key] = value
        if tag_open:
            tag_open = False
            build.append('</span>')

    while next_attr_char != -1:
        attr_char = string[next_attr_char + 1].lower()

        if next_attr_char != 0 and string[:next_attr_char]:
            if current_attrs and not tag_open:
                build.append(
                    '<span style="%s">' % format_inline_css(current_attrs))
                tag_open = True
            build.append(saxutils.escape(string[:next_attr_char]))

        if attr_char == 'o':
            if tag_open:
                build.append('</span>')
                tag_open = False
            current_attrs = {}
        elif attr_char == 'b':
            check_property('font-weight', 'bold')
        elif attr_char == 'u':
            check_property('text-decoration', 'underline')
        elif attr_char == 'i':
            check_property('font-style', 'italic')

        if attr_char in digits:
            number_str = string[next_attr_char +
                                1:string.find('}', next_attr_char)]
            number = int(number_str)
            if number in number_to_color_names:
                check_property('color',
                               number_to_color_names.get(number, 'black'))
            else:
                check_property('color', ncurses_color_to_html(number))
            string = string[next_attr_char + len(number_str) + 2:]
        else:
            string = string[next_attr_char + 2:]
        next_attr_char = string.find('\x19')

    if current_attrs and not tag_open and string:
        build.append('<span style="%s">' % format_inline_css(current_attrs))
        tag_open = True
    build.append(saxutils.escape(string))
    if tag_open:
        build.append('</span>')
    build.append("</p></body>")
    text = ''.join(build)
    return text.replace('\n', '<br />')
