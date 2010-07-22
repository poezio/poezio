# -*- coding:utf-8 -*-
#
# Copyright 2010 Le Coz Florent <louizatakk@fedoraproject.org>
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
from datetime import datetime
from config import config

DATA_HOME = config.get('log_dir', environ.get("XDG_DATA_HOME"))
if not DATA_HOME:
    DATA_HOME = environ.get('HOME')+'/.local/share'
DATA_PATH = DATA_HOME + '/poezio/'

class Logger(object):
    """
    Appends things to files. Error/information/warning logs
    and also log the conversations to logfiles
    """
    def __init__(self):# , logfile, loglevel):
        self.logfile = config.get('logfile', 'logs')
        self.loglevel = config.get('loglevel', 3)
        # self.logfile = logfile
        # self.loglevel = loglevel

    def info(self, msg):
        if self.logfile and self.loglevel >= 3:
            fd = open(self.logfile, 'a')
            fd.write(datetime.now().strftime("%H:%M:%S") + ' Info [' + msg + ']\n')
            fd.close()

    def warning(self, msg):
        if self.logfile and self.loglevel >= 2:
            fd = open(self.logfile, 'a')
            fd.write(datetime.now().strftime("%H:%M:%S") + ' Warning [' + msg + ']\n')
            fd.close()

    def error(self, msg):
        if self.logfile and self.loglevel >= 1:
            fd = open(self.logfile, 'a')
            fd.write(datetime.now().strftime("%H:%M:%S") + ' Error [' + msg + ']\n')
            fd.close()
        sys.exit(-1)

    def message(self, room, nick, msg):
        """
        log the message in the appropriate room
        """
        if config.get('use_log', 'false') == 'false':
            return
        dir = DATA_PATH+'logs/'
        try:
            makedirs(dir)
        except OSError:
            pass
        try:
            fd = open(dir+room, 'a')
        except IOError:
            return
        if nick:
            fd.write(datetime.now().strftime('%d-%m-%y [%H:%M:%S] ')+nick.encode('utf-8')+': '+msg.encode('utf-8')+'\n')
        else:
            fd.write(datetime.now().strftime('%d-%m-%y [%H:%M:%S] ')+'* '+msg.encode('utf-8')+'\n')
        fd.close()

logger = Logger()
