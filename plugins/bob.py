"""
This plugin sends a small image to the recipient of your choice, using XHTML-IM and Bits of Binary.

Usage
-----

/bob some/image.png

Configuration options
---------------------

.. glossary::

    max_size
        **Default:** ``2048``

        The maximum acceptable size of a file, over which you will get an error instead.

    max_age
        **Default:** ``86400``

        The time during which the file should stay in cache on the receiving side.
"""

from poezio.core.structs import Completion
from poezio.plugin import BasePlugin
from poezio import tabs

from pathlib import Path
from glob import glob
from os.path import expanduser
from mimetypes import guess_type


class Plugin(BasePlugin):

    default_config = {'bob': {'max_size': 2048,
                              'max_age': 86400}}

    def init(self):
        for tab in tabs.ConversationTab, tabs.PrivateTab, tabs.MucTab:
            self.api.add_tab_command(tab, 'bob', self.command_bob,
                                     usage='<image>',
                                     help='Send image <image> to the current discussion',
                                     short='Send a short image',
                                     completion=self.completion_bob)

    def command_bob(self, filename):
        path = Path(expanduser(filename))
        try:
            size = path.stat().st_size
        except OSError as exc:
            self.api.information('Error sending “%s”: %s' % (path.name, exc), 'Error')
            return
        mime_type = guess_type(path.as_posix())[0]
        if mime_type is None or not mime_type.startswith('image/'):
            self.api.information('Error sending “%s”, not an image file.' % path.name, 'Error')
            return
        if size > self.config.get('max_size'):
            self.api.information('Error sending “%s”, file too big.' % path.name, 'Error')
            return
        with open(path.as_posix(), 'rb') as file:
            data = file.read()
        max_age = self.config.get('max_age')
        cid = self.core.xmpp.plugin['xep_0231'].set_bob(data, mime_type, max_age=max_age)
        self.api.run_command('/xhtml <img src="cid:%s" alt="%s"/>' % (cid, path.name))

    @staticmethod
    def completion_bob(the_input):
        txt = expanduser(the_input.get_text()[5:])
        images = []
        for filename in glob(txt + '*'):
            mime_type = guess_type(filename)[0]
            if mime_type is not None and mime_type.startswith('image/'):
                images.append(filename)
        return Completion(the_input.auto_completion, images, quotify=False)
