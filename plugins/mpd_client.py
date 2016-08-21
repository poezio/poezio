"""
This plugin is here to send what you are listening to in a chat tab.

Installation
------------

You need `python-mpd`_, in its python3 version.

Then you can load the plugin.

.. code-block:: none

 /load mpd_client


Configuration
-------------

You have to put the following into :file:`mpd_client.cfg`, as explained in
the :ref:`plugin-configuration` section.

.. note:: If you do not put anything, the plugin will try to connect to
        :file:`localhost:6600` with no password.

.. code-block:: ini

    [mpd_client]
    host = the_mpd_host
    port = 6600
    password = password if necessary


Usage
-----

.. glossary::

    /mpd
        **Usage:** ``/mpd [full]``

        The bare command will show the current song, artist, and album

        ``/mpd full`` will show the current song, artist, and album,
        plus a nice progress bar in color.

.. _python-mpd: https://github.com/Mic92/python-mpd2

"""

from poezio.plugin import BasePlugin
from poezio.common import shell_split
from poezio.core.structs import Completion
from os.path import basename as base
from poezio import tabs
import mpd

class Plugin(BasePlugin):
    def init(self):
        for _class in (tabs.ConversationTab, tabs.MucTab, tabs.PrivateTab):
            self.api.add_tab_command(_class, 'mpd', self.command_mpd,
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
                percents = int(current_time / float(current['time']) * 10)
                s += ' \x192}[\x191}' + '-'*(percents-1) + '\x193}+' + '\x191}' + '-' * (10-percents-1) + '\x192}]\x19o'
        if not self.api.send_message('%s' % (s,)):
            self.api.information('Cannot send result (%s)' % s, 'Error')

    def completion_mpd(self, the_input):
        return Completion(the_input.auto_completion, ['full'], quotify=False)
