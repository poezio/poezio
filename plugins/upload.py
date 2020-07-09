"""
Upload a file and auto-complete the input with its URL.

Usage
-----

This plugin adds a command to the chat tabs.

.. glossary::

    /upload
        **Usage:** ``/upload [filename]``

        Uploads the <filename> file to the preferred HTTP File Upload
        service (see XEP-0363) and fill the input with its URL.

        If <filename> isn’t specified, use the FileChooser from
        xdg-desktop-portal to ask the user which file to upload.


"""

from typing import Optional

import asyncio
import traceback
from os.path import expanduser
from glob import glob
from concurrent.futures import ThreadPoolExecutor

from slixmpp.plugins.xep_0363.http_upload import FileTooBig, HTTPError, UploadServiceNotFound

from poezio.plugin import BasePlugin
from poezio.core.structs import Completion
from poezio.decorators import command_args_parser
from poezio import tabs

try:
    from gi.repository import Gio, GLib
    from urllib.parse import urlparse, unquote
    HAVE_GLIB = True
except ImportError:
    HAVE_GLIB = False

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

    async def upload(self, filename: Optional[str], encrypted=False) -> Optional[str]:
        if filename is None:
            with ThreadPoolExecutor() as pool:
                loop = asyncio.get_running_loop()
                filename = await loop.run_in_executor(pool, self.open_file_xdg_desktop_portal)
                if filename is None:
                    return None
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

    async def send_upload(self, filename: Optional[str], tab, encrypted=False):
        url = await self.upload(filename, encrypted)
        if url is not None:
            self.embed.embed_image_url(url, tab)

    @command_args_parser.quoted(0, 1)
    def command_upload(self, args):
        if args:
            filename = expanduser(args[0])
        else:
            filename = None
        tab = self.api.current_tab()
        encrypted = self.core.xmpp['xep_0454'] and tab.e2e_encryption is not None
        asyncio.create_task(self.send_upload(filename, tab, encrypted))

    @staticmethod
    def completion_filename(the_input):
        txt = expanduser(the_input.get_text()[8:])
        files = glob(txt + '*')
        return Completion(the_input.auto_completion, files, quotify=False)

    def open_file_xdg_desktop_portal(self):
        '''
        Use org.freedesktop.portal.FileChooser from xdg-desktop-portal to open a
        file chooser dialog.

        This method uses GDBus from GLib, and specifically runs its mainloop which
        will block the entirety of poezio until it is done, which might cause us to
        drop from rooms and such if the user isn’t quick enough at choosing the
        file…

        See https://flatpak.github.io/xdg-desktop-portal/portal-docs.html
        '''
        if not HAVE_GLIB:
            self.api.information('GLib or Gio not available.', 'Error')
            return None

        def get_file(connection,
                     sender,
                     path,
                     interface,
                     signal,
                     params):
            nonlocal return_path
            # TODO: figure out how to raise an exception to the outside of the GLib
            # loop.
            if not isinstance(params, GLib.Variant):
                loop.quit()
                return
            response_code, results = params.unpack()
            if response_code != 0:
                loop.quit()
                return
            uris = results['uris']
            if len(uris) != 1:
                loop.quit()
                return
            parsed_uri = urlparse(uris[0])
            if parsed_uri.scheme != "file":
                loop.quit()
                return
            return_path = unquote(parsed_uri.path)
            loop.quit()

        return_path = None
        proxy = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION,
                                               Gio.DBusProxyFlags.NONE,
                                               None,
                                               'org.freedesktop.portal.Desktop',
                                               '/org/freedesktop/portal/desktop',
                                               'org.freedesktop.portal.FileChooser',
                                               None)

        try:
            handle = proxy.OpenFile('(ssa{sv})', '', 'poezio', {
                'accept_label': GLib.Variant('s', '_Upload'),
            })
        except GLib.Error as err:
            self.api.information('Failed to query file selection portal: %s' % err, 'Error')
            return None
        conn = proxy.get_connection()
        conn.signal_subscribe('org.freedesktop.portal.Desktop',
                              'org.freedesktop.portal.Request',
                              'Response',
                              handle,
                              None,
                              Gio.DBusSignalFlags.NO_MATCH_RULE,
                              get_file)

        loop = GLib.MainLoop()
        loop.run()
        return return_path
