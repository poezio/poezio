#!/usr/bin/env python3
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

from subprocess import DEVNULL

log = logging.getLogger(__name__)


class Executor(threading.Thread):
    """
    Just a class to execute commands in a thread.  This way, the execution
    can totally fail, we don’t care, and we can start commands without
    having to wait for them to return.
    WARNING: Be careful to properly escape what is untrusted by using
    shlex.quote for example.
    """

    def __init__(self, command, remote=False):
        threading.Thread.__init__(self)
        self.command = command
        self.remote = remote
        # check for > or >> special case
        self.filename = None
        self.redirection_mode = 'w'
        if len(command) >= 3:
            if command[-2] in ('>', '>>'):
                self.filename = command.pop(-1)
                if command[-1] == '>>':
                    self.redirection_mode = 'a'
                command.pop(-1)

    def run(self):
        log.debug('executing %s', self.command)
        stdout = DEVNULL
        if self.filename:
            try:
                stdout = open(self.filename, self.redirection_mode)
            except OSError:
                log.error(
                    'Could not open redirection file: %s',
                    self.filename,
                    exc_info=True)
                return
        try:
            subprocess.call(self.command, stdout=stdout, stderr=DEVNULL)
        except:
            if self.remote:
                import traceback
                print(traceback.format_exc())
            else:
                log.error('Could not execute %s:', self.command, exc_info=True)


def main():
    while True:
        line = sys.stdin.readline()
        if line == '':
            break
        command = shlex.split(line)
        e = Executor(command, remote=True)
        e.start()


if __name__ == '__main__':
    main()
