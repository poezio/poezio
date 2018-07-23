# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.
"""
The logger module that handles logging of the poezio
conversations and roster changes
"""

import mmap
import re
from typing import List, Dict, Optional, IO, Any
from datetime import datetime

from poezio import common
from poezio.config import config
from poezio.xhtml import clean_text
from poezio.theming import dump_tuple, get_theme

import logging

log = logging.getLogger(__name__)

from poezio.config import LOG_DIR as log_dir

MESSAGE_LOG_RE = re.compile(r'^MR (\d{4})(\d{2})(\d{2})T'
                            r'(\d{2}):(\d{2}):(\d{2})Z '
                            r'(\d+) <([^ ]+)>  (.*)$')
INFO_LOG_RE = re.compile(r'^MI (\d{4})(\d{2})(\d{2})T'
                         r'(\d{2}):(\d{2}):(\d{2})Z '
                         r'(\d+) (.*)$')


class LogItem:
    def __init__(self, year, month, day, hour, minute, second, nb_lines,
                 message):
        self.time = datetime(
            int(year), int(month), int(day), int(hour), int(minute),
            int(second))
        self.nb_lines = int(nb_lines)
        self.text = message


class LogInfo(LogItem):
    def __init__(self, *args):
        LogItem.__init__(self, *args)


class LogMessage(LogItem):
    def __init__(self, year, month, day, hour, minute, seconds, nb_lines, nick,
                 message):
        LogItem.__init__(self, year, month, day, hour, minute, seconds,
                         nb_lines, message)
        self.nick = nick


def parse_log_line(msg):
    match = re.match(MESSAGE_LOG_RE, msg)
    if match:
        return LogMessage(*match.groups())
    match = re.match(INFO_LOG_RE, msg)
    if match:
        return LogInfo(*match.groups())
    log.debug('Error while parsing "%s"', msg)
    return None


class Logger:
    """
    Appends things to files. Error/information/warning logs
    and also log the conversations to logfiles
    """

    def __init__(self):
        self._roster_logfile = None  # Optional[IO[Any]]
        # a dict of 'groupchatname': file-object (opened)
        self._fds = {}  # type: Dict[str, IO[Any]]

    def __del__(self):
        for opened_file in self._fds.values():
            if opened_file:
                try:
                    opened_file.close()
                except:  # Can't close? too bad
                    pass

    def close(self, jid) -> None:
        jid = str(jid).replace('/', '\\')
        if jid in self._fds:
            self._fds[jid].close()
            log.debug('Log file for %s closed.', jid)
            del self._fds[jid]
        return None

    def reload_all(self) -> None:
        """Close and reload all the file handles (on SIGHUP)"""
        for opened_file in self._fds.values():
            if opened_file:
                opened_file.close()
        log.debug('All log file handles closed')
        for room in self._fds:
            self._check_and_create_log_dir(room)
            log.debug('Log handle for %s re-created', room)
        return None

    def _check_and_create_log_dir(self, room: str,
                                  open_fd: bool = True) -> Optional[IO[Any]]:
        """
        Check that the directory where we want to log the messages
        exists. if not, create it
        """
        if not config.get_by_tabname('use_log', room):
            return None
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.error('Unable to create the log dir', exc_info=True)
        except:
            log.error('Unable to create the log dir', exc_info=True)
            return None
        if not open_fd:
            return None
        filename = log_dir / room
        try:
            fd = filename.open('a', encoding='utf-8')
            self._fds[room] = fd
            return fd
        except IOError:
            log.error(
                'Unable to open the log file (%s)', filename, exc_info=True)
        return None

    def get_logs(self, jid: str,
                 nb: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Get the nb last messages from the log history for the given jid.
        Note that a message may be more than one line in these files, so
        this function is a little bit more complicated than “read the last
        nb lines”.
        """
        if config.get_by_tabname('load_log', jid) <= 0:
            return None

        if not config.get_by_tabname('use_log', jid):
            return None

        if nb <= 0:
            return None

        self._check_and_create_log_dir(jid, open_fd=False)

        filename = log_dir / jid
        try:
            fd = filename.open('rb')
        except FileNotFoundError:
            log.info('Non-existing log file (%s)', filename, exc_info=True)
            return None
        except OSError:
            log.error(
                'Unable to open the log file (%s)', filename, exc_info=True)
            return None
        if not fd:
            return None

        # read the needed data from the file, we just search nb messages by
        # searching "\nM" nb times from the end of the file.  We use mmap to
        # do that efficiently, instead of seek()s and read()s which are costly.
        with fd:
            try:
                lines = get_lines_from_fd(fd, nb=nb)
            except Exception:  # file probably empty
                log.error(
                    'Unable to mmap the log file for (%s)',
                    filename,
                    exc_info=True)
                return None
        return parse_log_lines(lines)

    def log_message(self,
                    jid: str,
                    nick: str,
                    msg: str,
                    date: Optional[datetime] = None,
                    typ: int = 1) -> bool:
        """
        log the message in the appropriate jid's file
        type:
              0 = Don’t log
              1 = Message
              2 = Status/whatever
        """
        if not config.get_by_tabname('use_log', jid):
            return True
        logged_msg = build_log_message(nick, msg, date=date, typ=typ)
        if not logged_msg:
            return True
        if jid in self._fds.keys():
            fd = self._fds[jid]
        else:
            option_fd = self._check_and_create_log_dir(jid)
            if option_fd is None:
                return True
            fd = option_fd
        filename = log_dir / jid
        try:
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
        """
        if not config.get_by_tabname('use_log', jid):
            return True
        self._check_and_create_log_dir('', open_fd=False)
        filename = log_dir / 'roster.log'
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
        except:
            log.error(
                'Unable to write in the log file (%s)',
                filename,
                exc_info=True)
            return False
        return True


def build_log_message(nick: str,
                      msg: str,
                      date: Optional[datetime] = None,
                      typ: int = 1) -> str:
    """
    Create a log message from a nick, a message, optionally a date and type
    message types:
        0 = Don’t log
        1 = Message
        2 = Status/whatever
    """
    if not typ:
        return ''

    msg = clean_text(msg)
    time = common.get_utc_time() if date is None else common.get_utc_time(date)
    str_time = time.strftime('%Y%m%dT%H:%M:%SZ')
    prefix = 'MR' if typ == 1 else 'MI'
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


def get_lines_from_fd(fd: IO[Any], nb: int = 10) -> List[str]:
    """
    Get the last log lines from a fileno
    """
    with mmap.mmap(fd.fileno(), 0, prot=mmap.PROT_READ) as m:
        pos = m.rfind(b"\nM")  # start of messages begin with MI or MR,
        # after a \n
        # number of message found so far
        count = 0
        while pos != -1 and count < nb - 1:
            count += 1
            pos = m.rfind(b"\nM", 0, pos)
        if pos == -1:  # If we don't have enough lines in the file
            pos = 1  # 1, because we do -1 just on the next line
            # to get 0 (start of the file)
        lines = m[pos - 1:].decode(errors='replace').splitlines()
    return lines


def parse_log_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Parse raw log lines into poezio log objects
    """
    messages = []
    color = '\x19%s}' % dump_tuple(get_theme().COLOR_LOG_MSG)

    # now convert that data into actual Message objects
    idx = 0
    while idx < len(lines):
        if lines[idx].startswith(' '):  # should not happen ; skip
            idx += 1
            log.debug('fail?')
            continue
        log_item = parse_log_line(lines[idx])
        idx += 1
        if not isinstance(log_item, LogItem):
            log.debug('wrong log format? %s', log_item)
            continue
        message = {
            'lines': [],
            'history': True,
            'time': common.get_local_time(log_item.time)
        }
        size = log_item.nb_lines
        if isinstance(log_item, LogInfo):
            message['lines'].append(color + log_item.text)
        elif isinstance(log_item, LogMessage):
            message['nickname'] = log_item.nick
            message['lines'].append(color + log_item.text)
        while size != 0 and idx < len(lines):
            message['lines'].append(lines[idx][1:])
            size -= 1
            idx += 1
        message['txt'] = '\n'.join(message['lines'])
        del message['lines']
        messages.append(message)
    return messages


def create_logger() -> None:
    "Create the global logger object"
    global logger
    logger = Logger()


logger = None  # type: Optional[Logger]
