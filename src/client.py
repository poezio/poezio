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
# disable any printout (this would mess the display)
stderr = sys.stderr
# sys.stdout = open('/dev/null', 'w')
# sys.stderr = open('/dev/null', 'w')

from connection import Connection
from multiuserchat import MultiUserChat
from config import config
from handler import Handler
from gui import Gui
from curses import initscr
import curses

import signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

import traceback

def exception_handler(type_, value, trace):
    """
    on any traceback: exit ncurses and print the traceback
    then exit the program
    """
    curses.echo()
    curses.endwin()
    traceback.print_exception(type_, value, trace, None, stderr)
    sys.exit()

sys.excepthook = exception_handler

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

    def launch(self):
        """
        launch
        """
        self.gui.main_loop(self.stdscr)

def main():
    """
    main function
    """
    client = Client()
    client.launch()
    sys.exit()

if __name__ == '__main__':
    main()
