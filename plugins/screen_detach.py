"""
This plugin will set your status to **away** if you detach your screen.

The default behaviour is to check for both tmux and screen (in that order).

Configuration options
---------------------

.. glossary::

    use_screen
        **Default:** ``true``

        Try to find an attached screen.

    use_tmux
        **Default:** ``true``

        Try to find and attached tmux.

    use_csi
        **Default:** ``false``

        Use `client state indication`_ to limit bandwidth (thus CPU) usage when detached. WARNING: using CSI together with chatrooms will result in inaccurate logs due to presence filtering or other inaccuracies.

.. _client state indication: https://xmpp.org/extensions/xep-0352.html
"""

from poezio.plugin import BasePlugin
import os
import stat
import pyinotify
import asyncio

DEFAULT_CONFIG = {
    'screen_detach': {
        'use_tmux': True,
        'use_screen': True,
        'use_csi': False
    }
}


# overload if this is not how your stuff
# is configured
try:
    LOGIN = os.getlogin()
    LOGIN_TMUX = os.getuid()
except Exception:
    LOGIN = os.getenv('USER')
    LOGIN_TMUX = os.getuid()

SCREEN_DIR = '/var/run/screens/S-%s' % LOGIN
TMUX_DIR = '/tmp/tmux-%s' % LOGIN_TMUX

def find_screen(path):
    if not os.path.isdir(path):
        return
    for f in os.listdir(path):
        path = os.path.join(path, f)
        if screen_attached(path):
            return path

def screen_attached(socket):
    return (os.stat(socket).st_mode & stat.S_IXUSR) != 0

class Plugin(BasePlugin, pyinotify.Notifier):

    default_config = DEFAULT_CONFIG

    def init(self):
        sock_path = None
        if self.config.get('use_tmux'):
            sock_path = find_screen(TMUX_DIR)
        if sock_path is None and self.config.get('use_screen'):
            sock_path = find_screen(SCREEN_DIR)

        # Only actually do something if we found an attached screen (assuming only one)
        if sock_path:
            self.attached = True
            wm = pyinotify.WatchManager()
            wm.add_watch(sock_path, pyinotify.EventsCodes.ALL_FLAGS['IN_ATTRIB'])
            pyinotify.Notifier.__init__(self, wm, default_proc_fun=HandleScreen(plugin=self))
            asyncio.get_event_loop().add_reader(self._fd, self.process)
        else:
            self.api.information('screen_detach plugin: No tmux or screen found',
                                 'Warning')
            self.attached = False

    def process(self):
        self.read_events()
        self.process_events()

    def cleanup(self):
        asyncio.get_event_loop().remove_reader(self._fd)

    def update_screen_state(self, socket):
        attached = screen_attached(socket)
        if attached != self.attached:
            self.attached = attached
            status = 'available' if self.attached else 'away'
            self.core.command.status(status)
            if self.config.get('use_csi'):
                if self.attached:
                    self.core.xmpp.plugin['xep_0352'].send_active()
                else:
                    self.core.xmpp.plugin['xep_0352'].send_inactive()

class HandleScreen(pyinotify.ProcessEvent):
    def my_init(self, **kwargs):
        self.plugin = kwargs['plugin']

    def process_IN_ATTRIB(self, event):
        self.plugin.update_screen_state(event.path)
