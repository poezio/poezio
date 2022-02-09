'''
This plugin lets the user select and send a sticker from a pack of stickers.

Command
-------

.. glossary::
    /sticker
        **Usage:** ``/sticker <pack>``

        Opens a picker tool, and send the sticker which has been selected.

Configuration options
---------------------

.. glossary::
    sticker_picker
        **Default:** ``poezio-sticker-picker``

        The command to invoke as a sticker picker.  A sample one is provided in
        tools/sticker-picker.

    stickers_dir
        **Default:** ``XDG_DATA_HOME/poezio/stickers``

        The directory under which the sticker packs can be found.
'''

import asyncio
from poezio import xdg
from poezio.plugin import BasePlugin
from poezio.core.structs import Completion
from pathlib import Path
from subprocess import check_output, CalledProcessError

class Plugin(BasePlugin):
    dependencies = {'upload'}

    def init(self):
        # The command to use as a picker helper.
        self.picker_command = config.getstr('sticker_picker', 'poezio-sticker-picker')

        # Select and create the stickers directory.
        directory = config.getstr('stickers_dir')
        if directory:
            self.directory = Path(directory).expanduser()
        else:
            self.directory = xdg.DATA_HOME / 'stickers'
        self.directory.mkdir(parents=True, exist_ok=True)

        self.upload = self.refs['upload']
        self.api.add_command('sticker', self.command_sticker,
                usage='<sticker pack>',
                short='Send a sticker, with a GUI selector',
                help='Send a sticker, with a GUI selector')

    def command_sticker(self, pack):
        '''
        Sends a sticker
        '''
        path = self.directory / pack
        try:
            sticker = check_output([self.picker_command, path])
        except CalledProcessError as err:
            self.api.information('Sticker picker failed: %s' % err, 'Error')
            return
        if sticker:
            filename = sticker.decode().rstrip()
            tab = self.api.current_tab()
            asyncio.create_task(self.upload.send_upload(path / filename, tab))

    def completion_sticker(self, the_input):
        '''
        Completion for /sticker
        '''
        txt = the_input.get_text()[9:]
        directories = [directory.name for directory in self.directory.glob(txt + '*')]
        return Completion(the_input.auto_completion, directories, quotify=False)
