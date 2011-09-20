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
from sleekxmpp.xmlstream import ET
from xml.etree.ElementTree import ElementTree
from sys import version_info

from config import config
import logging

digits = '0123456789' # never trust the modules

log = logging.getLogger(__name__)

shell_colors_re = re.compile(r'(\[(?:\d+;)*(?:\d+m))')
start_indent_re = re.compile(r'\[0;30m\[0;37m   ')
newline_indent_re = re.compile('\n\[0;37m   ')

def get_body_from_message_stanza(message):
    """
    Returns a string with xhtml markups converted to
    poezio colors if there's an xhtml_im element, or
    the body (without any color) otherwise
    """
    if config.get('enable_xhtml_im', 'true') == 'true':
        xhtml_body = message['xhtml_im']
        if xhtml_body:
            return xhtml_to_poezio_colors(xhtml_body)
    return message['body']


def xhtml_to_poezio_colors(text):
    def parse_css(css):
        def get_color(string):
            if value == 'black':
                return 0
            if value == 'red':
                return 1
            if value == 'green':
                return 2
            if value == 'yellow':
                return 3
            if value == 'blue':
                return 4
            if value == 'magenta':
                return 5
            if value == 'cyan':
                return 6
            if value == 'white':
                return 7
            if value == 'default':
                return 8
        shell = ''
        rules = css.split(';')
        for rule in rules:
            key, value = rule.split(':', 1)
            key = key.strip()
            value = value.strip()
            log.debug(value)
            if key == 'background-color':
                pass#shell += '\x191'
            elif key == 'color':
                shell += '\x19%d' % get_color(value)
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

    log.debug(text)
    xml = ET.fromstring(text)
    message = ''
    for elem in xml.iter():
        if elem.tag == '{http://www.w3.org/1999/xhtml}a':
            if 'href' in elem.attrib and elem.attrib['href'] != elem.text:
                message += '\x19u%s\x19o (%s)' % (elem.attrib['href'], elem.text)
            else:
                message += '\x19u' + elem.text + '\x19o'
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
            if elem.attrib['alt']:
                message += '%s (%s)' % (elem.attrib['src'], elem.attrib['alt'])
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
            message += elem.text

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
            message += elem.tail
    return message


def clean_text(string):
    """
    Remove all \x19 from the string
    """
    pos = string.find('\x19')
    while pos != -1:
        string = string[:pos] + string[pos+2:]
        pos = string.find('\x19')
    return string

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
            res += string[:next_attr_char]
        string = string[next_attr_char+2:]
        if attr_char == 'o':
            for elem in opened_elements[::-1]:
                res += '</%s>' % (elem,)
            opened_elements = []
        elif attr_char == 'b':
            if 'strong' not in opened_elements:
                opened_elements.append('strong')
                res += '<strong>'
        elif attr_char in digits:
            number = int(attr_char)
            if number in number_to_color_names:
                if 'strong' in opened_elements:
                    res += '</strong>'
                    opened_elements.remove('strong')
                if 'span' in opened_elements:
                    res += '</span>'
                else:
                    opened_elements.append('span')
                res += "<span style='color: %s'>" % (number_to_color_names[number])
        next_attr_char = string.find('\x19')
    res += string
    for elem in opened_elements[::-1]:
        res += '</%s>' % (elem,)
    res += "</p></body>"
    return res.replace('\n', '<br />')


def poezio_colors_to_xhtml(string):
    """
    Generate a valid xhtml string from
    the poezio colors in the given string
    """
    res = "<body xmlns='http://www.w3.org/1999/xhtml'>"
    next_attr_char = string.find('\x19')
    open_elements = []
    while next_attr_char != -1:
        attr_char = string[next_attr_char+1].lower()
        if next_attr_char != 0:
            res += string[:next_attr_char]
        string = string[next_attr_char+2:]
        if attr_char == 'o':
            # close all opened elements
            for elem in open_elements:
                res += '</%s>'
            open_elements = []
        elif attr_char == 'b':
            if 'strong' not in open_elements:
                res += '<strong>'
                open_elements.append('strong')
        elif attr_char in digits:
            self._win.attron(common.curses_color_pair(int(attr_char)))
        next_attr_char = string.find('\x19')


