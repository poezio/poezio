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
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import singleton

def main():
    """
    Enter point
    """
    sys.stdout.write("\x1b]0;poezio\x07")
    sys.stdout.flush()
    import config
    config_path = config.check_create_config_dir()
    config.run_cmdline_args(config_path)
    config.create_global_config()
    config.check_create_log_dir()
    config.setup_logging()
    config.post_logging_setup()

    from config import options

    import theming
    theming.update_themes_dir()

    import logger
    logger.create_logger()

    import roster
    roster.create_roster()

    import core

    log = logging.getLogger('')

    signal.signal(signal.SIGINT, signal.SIG_IGN) # ignore ctrl-c
    cocore = singleton.Singleton(core.Core)
    signal.signal(signal.SIGUSR1, cocore.sigusr_handler) # reload the config
    signal.signal(signal.SIGHUP, cocore.exit_from_signal)
    signal.signal(signal.SIGTERM, cocore.exit_from_signal)
    if options.debug:
        cocore.debug = True
    cocore.start()

    # Warning: asyncio must always be imported after the config. Otherwise
    # the asyncio logger will not follow our configuration and won't write
    # the tracebacks in the correct file, etc
    import asyncio

    asyncio.get_event_loop().add_reader(sys.stdin, cocore.on_input_readable)
    asyncio.get_event_loop().add_signal_handler(signal.SIGWINCH, cocore.sigwinch_handler)
    cocore.xmpp.start()
    asyncio.get_event_loop().run_forever()
    # We reach this point only when loop.stop() is called
    try:
        cocore.reset_curses()
    except:
        pass

if __name__ == '__main__':
    main()
