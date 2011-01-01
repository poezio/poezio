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

DATA_HOME = config.get('log_dir', os.path.join(environ.get('XDG_DATA_HOME') or os.path.join(environ.get('HOME'), '.local', 'share'), 'poezio'))

class Logger(object):
    """
    Appends things to files. Error/information/warning logs
    and also log the conversations to logfiles
    """
    def __init__(self):# , logfile, loglevel):
        self.logfile = config.get('logfile', 'logs')

    def groupchat(self, room, nick, msg):
        """
        log the message in the appropriate room's file
        """
        if config.get('use_log', 'false') == 'false':
            return
        dir = DATA_HOME+'logs/'
        try:
            makedirs(dir)
        except OSError:
            pass
        try:
            fd = open(dir+room, 'a')
        except IOError:
            return
        msg = msg
        if nick:
            fd.write(datetime.now().strftime('%d-%m-%y [%H:%M:%S] ')+nick+': '+msg+'\n')
        else:
            fd.write(datetime.now().strftime('%d-%m-%y [%H:%M:%S] ')+'* '+msg+'\n')
        fd.close()

logger = Logger()
