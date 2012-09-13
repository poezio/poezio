# Copyright 2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Defines the Fifo class
"""

import logging
log = logging.getLogger(__name__)

import os
import threading

class OpenTrick(threading.Thread):
    """
    A threaded trick to make the open for writing succeed.
    A fifo cannot be opened for writing if it has not been
    yet opened by the other hand for reading.
    So, we just open the fifo for reading and close it
    immediately afterwards.
    Once that is done, we can freely keep the fifo open for
    writing and write things in it. The writing can fail if
    there’s still nothing reading that fifo, but we just yell
    an error in that case.
    """
    def __init__(self, path):
        threading.Thread.__init__(self)
        self.path = path

    def run(self):
        open(self.path, 'r', encoding='utf-8').close()


class Fifo(object):
    """
    Just a simple file handler, writing and reading in a fifo.
    Mode is either 'r' or 'w', just like the mode for the open()
    function.
    """
    def __init__(self, path, mode):
        self.trick = None
        if not os.path.exists(path):
            os.mkfifo(path)
        if mode == 'w':
            self.trick = OpenTrick(path)
            # that thread will wait until we open it for writing
            self.trick.start()
        self.fd = open(path, mode, encoding='utf-8')

    def write(self, data):
        """
        Try to write on the fifo. If that fails, this means
        that nothing has that fifo opened, so the writing is useless,
        so we just return (and display an error telling that, somewhere).
        """
        self.fd.write(data)
        self.fd.flush()

    def readline(self):
        return self.fd.readline()

    def __del__(self):
        try:
            self.fd.close()
        except:
            pass
