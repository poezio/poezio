# a plugin adding a command to manipulate an MPD instance

from plugin import BasePlugin
from common import shell_split
import mpd

class Plugin(BasePlugin):
    def init(self):
        self.add_command('mpd', self.command_mpd, "Usage: /mpd [full]\nMpd: sends a message showing the current song of an MPD instance. If full is provided, teh message is more verbose.", self.completion_mpd)

    def command_mpd(self, args):
        args = shell_split(args)
        c = mpd.MPDClient()
        c.connect(host=self.config.get('host', 'localhost'), port=self.config.get('host', '6600'))

        current = c.currentsong()
        current_time = float(c.status()['elapsed'])

        s = '%(artist)s - %(title)s (%(album)s)' % current
        if 'full' in args:
            pourcentage = int(current_time / float(current['time']) * 10)
            s += ' \x192[\x191' + '-'*(pourcentage-1) + '\x193+' + '\x191' + '-' * (10-pourcentage-1) + '\x192]\x19o'
        if not self.core.send_message('%s' % (s,)):
            self.core.information('Cannot send result (%s), this is not a conversation tab' % result)

    def completion_mpd(self, the_input):
        return the_input.auto_completion(['full'])
