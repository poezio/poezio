"""

This plugins allows commands to be sent to poezio via a named pipe.

"""


from plugin import BasePlugin
import threading
import os
import stat
import logging

log = logging.getLogger(__name__)

PIPENAME = "/tmp/poezio.fifo"

class Plugin(BasePlugin):
    def init(self):
        self.stop = False

        self.pipename = self.config.get("pipename", PIPENAME)

        if not os.path.exists(self.pipename):
            os.mkfifo(self.pipename)

        if not stat.S_ISFIFO(os.stat(self.pipename).st_mode):
            log.error("File %s is not a fifo file" % self.pipename)
            raise TypeError

        thread = threading.Thread(target=self.main_loop)
        thread.setDaemon(True)
        thread.start()

    def main_loop(self):
        while not self.stop:
            fd = open(self.pipename, 'r')
            line = fd.read().strip()
            self.api.run_command(line)
            fd.close()

    def cleanup(self):
        self.stop = True
