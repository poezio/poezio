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

import common
from config import config
from xhtml import clean_text
from theming import dump_tuple, get_theme

import logging

log = logging.getLogger(__name__)

from config import LOG_DIR as log_dir

message_log_re = re.compile(r'MR (\d{4})(\d{2})(\d{2})T'
                            r'(\d{2}):(\d{2}):(\d{2})Z '
                            r'(\d+) <([^ ]+)>  (.*)')
info_log_re = re.compile(r'MI (\d{4})(\d{2})(\d{2})T'
                         r'(\d{2}):(\d{2}):(\d{2})Z '
                         r'(\d+) (.*)')

def parse_message_line(msg):
    if re.match(message_log_re, msg):
        return [i for i in re.split(message_log_re, msg) if i]
    elif re.match(info_log_re, msg):
        return [i for i in re.split(info_log_re, msg) if i]
    return False


class Logger(object):
    """
    Appends things to files. Error/information/warning logs
    and also log the conversations to logfiles
    """
    def __init__(self):
        self.logfile = config.get('logfile')
        self.roster_logfile = None
        # a dict of 'groupchatname': file-object (opened)
        self.fds = dict()

    def __del__(self):
        for opened_file in self.fds.values():
            if opened_file:
                try:
                    opened_file.close()
                except: # Can't close? too bad
                    pass

    def reload_all(self):
        """Close and reload all the file handles (on SIGHUP)"""
        for opened_file in self.fds.values():
            if opened_file:
                opened_file.close()
        log.debug('All log file handles closed')
        for room in self.fds:
            self.fds[room] = self.check_and_create_log_dir(room)
            log.debug('Log handle for %s re-created', room)

    def check_and_create_log_dir(self, room, open_fd=True):
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
            self.fds[room] = fd
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

        self.check_and_create_log_dir(jid, open_fd=False)

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
            tup = parse_message_line(lines[idx])
            idx += 1
            if not tup or 7 > len(tup) > 10: # skip
                log.debug('format? %s', tup)
                continue
            time = [int(i) for index, i in enumerate(tup) if index < 6]
            message = {'lines': [],
                       'history': True,
                       'time': common.get_local_time(datetime(*time))}
            size = int(tup[6])
            if len(tup) == 8: #info line
                message['lines'].append(color+tup[7])
            else: # message line
                message['nickname'] = tup[7]
                message['lines'].append(color+tup[8])
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
        if jid in self.fds.keys():
            fd = self.fds[jid]
        else:
            fd = self.check_and_create_log_dir(jid)
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
        self.check_and_create_log_dir('', open_fd=False)
        if not self.roster_logfile:
            try:
                self.roster_logfile = open(os.path.join(log_dir, 'roster.log'), 'a')
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
            self.roster_logfile.write('MI %s %s %s %s\n' % (str_time, nb_lines, jid, first_line))
            for line in lines:
                self.roster_logfile.write(' %s\n' % line)
            self.roster_logfile.flush()
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
