"""
Test the functions in the `logger` module
"""

import pytest
from poezio.logger import LogInfo, LogMessage, parse_message_line

def test_parse_message():
    line = 'MR 20170909T09:09:09Z 000 <nick>  body'
    assert vars(parse_message_line(line)) == vars(LogMessage('2017', '09', '09', '09', '09', '09', '0', 'nick', 'body'))

    line = '<>'
    assert parse_message_line(line) == None

    line = 'MR 20170908T07:05:04Z 003 <nick>  '
    assert vars(parse_message_line(line)) == vars(LogMessage('2017', '09', '08', '07', '05', '04', '003', 'nick', ''))
