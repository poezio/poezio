"""
Test the functions in the `xhtml` module
"""

import pytest
import xml
import poezio.xhtml
from poezio.xhtml import (poezio_colors_to_html, xhtml_to_poezio_colors,
                   _parse_css as parse_css, clean_text)

class ConfigShim(object):
    def __init__(self):
        self.value = True
    def get(self, *args, **kwargs):
        return self.value

config = ConfigShim()
poezio.xhtml.config = config

def test_clean_text():
    example_string = '\x191}Toto \x192,-1}titi\x19b Tata'
    assert clean_text(example_string) == 'Toto titi Tata'

    clean_string = 'toto titi tata'
    assert clean_text(clean_string) == clean_string

def test_poezio_colors_to_html():
    base = "<body xmlns='http://www.w3.org/1999/xhtml'><p>"
    end = "</p></body>"
    text = '\x191}coucou'
    assert poezio_colors_to_html(text) == base + '<span style="color: red;">coucou</span>' + end

    text = '\x19bcoucou\x19o toto \x194}titi'
    assert poezio_colors_to_html(text) == base + '<span style="font-weight: bold;">coucou</span> toto <span style="color: blue;">titi</span>' + end

    text = '\x19icoucou'
    assert poezio_colors_to_html(text) == base + '<span style="font-style: italic;">coucou</span>' + end

def test_xhtml_to_poezio_colors():
    start = b'<body xmlns="http://www.w3.org/1999/xhtml"><p>'
    end = b'</p></body>'
    xhtml = start + b'test' + end
    assert xhtml_to_poezio_colors(xhtml) == 'test'

    xhtml = start + b'<a href="http://perdu.com">salut</a>' + end
    assert xhtml_to_poezio_colors(xhtml) == '\x19usalut\x19o (http://perdu.com)'

    xhtml = start + b'<a href="http://perdu.com">http://perdu.com</a>' + end
    assert xhtml_to_poezio_colors(xhtml) == '\x19uhttp://perdu.com\x19o'

    xhtml = start + b'<span style="font-style: italic">Test</span>' + end
    assert xhtml_to_poezio_colors(xhtml) == '\x19iTest\x19o'

    xhtml = b'<div style="font-weight:bold">Allo <div style="color:red">test <div style="color: blue">test2</div></div></div>'
    assert xhtml_to_poezio_colors(xhtml, force=True) == '\x19bAllo \x19196}test \x1921}test2\x19o'

    xhtml = (b'<div style="color:blue"><div style="color:yellow">'
             b'<div style="color:blue">Allo <div style="color:red">'
             b'test <div style="color: blue">test2</div></div></div></div></div>')
    assert xhtml_to_poezio_colors(xhtml, force=True) == '\x1921}Allo \x19196}test \x1921}test2\x19o'

    with pytest.raises(xml.sax._exceptions.SAXParseException):
        xhtml_to_poezio_colors(b'<p>Invalid xml')

def test_xhtml_to_poezio_colors_disabled():
    config.value = False
    start = b'<body xmlns="http://www.w3.org/1999/xhtml"><p>'
    end = b'</p></body>'
    xhtml = start + b'test' + end
    assert xhtml_to_poezio_colors(xhtml) == 'test'

    xhtml = start + b'<a href="http://perdu.com">salut</a>' + end
    assert xhtml_to_poezio_colors(xhtml) == '\x19usalut\x19o (http://perdu.com)'

    xhtml = start + b'<a href="http://perdu.com">http://perdu.com</a>' + end
    assert xhtml_to_poezio_colors(xhtml) == '\x19uhttp://perdu.com\x19o'

    xhtml = b'<div style="font-weight:bold">Allo <div style="color:red">test <div style="color: blue">test2</div></div></div>'
    assert xhtml_to_poezio_colors(xhtml, force=True) == 'Allo test test2'

    xhtml = (b'<div style="color:blue"><div style="color:yellow">'
             b'<div style="color:blue">Allo <div style="color:red">'
             b'test <div style="color: blue">test2</div></div></div></div></div>')
    assert xhtml_to_poezio_colors(xhtml, force=True) == 'Allo test test2'

    config.value = True

def test_parse_css():
    example_css = 'text-decoration: underline; color: red;'
    assert parse_css(example_css) == '\x19u\x19196}'

    example_css = 'text-decoration: underline coucou color: red;'
    assert parse_css(example_css) == ''
