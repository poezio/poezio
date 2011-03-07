#!/usr/bin/env python3
#
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

"""
Starting point of poezio. Launches both the Connection and Gui
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import signal
import logging

from config import options
import singleton
import core

def main():
    """
    Enter point
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN) # ignore ctrl-c
    if options.debug:
        logging.basicConfig(filename=options.debug, level=logging.DEBUG)
    cocore = singleton.Singleton(core.Core)
    cocore.start()
    if not cocore.xmpp.start():  # Connect to remote server
        cocore.on_failed_connection()
    cocore.main_loop()    # Refresh the screen, wait for user events etc

if __name__ == '__main__':
    main()
