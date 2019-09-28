import pytest
from contextlib import contextmanager
from datetime import datetime
from poezio.theming import get_theme
from poezio.ui.render import build_lines, Line, write_pre
from poezio.ui.consts import SHORT_FORMAT
from poezio.ui.types import BaseMessage, Message, XMLLog

def test_simple_build_basemsg():
    msg = BaseMessage(txt='coucou')
    line = build_lines(msg, 100, True, 10)[0]
    assert (line.start_pos, line.end_pos) == (0, 6)


def test_simple_render_message():
    msg = Message(txt='coucou', nickname='toto')
    line = build_lines(msg, 100, True, 10)[0]
    assert (line.start_pos, line.end_pos) == (0, 8)


def test_simple_render_xmllog():
    msg = XMLLog(txt='coucou', incoming=True)
    line = build_lines(msg, 100, True, 10)[0]
    assert (line.start_pos, line.end_pos) == (0, 6)


def test_simple_render_separator():
    line = build_lines(None, 100, True, 10)[0]
    assert line is None

class FakeBuffer:
    def __init__(self):
        self.text = ''

    @contextmanager
    def colored_text(self, *args, **kwargs):
        yield None

    def addstr(self, txt):
        self.text += txt

@pytest.fixture(scope='function')
def buffer():
    return FakeBuffer()

@pytest.fixture
def time():
    return datetime.strptime('2019-09-27 10:11:12', '%Y-%m-%d %H:%M:%S')

def test_write_pre_basemsg(buffer):
    str_time = '10:11:12'
    time = datetime.strptime(str_time, '%H:%M:%S')
    msg = BaseMessage(txt='coucou', time=time)

    write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 '

def test_write_pre_message_simple(buffer, time):
    msg = Message(txt='coucou', nickname='toto', time=time)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 toto> '


def test_write_pre_message_simple_history(buffer, time):
    msg = Message(txt='coucou', nickname='toto', time=time, history=True)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == '2019-09-27 10:11:12 toto> '


def test_write_pre_message_highlight(buffer, time):
    msg = Message(txt='coucou', nickname='toto', time=time, highlight=True)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 toto> '

def test_write_pre_message_no_timestamp(buffer):
    msg = Message(txt='coucou', nickname='toto')
    write_pre(msg, buffer, False, 10)
    assert buffer.text == 'toto> '


def test_write_pre_message_me(buffer, time):
    msg = Message(txt='/me coucou', nickname='toto', time=time)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 * toto '


def test_write_pre_message_revisions(buffer, time):
    msg = Message(txt='coucou', nickname='toto', time=time, revisions=5)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 toto5> '


def test_write_pre_message_revisions_me(buffer, time):
    msg = Message(txt='/me coucou', nickname='toto', time=time, revisions=5)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 * toto5 '


def test_write_pre_message_ack(buffer, time):
    ack = get_theme().CHAR_ACK_RECEIVED
    expected = '10:11:12 %s toto> ' % ack
    msg = Message(txt='coucou', nickname='toto', time=time, ack=1)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == expected


def test_write_pre_message_nack(buffer, time):
    nack = get_theme().CHAR_NACK
    expected = '10:11:12 %s toto> ' % nack
    msg = Message(txt='coucou', nickname='toto', time=time, ack=-1)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == expected


def test_write_pre_xmllog_in(buffer):
    msg = XMLLog(txt="coucou", incoming=True)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == '%s IN  ' % msg.time.strftime('%H:%M:%S')


def test_write_pre_xmllog_out(buffer):
    msg = XMLLog(txt="coucou", incoming=False)
    write_pre(msg, buffer, True, 10)
    assert buffer.text == '%s OUT ' % msg.time.strftime('%H:%M:%S')
