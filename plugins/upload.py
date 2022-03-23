"""
Upload a file and auto-complete the input with its URL.

Usage
-----

This plugin adds a command to the chat tabs.

.. glossary::

    /upload
        **Usage:** ``/upload <filename>``

        Uploads the <filename> file to the preferred HTTP File Upload
        service (see XEP-0363) and fill the input with its URL.


"""

from typing import Optional

import asyncio
import traceback
from os.path import expanduser
from glob import glob

from slixmpp.plugins.xep_0363.http_upload import FileTooBig, HTTPError, UploadServiceNotFound

from poezio.plugin import BasePlugin
from poezio.core.structs import Completion
from poezio.decorators import command_args_parser
from poezio import tabs


class Plugin(BasePlugin):
    dependencies = {'embed'}

    def init(self):
        self.embed = self.refs['embed']

        if not self.core.xmpp['xep_0363']:
            raise Exception('slixmpp XEP-0363 plugin failed to load')
        if not self.core.xmpp['xep_0454']:
            self.api.information(
                'slixmpp XEP-0454 plugin failed to load. '
                'Will not be able to encrypt uploaded files.',
                'Warning',
            )
        for _class in (tabs.PrivateTab, tabs.StaticConversationTab, tabs.DynamicConversationTab, tabs.MucTab):
            self.api.add_tab_command(
                _class,
                'upload',
                self.command_upload,
                usage='<filename>',
                help='Upload a file and auto-complete the input with its URL.',
                short='Upload a file',
                completion=self.completion_filename)

    async def upload(self, filename, encrypted=False) -> Optional[str]:
        try:
            upload_file = self.core.xmpp['xep_0363'].upload_file
            if encrypted:
                upload_file = self.core.xmpp['xep_0454'].upload_file
            url = await upload_file(filename)
        except UploadServiceNotFound:
            self.api.information('HTTP Upload service not found.', 'Error')
            return None
        except (FileTooBig, HTTPError) as exn:
            self.api.information(str(exn), 'Error')
            return None
        except Exception:
            exception = traceback.format_exc()
            self.api.information('Failed to upload file: %s' % exception,
                                 'Error')
            return None
        return url

    async def send_upload(self, filename, tab, encrypted=False):
        url = await self.upload(filename, encrypted)
        if url is not None:
            self.embed.embed_image_url(url, tab)

    @command_args_parser.quoted(1)
    def command_upload(self, args):
        if args is None:
            self.core.command.help('upload')
            return
        filename, = args
        filename = expanduser(filename)
        tab = self.api.current_tab()
        encrypted = self.core.xmpp['xep_0454'] and tab.e2e_encryption is not None
        asyncio.create_task(self.send_upload(filename, tab, encrypted))

    @staticmethod
    def completion_filename(the_input):
        txt = expanduser(the_input.get_text()[8:])
        files = glob(txt + '*')
        return Completion(the_input.auto_completion, files, quotify=False)
