# Copyright 2010-2011 Le Coz Florent <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

import sys
from os import environ, makedirs
import os
from datetime import datetime
from config import config
from xhtml import clean_text

import logging

log = logging.getLogger(__name__)

DATA_HOME = config.get('log_dir', '') or os.path.join(environ.get('XDG_DATA_HOME') or os.path.join(environ.get('HOME'), '.local', 'share'), 'poezio')

class Logger(object):
    """
    Appends things to files. Error/information/warning logs
    and also log the conversations to logfiles
    """
    def __init__(self):
        self.logfile = config.get('logfile', 'logs')
        # a dict of 'groupchatname': file-object (opened)
        self.fds = dict()

    def __del__(self):
        for opened_file in self.fds.values():
            opened_file.close()

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

logger = Logger()
