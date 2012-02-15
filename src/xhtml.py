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

import re
import subprocess
import curses
from sleekxmpp.xmlstream import ET

import xml.sax.saxutils

from xml.etree.ElementTree import ElementTree

from sys import version_info

from config import config
import logging

digits = '0123456789' # never trust the modules
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
}

log = logging.getLogger(__name__)

whitespace_re = re.compile(r'\s+')

xhtml_attr_re = re.compile(r'\x19\d{0,3}\}|\x19[buaio]')

xhtml_simple_attr_re = re.compile(r'\x19\d')

def get_body_from_message_stanza(message):
    """
    Returns a string with xhtml markups converted to
    poezio colors if there's an xhtml_im element, or
    the body (without any color) otherwise
    """
    if config.get('enable_xhtml_im', 'true') == 'true':
        xhtml_body = message['xhtml_im']
        if xhtml_body:
            content = xhtml_to_poezio_colors(xhtml_body)
            content = content if content else message['body']
            return content or " "
    return message['body']

def ncurses_color_to_html(color):
    """
    Takes an int between 0 and 256 and returns
    a string of the form #XXXXXX representing an
    html color.
    """
    if color <= 15:
        (r, g, b) = curses.color_content(color)
        r = r / 1000 * 6 - 0.01
        g = g / 1000 * 6 - 0.01
        b = b / 1000 * 6 - 0.01
    elif color <= 231:
        color = color - 16
        r = color % 6
        color = color / 6
        g = color % 6
        color = color / 6
        b = color % 6
    else:
        color -= 232
        r = g = b = color / 24 * 6
    return '#%02X%02X%02X' % (r*256/6, g*256/6, b*256/6)

def xhtml_to_poezio_colors(text):
    def parse_css(css):
        def get_color(value):
            if value[0] == '#':
                value = value[1:]
                length = len(value)
                if length != 3 and length != 6:
                    return -1
                value = int(value, 16)
                if length == 6:
                    r = int(value >> 16)
                    g = int((value >> 8) & 0xff)
                    b = int(value & 0xff)
                    if r == g == b:
                        return 232 + int(r/10.6251)
                    div = 42.51
                else:
                    r = int(value >> 8)
                    g = int((value >> 4) & 0xf)
                    b = int(value & 0xf)
                    if r == g == b:
                        return 232 + int(1.54*r)
                    div = 2.51
                return 6*6*int(r/div) + 6*int(g/div) + int(b/div) + 16
            if value in colors:
                return colors[value]
            return -1
        shell = ''
        rules = css.split(';')
        for rule in rules:
            if ':' not in rule:
                continue
            key, value = rule.split(':', 1)
            key = key.strip()
            value = value.strip()
            if key == 'background-color':
                pass#shell += '\x191'
            elif key == 'color':
                color = get_color(value)
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

    def trim(string):
        return re.sub(whitespace_re, ' ', string)

    xml = ET.fromstring(text)
    message = ''
    if version_info[1] == 2:
        elems = xml.iter()
    else:
        elems = xml.getiterator()
    for elem in elems:
        if elem.tag == '{http://www.w3.org/1999/xhtml}a':
            if 'href' in elem.attrib and elem.attrib['href'] != elem.text:
                message += '\x19u%s\x19o (%s)' % (trim(elem.attrib['href']), trim(elem.text if elem.text else ""))
            else:
                message += '\x19u' + (elem.text if elem.text else "") + '\x19o'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}blockquote':
            message += '“'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}body':
            pass
        elif elem.tag == '{http://www.w3.org/1999/xhtml}br':
            message += '\n'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}cite':
            message += '\x19u'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}em':
            message += '\x19i'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}img' and 'src' in elem.attrib:
            if 'alt' in elem.attrib:
                message += '%s (%s)' % (trim(elem.attrib['src']), trim(elem.attrib['alt']))
            else:
                message += elem.attrib['src']
        elif elem.tag == '{http://www.w3.org/1999/xhtml}li':
            pass
        elif elem.tag == '{http://www.w3.org/1999/xhtml}ol':
            pass
        elif elem.tag == '{http://www.w3.org/1999/xhtml}p':
            pass
        elif elem.tag == '{http://www.w3.org/1999/xhtml}span':
            pass
        elif elem.tag == '{http://www.w3.org/1999/xhtml}strong':
            message += '\x19b'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}ul':
            pass

        if ('style' in elem.attrib and elem.tag != '{http://www.w3.org/1999/xhtml}br'
                                   and elem.tag != '{http://www.w3.org/1999/xhtml}em'
                                   and elem.tag != '{http://www.w3.org/1999/xhtml}strong'):
            message += parse_css(elem.attrib['style'])

        if (elem.text and elem.tag != '{http://www.w3.org/1999/xhtml}a'
                      and elem.tag != '{http://www.w3.org/1999/xhtml}br'
                      and elem.tag != '{http://www.w3.org/1999/xhtml}img'):
            message += trim(elem.text)

        if ('style' in elem.attrib and elem.tag != '{http://www.w3.org/1999/xhtml}br'
                                   and elem.tag != '{http://www.w3.org/1999/xhtml}em'
                                   and elem.tag != '{http://www.w3.org/1999/xhtml}strong'):
            message += '\x19o'

        if elem.tag == '{http://www.w3.org/1999/xhtml}blockquote':
            message += '”'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}cite':
            message += '\x19o'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}em':
            message += '\x19o'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}strong' or elem.tag == '{http://www.w3.org/1999/xhtml}b':
            message += '\x19o'
        elif elem.tag == '{http://www.w3.org/1999/xhtml}u':
            message += '\x19o'

        if 'title' in elem.attrib:
            message += ' [' + elem.attrib['title'] + ']'

        if elem.tail:
            message += trim(elem.tail)
    return message

def clean_text(s):
    """
    Remove all xhtml-im attributes (\x19etc) from the string with the
    complete color format, i.e \x19xxx}
    """
    s = re.sub(xhtml_attr_re, "", s)
    return s

def clean_text_simple(string):
    """
    Remove all \x19 from the string formatted with simple colors:
    \x198
    """
    pos = string.find('\x19')
    while pos != -1:
        string = string[:pos] + string[pos+2:]
        pos = string.find('\x19')
    return string

def convert_simple_to_full_colors(text):
    """
    takes a \x19n formatted string and returns
    a \x19n} formatted one.
    """
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
}

def poezio_colors_to_html(string):
    """
    Convert poezio colors to html makups
    (e.g. \x191: <span style='color: red'>)
    """
    # TODO underlined

    # a list of all opened elements, e.g. ['strong', 'span']
    # So that we know what we need to close
    opened_elements = []
    res = "<body xmlns='http://www.w3.org/1999/xhtml'><p>"
    next_attr_char = string.find('\x19')
    while next_attr_char != -1:
        attr_char = string[next_attr_char+1].lower()
        if next_attr_char != 0:
            res += xml.sax.saxutils.escape(string[:next_attr_char])
        if attr_char == 'o':
            for elem in opened_elements[::-1]:
                res += '</%s>' % (elem,)
            opened_elements = []
        elif attr_char == 'b':
            if 'strong' not in opened_elements:
                opened_elements.append('strong')
                res += '<strong>'
        if attr_char in digits:
            number_str = string[next_attr_char+1:string.find('}', next_attr_char)]
            number = int(number_str)
            if 'strong' in opened_elements:
                res += '</strong>'
                opened_elements.remove('strong')
            if 'span' in opened_elements:
                res += '</span>'
            else:
                opened_elements.append('span')
            res += "<span style='color: %s'>" % (ncurses_color_to_html(number),)
            string = string[next_attr_char+len(number_str)+2:]
        else:
            string = string[next_attr_char+2:]
        next_attr_char = string.find('\x19')
    res += xml.sax.saxutils.escape(string)
    for elem in opened_elements[::-1]:
        res += '</%s>' % (elem,)
    res += "</p></body>"
    return res.replace('\n', '<br />')
