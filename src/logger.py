# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

from os import environ, makedirs
import os
from datetime import datetime
from config import config
from xhtml import clean_text

import logging

log = logging.getLogger(__name__)

DATA_HOME = config.get('log_dir', '') or os.path.join(environ.get('XDG_DATA_HOME') or os.path.join(environ.get('HOME'), '.local', 'share'), 'poezio')
DATA_HOME = os.path.expanduser(DATA_HOME)

class Logger(object):
    """
    Appends things to files. Error/information/warning logs
    and also log the conversations to logfiles
    """
    def __init__(self):
        self.logfile = config.get('logfile', 'logs')
        self.roster_logfile = None
        # a dict of 'groupchatname': file-object (opened)
        self.fds = dict()

    def __del__(self):
        for opened_file in self.fds.values():
            if opened_file:
                opened_file.close()

    def reload_all(self):
        """Close and reload all the file handles (on SIGHUP)"""
        for opened_file in self.fds.values():
            if opened_file:
                opened_file.close()
        log.debug('All log file handles closed')
        for room in self.fds:
            self.fds[room] = self.check_and_create_log_dir(room)
            log.debug('Log handle for %s re-created', room)

    def check_and_create_log_dir(self, room):
        """
        Check that the directory where we want to log the messages
        exists. if not, create it
        """
        if config.get('use_log', 'false') == 'false':
            return None
        directory = os.path.join(DATA_HOME, 'logs')
        try:
            makedirs(directory)
        except OSError:
            pass
        try:
            fd = open(os.path.join(directory, room), 'a')
            self.fds[room] = fd
            return fd
        except IOError:
            return None

    def log_message(self, jid, nick, msg):
        """
        log the message in the appropriate jid's file
        """
        if jid in self.fds.keys():
            fd = self.fds[jid]
        else:
            fd = self.check_and_create_log_dir(jid)
        if not fd:
            return
        try:
            msg = clean_text(msg)
            if nick:
                fd.write(datetime.now().strftime('%d-%m-%y [%H:%M:%S] ')+nick+': '+msg+'\n')
            else:
                fd.write(datetime.now().strftime('%d-%m-%y [%H:%M:%S] ')+'* '+msg+'\n')
        except IOError:
            pass
        else:
            fd.flush()          # TODO do something better here?

    def log_roster_change(self, jid, message):
        if not self.roster_logfile:
            try:
                self.roster_logfile = open(os.path.join(DATA_HOME, 'logs', 'roster.log'), 'a')
            except IOError:
                return
        self.roster_logfile.write('%s %s %s\n' % (datetime.now().strftime('%d-%m-%y [%H:%M:%S]'), jid, message))
        self.roster_logfile.flush()

logger = Logger()
