#/usr/bin/env python3
# Copyright 2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
This file is a standalone program that reads commands on
stdin and executes them (each line should be a command).

Usage: cat some_fifo | ./daemon.py

Poezio writes commands in the fifo, and this daemon executes them on the
local machine.
Note that you should not start this daemon if you do not trust the remote
machine that is running poezio, since this could make it run any (dangerous)
command on your local machine.
"""

import sys
import threading
import subprocess
import shlex
import logging

log = logging.getLogger(__name__)

class Executor(threading.Thread):
    """
    Just a class to execute commands in a thread.
    This way, the execution can totally fail, we don’t care,
    and we can start commands without having to wait for them
    to return
    """
    def __init__(self, command):
        threading.Thread.__init__(self)
        self.command = command

    def run(self):
        log.info('executing %s' % (self.command.strip(),))
        command = shlex.split('sh -c "%s"' % self.command)
        subprocess.call(command)

def main():
    while True:
        line = sys.stdin.readline()
        if line == '':
            break
        e = Executor(line)
        e.start()

if __name__ == '__main__':
    main()
