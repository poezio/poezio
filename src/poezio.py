#!/usr/bin/env python3
#
# Copyright 2010 Le Coz Florent <louiz@louiz.org>
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
import curses
import sys
import traceback
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def installThreadExcepthook():
    """
    Workaround for sys.excepthook thread bug
    See http://bugs.python.org/issue1230540
    Python, you made me sad :(
    """
    init_old = threading.Thread.__init__
    def init(self, *args, **kwargs):
        init_old(self, *args, **kwargs)
        run_old = self.run
        def run_with_except_hook(*args, **kw):
            try:
                run_old(*args, **kw)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                sys.excepthook(*sys.exc_info())
        self.run = run_with_except_hook
    threading.Thread.__init__ = init

class MyStdErr(object):
    def __init__(self, fd):
        """
        Change sys.stderr to something like /dev/null
        to disable any printout on the screen that would
        mess everything
        """
        self.old_stderr = sys.stderr
        sys.stderr = fd
    def restore(self):
        """
        Restore the good ol' sys.stderr, because we need
        it in order to print the tracebacks
        """
        sys.stderr.close()
        sys.stderr = self.old_stderr

# my_stderr = MyStdErr(open('/dev/null', 'a'))

def exception_handler(type_, value, trace):
    """
    on any traceback: exit ncurses and print the traceback
    then exit the program
    """
    my_stderr.restore()
    try:
        curses.endwin()
        curses.echo()
    except: # if an exception is raised but initscr has never been called yet
        pass
    traceback.print_exception(type_, value, trace, None, sys.stderr)
    import os                   # used to quit the program even from a thread
    os.abort()

# sys.excepthook = exception_handler

import signal
import logging

from connection import connection
from config import config, options
from core import core

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_IGN) # ignore ctrl-c
    if options.debug:
        logging.basicConfig(filename=options.debug,level=logging.DEBUG)
    connection.start()  # Connect to remote server
    core.main_loop()    # Refresh the screen, wait for user events etc
