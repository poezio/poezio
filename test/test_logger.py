"""
Test the functions in the `logger` module
"""
import datetime
from poezio.logger import LogMessage, parse_log_line, parse_log_lines, build_log_message
from poezio.common import get_utc_time, get_local_time

def test_parse_message():
    line = 'MR 20170909T09:09:09Z 000 <nick>  body'
    assert vars(parse_log_line(line)) == vars(LogMessage('2017', '09', '09', '09', '09', '09', '0', 'nick', 'body'))

    line = '<>'
    assert parse_log_line(line) is None

    line = 'MR 20170908T07:05:04Z 003 <nick>  '
    assert vars(parse_log_line(line)) == vars(LogMessage('2017', '09', '08', '07', '05', '04', '003', 'nick', ''))


def test_log_and_parse_messages():
    msg1 = {'nick': 'toto', 'msg': 'coucou', 'date': datetime.datetime.now().replace(microsecond=0)}
    msg1_utc = get_utc_time(msg1['date'])
    built_msg1 = build_log_message(**msg1)
    assert built_msg1 == 'MR %s 000 <toto>  coucou\n' % (msg1_utc.strftime('%Y%m%dT%H:%M:%SZ'))

    msg2 = {'nick': 'toto', 'msg': 'coucou\ncoucou', 'date': datetime.datetime.now().replace(microsecond=0)}
    built_msg2 = build_log_message(**msg2)
    msg2_utc = get_utc_time(msg2['date'])
    assert built_msg2 == 'MR %s 001 <toto>  coucou\n coucou\n' % (msg2_utc.strftime('%Y%m%dT%H:%M:%SZ'))

    assert parse_log_lines((built_msg1 + built_msg2).split('\n')) == [
        {'time': msg1['date'], 'history': True, 'txt': '\x195,-1}coucou', 'nickname': 'toto'},
        {'time': msg2['date'], 'history': True, 'txt': '\x195,-1}coucou\ncoucou', 'nickname': 'toto'},
    ]
