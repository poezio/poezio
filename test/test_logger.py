"""
Test the functions in the `logger` module
"""

from poezio.logger import LogMessage, parse_log_line

def test_parse_message():
    line = 'MR 20170909T09:09:09Z 000 <nick>  body'
    assert vars(parse_log_line(line)) == vars(LogMessage('2017', '09', '09', '09', '09', '09', '0', 'nick', 'body'))

    line = '<>'
    assert parse_log_line(line) == None

    line = 'MR 20170908T07:05:04Z 003 <nick>  '
    assert vars(parse_log_line(line)) == vars(LogMessage('2017', '09', '08', '07', '05', '04', '003', 'nick', ''))
