"""
This plugin will set your status to **away** if you detach your screen.

Installation
------------
You only have to load the plugin.

.. code-block:: none

    /load screen_detach

"""
from plugin import BasePlugin
import os
import stat
import pyinotify

SCREEN_DIR = '/var/run/screen/S-%s' % (os.getlogin(),)

class Plugin(BasePlugin):
    def init(self):
        self.timed_event = None
        sock_path = None
        self.thread = None
        for f in os.listdir(SCREEN_DIR):
            path = os.path.join(SCREEN_DIR, f)
            if screen_attached(path):
                sock_path = path
                self.attached = True
                break

        # Only actually do something if we found an attached screen (assuming only one)
        if sock_path:
            wm = pyinotify.WatchManager()
            wm.add_watch(sock_path, pyinotify.EventsCodes.ALL_FLAGS['IN_ATTRIB'])
            self.thread = pyinotify.ThreadedNotifier(wm, default_proc_fun=HandleScreen(plugin=self))
            self.thread.start()

    def cleanup(self):
        if self.thread:
            self.thread.stop()

    def update_screen_state(self, socket):
        attached = screen_attached(socket)
        if attached != self.attached:
            self.attached = attached
            status = 'available' if self.attached else 'away'
            self.core.command_status(status)

def screen_attached(socket):
    return (os.stat(socket).st_mode & stat.S_IXUSR) != 0

class HandleScreen(pyinotify.ProcessEvent):
    def my_init(self, **kwargs):
        self.plugin = kwargs['plugin']

    def process_IN_ATTRIB(self, event):
        self.plugin.update_screen_state(event.path)
