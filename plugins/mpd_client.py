# a plugin adding a command to manipulate an MPD instance

from plugin import BasePlugin
from common import shell_split
from os.path import basename as base
import tabs
import mpd
import threading
from select import select
from time import sleep

class UpdateThread(threading.Thread):
    """
    Background thread that awaits mpd changes
    """

    def __init__(self, plugin, xmpp):
        threading.Thread.__init__(self)
        self.plugin = plugin
        self.xmpp = xmpp
        self.alive = False
        self.c = mpd.MPDClient()

    def run(self, *args, **kwargs):
        self.alive = True
        while self.alive:
            try:
                self.c.connect(host=self.plugin.config.get('host', 'localhost'), port=self.plugin.config.get('port', '6600'))
                password = self.plugin.config.get('password', '')
                if password:
                    self.c.password(password)
                self.c.send_idle()
                select([self.c], [], [])
                self.c.fetch_idle()
                status = self.c.status()
                if status['state'] == 'play' and self.alive:
                    song = self.c.currentsong()
                    self.xmpp.plugin['xep_0118'].publish_tune(artist=song.get('artist'),
                            length=song.get('time'), title=song.get('title'),
                            track=song.get('track'), block=False)
                self.c.disconnect()
            except:
                pass
            finally:
                try:
                    self.c.disconnect()
                except:
                    pass
                sleep(8)

class Plugin(BasePlugin):
    def init(self):
        for _class in (tabs.ConversationTab, tabs.MucTab, tabs.PrivateTab):
            self.api.add_tab_command(_class, 'mpd', self.command_mpd,
                    usage='[full]',
                    help='Sends a message showing the current song of an MPD instance. If full is provided, the message is more verbose.',
                    short='Send the MPD status',
                    completion=self.completion_mpd)
        if self.config.get('broadcast', 'true').lower() != 'false':
            self.core.xmpp.register_plugin('xep_0118')
            self.thread = UpdateThread(plugin=self, xmpp=self.core.xmpp)
            self.thread.start()

    def cleanup(self):
        self.thread.alive = False
        self.thread.c.disconnect()
        self.core.xmpp.plugin['xep_0118'].stop(block=False)

    def command_mpd(self, args):
        args = shell_split(args)
        c = mpd.MPDClient()
        c.connect(host=self.config.get('host', 'localhost'), port=self.config.get('port', '6600'))
        password = self.config.get('password', '')
        if password:
            c.password(password)
        current = c.currentsong()
        artist = current.get('artist', 'Unknown artist')
        album = current.get('album', 'Unknown album')
        title = current.get('title', base(current.get('file', 'Unknown title')))

        s = '%s - %s (%s)' % (artist, title, album)
        if 'full' in args:
            if 'elapsed' in current and 'time' in current:
                current_time = float(c.status()['elapsed'])
                percents = int(current_time / float(current['time']) * 10)
                s += ' \x192}[\x191}' + '-'*(percents-1) + '\x193}+' + '\x191}' + '-' * (10-percents-1) + '\x192}]\x19o'
        if not self.api.send_message('%s' % (s,)):
            self.api.information('Cannot send result (%s)' % s, 'Error')

    def completion_mpd(self, the_input):
        return the_input.auto_completion(['full'], quotify=False)
