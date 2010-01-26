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

from config import config
import sys
from datetime import datetime

class Logger(object):
    """
    Appends things to files. Error/information/warning logs
    and also log the conversations to logfiles
    """
    def __init__(self):
        self.logfile = config.get('logfile')

    def warning(self, msg):
        if self.logfile:
            fd = open(self.logfile, 'a')
            fd.write(datetime.now().strftime("%H:%M:%S") + ' Warning [' + msg + ']')
            fd.close()

    def error(self, msg):
        if self.logfile:
            fd = open(self.logfile, 'a')
            fd.write(datetime.now().strftime("%H:%M:%S") + ' Error [' + msg + ']')
            fd.close()
        sys.exit(-1)

logger = Logger()
