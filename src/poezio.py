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

import threading
import sys
import traceback

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
    def restaure(self):
        """
        Restaure the good ol' sys.stderr, because we need
        it in order to print the tracebacks
        """
        sys.stderr = self.old_stderr

my_stderr = MyStdErr(open('/dev/null', 'a'))

def exception_handler(type_, value, trace):
    """
    on any traceback: exit ncurses and print the traceback
    then exit the program
    """
    my_stderr.restaure()
    curses.endwin()
    curses.echo()
    traceback.print_exception(type_, value, trace, None, sys.stderr)
    import os                   # used to quit the program even from a thread
    os.abort()

sys.excepthook = exception_handler

import sys
import curses
import signal

from connection import Connection
from multiuserchat import MultiUserChat
from config import config
from gui import Gui
from curses import initscr

signal.signal(signal.SIGINT, signal.SIG_IGN) # ignore ctrl-c

def main():
    """
    main function
    """
    resource = config.get('resource', 'poezio')
    server = config.get('server', 'anon.louiz.org:jeproteste.info')
    connection = Connection(server, resource)
    connection.start()
    stdscr = initscr()
    gui = Gui(stdscr, MultiUserChat(connection.client))
    gui.main_loop(stdscr)

if __name__ == '__main__':
    installThreadExcepthook()
    main()
