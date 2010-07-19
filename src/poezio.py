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

"""
Starting point of poezio. Launches both the Connection and Gui
"""

import sys
import traceback
import curses
from common import MyStdErr, exception_handler

sys.excepthook = exception_handler

from connection import Connection
from multiuserchat import MultiUserChat
from config import config
from gui import Gui
from curses import initscr

import signal
signal.signal(signal.SIGINT, signal.SIG_IGN) # ignore ctrl-c

def main():
    """
    main function
    """
    resource = config.get('resource', 'poezio')
    server = config.get('server', 'louiz.org')
    connection = Connection(server, resource)
    connection.start()
    stdscr = initscr()
    gui = Gui(stdscr, MultiUserChat(connection.client))
    gui.main_loop(stdscr)

if __name__ == '__main__':
    main()
