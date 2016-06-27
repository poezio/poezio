"""

This plugins allows commands to be sent to poezio via a named pipe.

You can run the same commands that you would in the poezio input
(e.g. ``echo '/message toto@example.tld Hi' >> /tmp/poezio.fifo``).

Configuration
-------------

.. glossary::
    :sorted:

    pipename
        **Default:** :file:`/tmp/poezio.fifo`

        The path to the fifo which will receive commands.

"""


from poezio.plugin import BasePlugin
import os
import stat
import logging
import asyncio

log = logging.getLogger(__name__)

PIPENAME = "/tmp/poezio.fifo"

class Plugin(BasePlugin):
    def init(self):
        self.stop = False

        self.pipename = self.config.get("pipename", PIPENAME)

        if not os.path.exists(self.pipename):
            os.mkfifo(self.pipename)

        if not stat.S_ISFIFO(os.stat(self.pipename).st_mode):
            raise TypeError("File %s is not a fifo file" % self.pipename)

        self.fd = os.open(self.pipename, os.O_RDONLY|os.O_NONBLOCK)

        self.data = b""
        asyncio.get_event_loop().add_reader(self.fd, self.read_from_fifo)

    def read_from_fifo(self):
        data = os.read(self.fd, 512)
        if not data:
            # EOF, close the fifo. And reopen it
            asyncio.get_event_loop().remove_reader(self.fd)
            os.close(self.fd)
            self.fd = os.open(self.pipename, os.O_RDONLY|os.O_NONBLOCK)
            asyncio.get_event_loop().add_reader(self.fd, self.read_from_fifo)
            self.data = b''
        else:
            self.data += data
        l = self.data.split(b'\n', 1)
        if len(l) == 2:
            line, self.data = l
            log.debug("run: %s" % (line.decode().strip()))
            self.api.run_command(line.decode().strip())

    def cleanup(self):
        asyncio.get_event_loop().remove_reader(self.fd)
        os.close(self.fd)
