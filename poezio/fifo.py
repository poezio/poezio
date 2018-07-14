"""
Defines the Fifo class

This fifo allows simple communication between a remote poezio
and a local computer, with ssh+cat.
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
    So, we just open the fifo for reading and we do not close
    it afterwards, because if the other reader disconnects,
    we will receive a SIGPIPE. And we do not want that.

    (we never read anything from it, obviously)
    """

    def __init__(self, path):
        threading.Thread.__init__(self)
        self.path = path
        self.fd = None

    def run(self):
        self.fd = open(self.path, 'r', encoding='utf-8')


class Fifo:
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
        "Read a line from the fifo"
        return self.fd.readline()

    def __del__(self):
        "Close opened fds"
        try:
            self.fd.close()
            if self.trick:
                self.trick.fd.close()
        except:
            log.error(
                'Unable to close descriptors for the fifo', exc_info=True)
