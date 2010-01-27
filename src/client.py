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
from connection import Connection
from multiuserchat import MultiUserChat
from config import config
from handler import Handler
from gui import Gui
from curses import wrapper, initscr

if len(sys.argv) == 1:          # not debug, so hide any error message and disable C-c
    import signal
    sys.stderr = open('/dev/null', 'a')
    signal.signal(signal.SIGINT, signal.SIG_IGN)

class Client(object):
    """
    Main class
    Just read some configuration and instantiate the classes
    """
    def __init__(self):
        self.handler = Handler()

        self.resource = config.get('resource', 'poezio')
        self.server = config.get('server', 'louiz.org')
        self.connection = Connection(self.server, self.resource)

        self.stdscr = initscr()
        self.connection.start()
        self.gui = Gui(self.stdscr, MultiUserChat(self.connection.client))

def main():
    client = Client()
    client.gui.main_loop(client.stdscr)
    sys.exit()

if __name__ == '__main__':
    main()
