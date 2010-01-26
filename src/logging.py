#!/usr/bin/python
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
from datetime import datetime
from config import config
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

logger = Logger()
