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
import os
import re
from os import makedirs
from datetime import datetime

from poezio import common
from poezio.config import config
from poezio.xhtml import clean_text
from poezio.theming import dump_tuple, get_theme

import logging

log = logging.getLogger(__name__)

from poezio.config import LOG_DIR as log_dir

MESSAGE_LOG_RE = re.compile(r'MR (\d{4})(\d{2})(\d{2})T'
                            r'(\d{2}):(\d{2}):(\d{2})Z '
                            r'(\d+) <([^ ]+)>  (.*)')
INFO_LOG_RE = re.compile(r'MI (\d{4})(\d{2})(\d{2})T'
                         r'(\d{2}):(\d{2}):(\d{2})Z '
                         r'(\d+) (.*)')

class LogItem:
    def __init__(self, year, month, day, hour, minute, second, nb_lines, message):
        self.time = datetime(int(year), int(month), int(day), int(hour),
                             int(minute), int(second))
        self.nb_lines = int(nb_lines)
        self.text = message

class LogInfo(LogItem):
    def __init__(self, *args):
        LogItem.__init__(self, *args)

class LogMessage(LogItem):
    def __init__(self, year, month, day, hour, minute, seconds, nb_lines, nick, message):
        LogItem.__init__(self, year, month, day, hour, minute, seconds,
                         nb_lines, message)
        self.nick = nick

def parse_message_line(msg):
    if re.match(MESSAGE_LOG_RE, msg):
        return LogMessage(*[i for i in re.split(MESSAGE_LOG_RE, msg) if i])
    if re.match(INFO_LOG_RE, msg):
        return LogInfo(*[i for i in re.split(INFO_LOG_RE, msg) if i])
    return None

class Logger(object):
    """
    Appends things to files. Error/information/warning logs
    and also log the conversations to logfiles
    """
    def __init__(self):
        self._roster_logfile = None
        # a dict of 'groupchatname': file-object (opened)
        self._fds = {}

    def __del__(self):
        for opened_file in self._fds.values():
            if opened_file:
                try:
                    opened_file.close()
                except: # Can't close? too bad
                    pass

    def close(self, jid):
        jid = str(jid).replace('/', '\\')
        if jid in self._fds:
            self._fds[jid].close()
            log.debug('Log file for %s closed.', jid)
            del self._fds[jid]

    def reload_all(self):
        """Close and reload all the file handles (on SIGHUP)"""
        for opened_file in self._fds.values():
            if opened_file:
                opened_file.close()
        log.debug('All log file handles closed')
        for room in self._fds:
            self._fds[room] = self._check_and_create_log_dir(room)
            log.debug('Log handle for %s re-created', room)

    def _check_and_create_log_dir(self, room, open_fd=True):
        """
        Check that the directory where we want to log the messages
        exists. if not, create it
        """
        if not config.get_by_tabname('use_log', room):
            return
        try:
            makedirs(log_dir)
        except OSError as e:
            if e.errno != 17: # file exists
                log.error('Unable to create the log dir', exc_info=True)
        except:
            log.error('Unable to create the log dir', exc_info=True)
            return
        if not open_fd:
            return
        try:
            fd = open(os.path.join(log_dir, room), 'a')
            self._fds[room] = fd
            return fd
        except IOError:
            log.error('Unable to open the log file (%s)',
                    os.path.join(log_dir, room),
                    exc_info=True)

    def get_logs(self, jid, nb=10):
        """
        Get the nb last messages from the log history for the given jid.
        Note that a message may be more than one line in these files, so
        this function is a little bit more complicated than “read the last
        nb lines”.
        """
        if config.get_by_tabname('load_log', jid) <= 0:
            return

        if not config.get_by_tabname('use_log', jid):
            return

        if nb <= 0:
            return

        self._check_and_create_log_dir(jid, open_fd=False)

        try:
            fd = open(os.path.join(log_dir, jid), 'rb')
        except FileNotFoundError:
            log.info('Non-existing log file (%s)',
                     os.path.join(log_dir, jid),
                     exc_info=True)
            return
        except OSError:
            log.error('Unable to open the log file (%s)',
                      os.path.join(log_dir, jid),
                      exc_info=True)
            return
        if not fd:
            return

        # read the needed data from the file, we just search nb messages by
        # searching "\nM" nb times from the end of the file.  We use mmap to
        # do that efficiently, instead of seek()s and read()s which are costly.
        with fd:
            try:
                m = mmap.mmap(fd.fileno(), 0, prot=mmap.PROT_READ)
            except Exception: # file probably empty
                log.error('Unable to mmap the log file for (%s)',
                        os.path.join(log_dir, jid),
                        exc_info=True)
                return
            pos = m.rfind(b"\nM") # start of messages begin with MI or MR,
                                  # after a \n
            # number of message found so far
            count = 0
            while pos != -1 and count < nb-1:
                count += 1
                pos = m.rfind(b"\nM", 0, pos)
            if pos == -1:       # If we don't have enough lines in the file
                pos = 1         # 1, because we do -1 just on the next line
                                # to get 0 (start of the file)
            lines = m[pos-1:].decode(errors='replace').splitlines()

        messages = []
        color = '\x19%s}' % dump_tuple(get_theme().COLOR_LOG_MSG)

        # now convert that data into actual Message objects
        idx = 0
        while idx < len(lines):
            if lines[idx].startswith(' '): # should not happen ; skip
                idx += 1
                log.debug('fail?')
                continue
            log_item = parse_message_line(lines[idx])
            idx += 1
            if not isinstance(log_item, LogItem):
                log.debug('wrong log format? %s', log_item)
                continue
            message = {'lines': [],
                       'history': True,
                       'time': common.get_local_time(log_item.time)}
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

    def log_message(self, jid, nick, msg, date=None, typ=1):
        """
        log the message in the appropriate jid's file
        type:
              0 = Don’t log
              1 = Message
              2 = Status/whatever
        """
        if not typ:
            return True

        jid = str(jid).replace('/', '\\')
        if not config.get_by_tabname('use_log', jid):
            return True
        if jid in self._fds.keys():
            fd = self._fds[jid]
        else:
            fd = self._check_and_create_log_dir(jid)
        if not fd:
            return True
        try:
            msg = clean_text(msg)
            if date is None:
                str_time = common.get_utc_time().strftime('%Y%m%dT%H:%M:%SZ')
            else:
                str_time = common.get_utc_time(date).strftime('%Y%m%dT%H:%M:%SZ')
            if typ == 1:
                prefix = 'MR'
            else:
                prefix = 'MI'
            lines = msg.split('\n')
            first_line = lines.pop(0)
            nb_lines = str(len(lines)).zfill(3)

            if nick:
                nick = '<' + nick + '>'
                fd.write(' '.join((prefix, str_time, nb_lines, nick, ' '+first_line, '\n')))
            else:
                fd.write(' '.join((prefix, str_time, nb_lines, first_line, '\n')))
            for line in lines:
                fd.write(' %s\n' % line)
        except:
            log.error('Unable to write in the log file (%s)',
                    os.path.join(log_dir, jid),
                    exc_info=True)
            return False
        else:
            try:
                fd.flush()          # TODO do something better here?
            except:
                log.error('Unable to flush the log file (%s)',
                        os.path.join(log_dir, jid),
                        exc_info=True)
                return False
        return True

    def log_roster_change(self, jid, message):
        """
        Log a roster change
        """
        if not config.get_by_tabname('use_log', jid):
            return True
        self._check_and_create_log_dir('', open_fd=False)
        if not self._roster_logfile:
            try:
                self._roster_logfile = open(os.path.join(log_dir, 'roster.log'), 'a')
            except IOError:
                log.error('Unable to create the log file (%s)',
                        os.path.join(log_dir, 'roster.log'),
                        exc_info=True)
                return False
        try:
            str_time = common.get_utc_time().strftime('%Y%m%dT%H:%M:%SZ')
            message = clean_text(message)
            lines = message.split('\n')
            first_line = lines.pop(0)
            nb_lines = str(len(lines)).zfill(3)
            self._roster_logfile.write('MI %s %s %s %s\n' % (str_time, nb_lines, jid, first_line))
            for line in lines:
                self._roster_logfile.write(' %s\n' % line)
            self._roster_logfile.flush()
        except:
            log.error('Unable to write in the log file (%s)',
                    os.path.join(log_dir, 'roster.log'),
                    exc_info=True)
            return False
        return True

def create_logger():
    "Create the global logger object"
    global logger
    logger = Logger()

logger = None
