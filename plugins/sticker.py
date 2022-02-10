'''
This plugin lets the user select and send a sticker from a pack of stickers.

The protocol used here is based on XEP-0363 and XEP-0066, while a future
version may use XEP-0449 instead.

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
import concurrent.futures
from poezio import xdg
from poezio.plugin import BasePlugin
from poezio.config import config
from poezio.decorators import command_args_parser
from poezio.core.structs import Completion
from pathlib import Path
from asyncio.subprocess import PIPE, DEVNULL

class Plugin(BasePlugin):
    dependencies = {'upload'}

    def init(self):
        # The command to use as a picker helper.
        self.picker_command = config.getstr('sticker_picker') or 'poezio-sticker-picker'

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
                short='Send a sticker',
                help='Send a sticker, with a helper GUI sticker picker',
                completion=self.completion_sticker)

    def command_sticker(self, pack):
        '''
        Sends a sticker
        '''
        if not pack:
            self.api.information('Missing sticker pack argument.', 'Error')
            return
        async def run_command(tab, path: Path):
            try:
                process = await asyncio.create_subprocess_exec(
                    self.picker_command, path, stdout=PIPE, stderr=PIPE)
                sticker, stderr = await process.communicate()
            except FileNotFoundError as err:
                self.api.information('Failed to launch the sticker picker: %s' % err, 'Error')
                return
            else:
                if process.returncode != 0:
                    self.api.information('Sticker picker failed: %s' % stderr.decode(), 'Error')
                    return
            if sticker:
                filename = sticker.decode().rstrip()
                self.api.information('Sending sticker %s' % filename, 'Info')
                await self.upload.send_upload(path / filename, tab)
        tab = self.api.current_tab()
        path = self.directory / pack
        asyncio.create_task(run_command(tab, path))

    def completion_sticker(self, the_input):
        '''
        Completion for /sticker
        '''
        txt = the_input.get_text()[9:]
        directories = [directory.name for directory in self.directory.glob(txt + '*')]
        return Completion(the_input.auto_completion, directories, quotify=False)
