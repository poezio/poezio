import pytest
from contextlib import contextmanager
from datetime import datetime
from poezio.theming import get_theme
from poezio.ui.render import build_lines, Line, write_pre
from poezio.ui.consts import SHORT_FORMAT
from poezio.ui.types import BaseMessage, Message, StatusMessage, XMLLog

def test_simple_build_basemsg():
    msg = BaseMessage(txt='coucou')
    line = build_lines(msg, 100, True, 10)[0]
    assert (line.start_pos, line.end_pos) == (0, 6)


def test_simple_render_message():
    msg = Message(txt='coucou', nickname='toto')
    line = build_lines(msg, 100, True, 10)[0]
    assert (line.start_pos, line.end_pos) == (0, 6)


def test_simple_render_xmllog():
    msg = XMLLog(txt='coucou', incoming=True)
    line = build_lines(msg, 100, True, 10)[0]
    assert (line.start_pos, line.end_pos) == (0, 6)


def test_simple_render_separator():
    line = build_lines(None, 100, True, 10)[0]
    assert line is None


def test_simple_render_status():
    class Obj:
        name = 'toto'
    msg = StatusMessage("Coucou {name}", {'name': lambda: Obj.name})
    assert msg.txt == "Coucou toto"
    Obj.name = 'titi'
    build_lines(msg, 100, True, 10)[0]
    assert msg.txt == "Coucou titi"


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
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 '
    assert size == len(buffer.text)

def test_write_pre_message_simple(buffer, time):
    msg = Message(txt='coucou', nickname='toto', time=time)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 toto> '
    assert size == len(buffer.text)


def test_write_pre_message_simple_history(buffer, time):
    msg = Message(txt='coucou', nickname='toto', time=time, history=True)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == '2019-09-27 10:11:12 toto> '
    assert size == len(buffer.text)


def test_write_pre_message_highlight(buffer, time):
    msg = Message(txt='coucou', nickname='toto', time=time, highlight=True)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 toto> '
    assert size == len(buffer.text)

def test_write_pre_message_no_timestamp(buffer):
    msg = Message(txt='coucou', nickname='toto')
    size = write_pre(msg, buffer, False, 10)
    assert buffer.text == 'toto> '
    assert size == len(buffer.text)


def test_write_pre_message_me(buffer, time):
    msg = Message(txt='/me coucou', nickname='toto', time=time)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 * toto '
    assert size == len(buffer.text)


def test_write_pre_message_revisions(buffer, time):
    msg = Message(txt='coucou', nickname='toto', time=time, revisions=5)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 toto5> '
    assert size == len(buffer.text)

def test_write_pre_message_revisions_me(buffer, time):
    msg = Message(txt='/me coucou', nickname='toto', time=time, revisions=5)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == '10:11:12 * toto5 '
    assert size == len(buffer.text)


def test_write_pre_message_ack(buffer, time):
    ack = get_theme().CHAR_ACK_RECEIVED
    expected = '10:11:12 %s toto> ' % ack
    msg = Message(txt='coucou', nickname='toto', time=time, ack=1)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == expected
    assert size == len(buffer.text)


def test_write_pre_message_nack(buffer, time):
    nack = get_theme().CHAR_NACK
    expected = '10:11:12 %s toto> ' % nack
    msg = Message(txt='coucou', nickname='toto', time=time, ack=-1)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == expected
    assert size == len(buffer.text)


def test_write_pre_xmllog_in(buffer):
    msg = XMLLog(txt="coucou", incoming=True)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == '%s IN  ' % msg.time.strftime('%H:%M:%S')
    assert size == len(buffer.text)


def test_write_pre_xmllog_out(buffer):
    msg = XMLLog(txt="coucou", incoming=False)
    size = write_pre(msg, buffer, True, 10)
    assert buffer.text == '%s OUT ' % msg.time.strftime('%H:%M:%S')
    assert size == len(buffer.text)
