# a plugin adding a command to manipulate an MPD instance

from plugin import BasePlugin
from common import shell_split
from os.path import basename as base
import tabs
import mpd

class Plugin(BasePlugin):
    def init(self):
        for _class in (tabs.ConversationTab, tabs.MucTab, tabs.PrivateTab):
            self.add_tab_command(_class, 'mpd', self.command_mpd,
                    usage='[full]',
                    help='Sends a message showing the current song of an MPD instance. If full is provided, the message is more verbose.',
                    short='Send the MPD status',
                    completion=self.completion_mpd)

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
                pourcentage = int(current_time / float(current['time']) * 10)
                s += ' \x192}[\x191}' + '-'*(pourcentage-1) + '\x193}+' + '\x191}' + '-' * (10-pourcentage-1) + '\x192}]\x19o'
        if not self.core.send_message('%s' % (s,)):
            self.core.information('Cannot send result (%s)' % s, 'Error')

    def completion_mpd(self, the_input):
        return the_input.auto_completion(['full'], quotify=False)
