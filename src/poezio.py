#!/usr/bin/env python3
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

import os
# chdir in the source directory, so that import are never failed
# also, no need to use a sh script to "cd" in this directoy
# before launching poezio.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import curses
import sys
import traceback

class MyStdErr(object):
    def __init__(self, fd):
        """
        Change sys.stderr to something like /dev/null
        to disable any printout on the screen that would
        mess everything
        """
        self.old_stderr = sys.stderr
        sys.stderr = fd
    def restaure(self):
        """
        Restaure the good ol' sys.stderr, because we need
        it in order to print the tracebacks
        """
        sys.stderr.close()
        sys.stderr = self.old_stderr

my_stderr = MyStdErr(open('/dev/null', 'a'))

def exception_handler(type_, value, trace):
    """
    on any traceback: exit ncurses and print the traceback
    then exit the program
    """
    my_stderr.restaure()
    try:
        curses.endwin()
        curses.echo()
    except: # if an exception is raised but initscr has never been called yet
        pass
    traceback.print_exception(type_, value, trace, None, sys.stderr)
    # import os                   # used to quit the program even from a thread
    # os.abort()

sys.excepthook = exception_handler

import signal

from connection import Connection
from config import config
from gui import Gui

signal.signal(signal.SIGINT, signal.SIG_IGN) # ignore ctrl-c

def main():
    """
    The main function consist of the Connection initialization
    then the gui (ncurses) init, connection handlers and then the
    connection is "started"
    """
    xmpp = Connection()         # Connection init
    gui = Gui(xmpp)             # Gui init.
    xmpp.start()                # Connect to remote server
    gui.main_loop()             # Refresh the screen, wait for user events etc

if __name__ == '__main__':
    if os.environ['TERM'] != 'screen':
        os.environ['TERM'] = 'xterm-256color' # FIXME
    main()
