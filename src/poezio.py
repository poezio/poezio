# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.


"""
Starting point of poezio. Launches both the Connection and Gui
"""

import sys
import os

import signal
import logging.config

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import options
from logger import logger
import singleton
import core

log = logging.getLogger('')

def main():
    """
    Enter point
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN) # ignore ctrl-c
    cocore = singleton.Singleton(core.Core)
    signal.signal(signal.SIGUSR1, cocore.sigusr_handler) # reload the config
    signal.signal(signal.SIGHUP, cocore.exit_from_signal)
    signal.signal(signal.SIGTERM, cocore.exit_from_signal)
    signal.signal(signal.SIGPIPE, cocore.exit_from_signal)
    if options.debug:
        cocore.debug = True
    cocore.start()
    try:
        if not cocore.xmpp.start():  # Connect to remote server
            cocore.on_failed_connection()
    except:
        cocore.running = False
        cocore.reset_curses()
        print("Poezio could not start, maybe you tried aborting it while it was starting?\n"
                "If you think it is abnormal, please run it with the -d option and report the bug.")
    else:
        log.error('------------------------ new poezio start ------------------------')
        cocore.main_loop()    # Refresh the screen, wait for user events etc

if __name__ == '__main__':
    main()
