"""
Test the functions in the `logger` module
"""
import datetime
from pathlib import Path
from random import sample
from shutil import rmtree
from string import hexdigits
from poezio import logger
from poezio.logger import (
    LogMessage, parse_log_line, parse_log_lines, build_log_message
)
from poezio.ui.types import Message
from poezio.common import get_utc_time
import pytest


class ConfigShim:
    def __init__(self, value):
        self.value = value

    def get_by_tabname(self, name, *args, **kwargs):
        return self.value


logger.config = ConfigShim(True)


@pytest.fixture
def log_dir():
    name = 'tmplog-' + ''.join(sample(hexdigits, 16))
    path = Path('/tmp', name)
    try:
        yield path
    finally:
        rmtree(path, ignore_errors=True)


def read_file(logger, name):
    if '/' in name:
        name = name.replace('/', '\\')
    filename = logger.log_dir / f'{name}'
    with open(filename) as fd:
        return fd.read()


def test_log_roster(log_dir):
    instance = logger.Logger()
    instance.log_dir = log_dir
    instance.log_roster_change('toto@example.com', 'test test')
    content = read_file(instance, 'roster.log')
    assert content[:3] == 'MI '
    assert content[-32:] == ' 000 toto@example.com test test\n'


def test_log_message(log_dir):
    instance = logger.Logger()
    instance.log_dir = log_dir
    msg = Message('content', 'toto')
    instance.log_message('toto@example.com', msg)
    content = read_file(instance, 'toto@example.com')
    line = parse_log_lines(content.split('\n'), '')[0]
    assert line['nickname'] == 'toto'
    assert line['txt'] == 'content'
    msg2 = Message('content\ncontent2', 'titi')
    instance.log_message('toto@example.com', msg2)
    content = read_file(instance, 'toto@example.com')
    lines = parse_log_lines(content.split('\n'), '')

    assert lines[0]['nickname'] == 'toto'
    assert lines[0]['txt'] == 'content'
    assert lines[1]['nickname'] == 'titi'
    assert lines[1]['txt'] == 'content\ncontent2'


def test_parse_message():
    line = 'MR 20170909T09:09:09Z 000 <nick>  body'
    assert vars(parse_log_line(line, 'user@domain')) == vars(LogMessage('2017', '09', '09', '09', '09', '09', '0', 'nick', 'body'))

    line = '<>'
    assert parse_log_line(line, 'user@domain') is None

    line = 'MR 20170908T07:05:04Z 003 <nick>  '
    assert vars(parse_log_line(line, 'user@domain')) == vars(LogMessage('2017', '09', '08', '07', '05', '04', '003', 'nick', ''))


def test_log_and_parse_messages():
    msg1 = {
        'nick': 'toto',
        'msg': 'coucou',
        'date': datetime.datetime.now().replace(microsecond=0),
        'prefix': 'MR',
    }
    msg1_utc = get_utc_time(msg1['date'])
    built_msg1 = build_log_message(**msg1)
    assert built_msg1 == 'MR %s 000 <toto>  coucou\n' % (msg1_utc.strftime('%Y%m%dT%H:%M:%SZ'))

    msg2 = {
        'nick': 'toto',
        'msg': 'coucou\ncoucou',
        'date': datetime.datetime.now().replace(microsecond=0),
        'prefix': 'MR',
    }
    built_msg2 = build_log_message(**msg2)
    msg2_utc = get_utc_time(msg2['date'])
    assert built_msg2 == 'MR %s 001 <toto>  coucou\n coucou\n' % (msg2_utc.strftime('%Y%m%dT%H:%M:%SZ'))

    assert parse_log_lines((built_msg1 + built_msg2).split('\n'), 'user@domain') == [
            {'time': msg1['date'], 'history': True, 'txt': 'coucou', 'nickname': 'toto', 'type': 'message'},
        {'time': msg2['date'], 'history': True, 'txt': 'coucou\ncoucou', 'nickname': 'toto', 'type': 'message'},
    ]
