# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GPL-3.0+ license. See the COPYING file.
"""
The logger module that handles logging of the poezio
conversations and roster changes
"""

import mmap
import re
from typing import List, Dict, Optional, IO, Any, Union, Generator
from datetime import datetime
from pathlib import Path

from poezio import common
from poezio.config import config
from poezio.xhtml import clean_text
from poezio.ui.types import Message, BaseMessage, LoggableTrait
from slixmpp import JID
from poezio.types import TypedDict

import logging

log = logging.getLogger(__name__)

MESSAGE_LOG_RE = re.compile(r'^MR (\d{4})(\d{2})(\d{2})T'
                            r'(\d{2}):(\d{2}):(\d{2})Z '
                            r'(\d+) <([^ ]+)>  (.*)$')
INFO_LOG_RE = re.compile(r'^MI (\d{4})(\d{2})(\d{2})T'
                         r'(\d{2}):(\d{2}):(\d{2})Z '
                         r'(\d+) (.*)$')


class LogItem:
    time: datetime
    nb_lines: int
    text: str

    def __init__(self, year: str, month: str, day: str, hour: str, minute: str,
                 second: str, nb_lines: str,
                 message: str):
        self.time = datetime(
            int(year), int(month), int(day), int(hour), int(minute),
            int(second))
        self.nb_lines = int(nb_lines)
        self.text = message


class LogInfo(LogItem):
    def __init__(self, *args):
        LogItem.__init__(self, *args)


class LogMessage(LogItem):
    nick: str

    def __init__(self, year: str, month: str, day: str, hour: str, minute: str,
                 seconds: str, nb_lines: str, nick: str,
                 message: str):
        LogItem.__init__(self, year, month, day, hour, minute, seconds,
                         nb_lines, message)
        self.nick = nick


LogDict = TypedDict(
    'LogDict',
    {
        'type': str, 'txt': str, 'time': datetime,
        'history': bool, 'nickname': str
    },
    total=False,
)


def parse_log_line(msg: str, jid: str = '') -> Optional[LogItem]:
    """Parse a log line.

    :param msg: The message ligne
    :param jid: jid (for error logging)
    :returns: The LogItem or None on error
    """
    match = MESSAGE_LOG_RE.match(msg)
    if match:
        return LogMessage(*match.groups())
    match = INFO_LOG_RE.match(msg)
    if match:
        return LogInfo(*match.groups())
    log.debug('Error while parsing %s’s logs: “%s”', jid, msg)
    return None


class Logger:
    """
    Appends things to files. Error/information/warning logs
    and also log the conversations to logfiles
    """
    _roster_logfile: Optional[IO[str]]
    log_dir: Path
    _fds: Dict[str, IO[str]]
    _busy_fds: Dict[str, bool]

    def __init__(self):
        self.log_dir = Path()
        self._roster_logfile = None
        # a dict of 'groupchatname': file-object (opened)
        self._fds = {}
        self._busy_fds = {}
        self._buffered_fds = {}

    def __del__(self):
        """Close all fds on exit"""
        for opened_file in self._fds.values():
            if opened_file:
                try:
                    opened_file.close()
                except Exception:  # Can't close? too bad
                    pass
        try:
            self._roster_logfile.close()
        except Exception:
            pass

    def get_file_path(self, jid: Union[str, JID]) -> Path:
        """Return the log path for a specific jid"""
        jidstr = str(jid).replace('/', '\\')
        return self.log_dir / jidstr

    def fd_busy(self, jid: Union[str, JID]) -> None:
        """Signal to the logger that this logfile is busy elsewhere.
        And that the messages should be queued to be logged later.

        :param jid: file name
        """
        jidstr = str(jid).replace('/', '\\')
        self._busy_fds[jidstr] = True
        if jidstr not in self._buffered_fds:
            self._buffered_fds[jidstr] = []

    def fd_available(self, jid: Union[str, JID]) -> None:
        """Signal to the logger that this logfile is no longer busy.
        And write messages to the end.

        :param jid: file name
        """
        jidstr = str(jid).replace('/', '\\')
        if jidstr in self._busy_fds:
            del self._busy_fds[jidstr]
        if jidstr in self._buffered_fds:
            msgs = ''.join(self._buffered_fds.pop(jidstr))
            if jidstr in self._fds:
                self._fds[jidstr].close()
                del self._fds[jidstr]
            self.log_raw(jid, msgs)

    def close(self, jid: str) -> None:
        """Close the log file for a JID."""
        jidstr = str(jid).replace('/', '\\')
        if jidstr in self._fds:
            self._fds[jidstr].close()
            log.debug('Log file for %s closed.', jid)
            del self._fds[jidstr]

    def reload_all(self) -> None:
        """Close and reload all the file handles (on SIGHUP)"""
        not_closed = set()
        for key, opened_file in self._fds.items():
            if opened_file:
                try:
                    opened_file.close()
                except Exception:
                    not_closed.add(key)
        if self._roster_logfile:
            try:
                self._roster_logfile.close()
            except Exception:
                not_closed.add('roster')
        log.debug('All log file handles closed')
        if not_closed:
            log.error('Unable to close log files for: %s', not_closed)
        for room in self._fds:
            self._check_and_create_log_dir(room)
            log.debug('Log handle for %s re-created', room)

    def _check_and_create_log_dir(self, jid: str,
                                  open_fd: bool = True) -> Optional[IO[str]]:
        """
        Check that the directory where we want to log the messages
        exists. if not, create it

        :param jid: JID of the file to open after creating the dir
        :param open_fd: if the file should be opened after creating the dir
        :returns: the opened fd or None
        """
        if not config.get_by_tabname('use_log', JID(jid)):
            return None
        # POSIX filesystems don't support / in filename, so we replace it with a backslash
        jid = str(jid).replace('/', '\\')
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.error('Unable to create the log dir', exc_info=True)
        except Exception:
            log.error('Unable to create the log dir', exc_info=True)
            return None
        if not open_fd:
            return None
        filename = self.get_file_path(jid)
        try:
            fd = filename.open('a', encoding='utf-8')
            self._fds[jid] = fd
            return fd
        except IOError:
            log.error(
                'Unable to open the log file (%s)', filename, exc_info=True)
        return None

    def log_message(self,
                    jid: str,
                    msg: Union[BaseMessage, Message]) -> bool:
        """
        Log the message in the appropriate file

        :param jid: JID of the entity for which to log the message
        :param msg: Message to log
        :returns: True if no error was encountered
        """
        if not config.get_by_tabname('use_log', JID(jid)):
            return True
        if not isinstance(msg, LoggableTrait):
            return True
        date = msg.time
        txt = msg.txt
        nick = ''
        typ = 'MI'
        if isinstance(msg, Message):
            nick = msg.nickname or ''
            if msg.me:
                txt = f'/me {txt}'
            typ = 'MR'
        logged_msg = build_log_message(nick, txt, date=date, prefix=typ)
        if not logged_msg:
            return True
        return self.log_raw(jid, logged_msg)

    def log_raw(self, jid: Union[str, JID], logged_msg: str, force: bool = False) -> bool:
        """Log a raw string.

        :param jid: filename
        :param logged_msg: string to log
        :param force: Bypass the buffered fd check
        :returns: True if no error was encountered
        """
        jidstr = str(jid).replace('/', '\\')
        if jidstr in self._fds.keys():
            fd = self._fds[jidstr]
        else:
            option_fd = self._check_and_create_log_dir(jid)
            if option_fd is None:
                return True
            fd = option_fd
        filename = self.get_file_path(jid)
        try:
            if not force and self._busy_fds.get(jidstr):
                self._buffered_fds[jidstr].append(logged_msg)
                return True
            fd.write(logged_msg)
        except OSError:
            log.error(
                'Unable to write in the log file (%s)',
                filename,
                exc_info=True)
            return False
        else:
            try:
                fd.flush()  # TODO do something better here?
            except OSError:
                log.error(
                    'Unable to flush the log file (%s)',
                    filename,
                    exc_info=True)
                return False
        return True

    def log_roster_change(self, jid: str, message: str) -> bool:
        """
        Log a roster change

        :param jid: jid to log the change for
        :param message: message to log
        :returns: True if no error happened
        """
        if not config.get_by_tabname('use_log', JID(jid)):
            return True
        self._check_and_create_log_dir('', open_fd=False)
        filename = self.log_dir / 'roster.log'
        if not self._roster_logfile:
            try:
                self._roster_logfile = filename.open('a', encoding='utf-8')
            except IOError:
                log.error(
                    'Unable to create the log file (%s)',
                    filename,
                    exc_info=True)
                return False
        try:
            str_time = common.get_utc_time().strftime('%Y%m%dT%H:%M:%SZ')
            message = clean_text(message)
            lines = message.split('\n')
            first_line = lines.pop(0)
            nb_lines = str(len(lines)).zfill(3)
            self._roster_logfile.write(
                'MI %s %s %s %s\n' % (str_time, nb_lines, jid, first_line))
            for line in lines:
                self._roster_logfile.write(' %s\n' % line)
            self._roster_logfile.flush()
        except Exception:
            log.error(
                'Unable to write in the log file (%s)',
                filename,
                exc_info=True)
            return False
        return True


def build_log_message(nick: str,
                      msg: str,
                      date: Optional[datetime] = None,
                      prefix: str = 'MI') -> str:
    """
    Create a log message from a nick, a message, optionally a date and type

    :param nick: nickname to log
    :param msg: text of the message
    :param date: date of the message
    :param prefix: MI (info) or MR (message)
    :returns: The log line(s)
    """
    msg = clean_text(msg)
    time = common.get_utc_time() if date is None else common.get_utc_time(date)
    str_time = time.strftime('%Y%m%dT%H:%M:%SZ')
    lines = msg.split('\n')
    first_line = lines.pop(0)
    nb_lines = str(len(lines)).zfill(3)
    if nick:
        nick = '<' + nick + '>'
        logged_msg = '%s %s %s %s  %s\n' % (prefix, str_time, nb_lines, nick,
                                            first_line)
    else:
        logged_msg = '%s %s %s %s\n' % (prefix, str_time, nb_lines, first_line)
    return logged_msg + ''.join(' %s\n' % line for line in lines)


def last_message_in_archive(filepath: Path) -> Optional[LogDict]:
    """Get the last message from the local archive.

    :param filepath: the log file path
    """
    last_msg = None
    for msg in iterate_messages_reverse(filepath):
        if msg['type'] == 'message':
            last_msg = msg
            break
    return last_msg


def iterate_messages_reverse(filepath: Path) -> Generator[LogDict, None, None]:
    """Get the latest messages from the log file, one at a time.

    :param fd: the file descriptor
    """
    try:
        with open(filepath, 'rb') as fd:
            with mmap.mmap(fd.fileno(), 0, prot=mmap.PROT_READ) as m:
                # start of messages begin with MI or MR, after a \n
                pos = m.rfind(b"\nM") + 1
                if pos != -1:
                    lines = parse_log_lines(
                        m[pos:-1].decode(errors='replace').splitlines()
                    )
                elif m[0:1] == b'M':
                    # Handle the case of a single message present in the log
                    # file, hence no newline.
                    lines = parse_log_lines(
                        m[:].decode(errors='replace').splitlines()
                    )
                if lines:
                    yield lines[0]
                while pos > 0:
                    old_pos = pos
                    pos = m.rfind(b"\nM", 0, pos) + 1
                    lines = parse_log_lines(
                        m[pos:old_pos].decode(errors='replace').splitlines()
                    )
                    if lines:
                        yield lines[0]
    except (OSError, ValueError):
        pass


def parse_log_lines(lines: List[str], jid: str = '') -> List[LogDict]:
    """
    Parse raw log lines into poezio log objects

    :param lines: Message lines
    :param jid: jid (for error logging)
    :return: a list of dicts containing message info
    """
    messages = []

    # now convert that data into actual Message objects
    idx = 0
    while idx < len(lines):
        if lines[idx].startswith(' '):  # should not happen ; skip
            idx += 1
            log.debug('fail?')
            continue
        log_item = parse_log_line(lines[idx], jid)
        idx += 1
        if not isinstance(log_item, LogItem):
            log.debug('wrong log format? %s', log_item)
            continue
        message_lines = []
        message = LogDict({
            'history': True,
            'time': common.get_local_time(log_item.time),
            'type': 'message',
        })
        size = log_item.nb_lines
        if isinstance(log_item, LogInfo):
            message_lines.append(log_item.text)
            message['type'] = 'info'
        elif isinstance(log_item, LogMessage):
            message['nickname'] = log_item.nick
            message_lines.append(log_item.text)
        while size != 0 and idx < len(lines):
            message_lines.append(lines[idx][1:])
            size -= 1
            idx += 1
        message['txt'] = '\n'.join(message_lines)
        messages.append(message)
    return messages


logger = Logger()
