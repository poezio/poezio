# Copyright 2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
This file is a standalone program that creates a fifo file (if it doesn’t exist
yet), opens it for reading, reads commands from it and executes them (each line
should be a command).

Usage: ./daemon.py <path_tofifo>

That fifo should be in a directory, shared through sshfs, with the remote
machine running poezio. Poezio then writes command in it, and this daemon
executes them on the local machine.
Note that you should not start this daemon if you do not trust the remote
machine that is running poezio, since this could make it run any (dangerous)
command on your local machine.
"""

import sys
import threading
import subprocess

from fifo import Fifo

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
        print('executing %s' % (self.command,))
        subprocess.call(self.command.split())

def main(path):
    while True:
        fifo = Fifo(path, 'r')
        while True:
            line = fifo.readline()
            if line == '':
                del fifo
                break
            e = Executor(line)
            e.start()

def usage():
    print('Usage: %s <fifo_name>' % (sys.argv[0],))

if __name__ == '__main__':
    argc = len(sys.argv)
    if argc != 2:
        usage()
    else:
        main(sys.argv[1])
