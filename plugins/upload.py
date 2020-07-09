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

def open_file_xdg_desktop_portal():
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
    except GLib.Error:
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


class Plugin(BasePlugin):
    dependencies = {'embed'}

    def init(self):
        self.embed = self.refs['embed']

        if not self.core.xmpp['xep_0363']:
            raise Exception('slixmpp XEP-0363 plugin failed to load')
        for _class in (tabs.PrivateTab, tabs.StaticConversationTab, tabs.DynamicConversationTab, tabs.MucTab):
            self.api.add_tab_command(
                _class,
                'upload',
                self.command_upload,
                usage='<filename>',
                help='Upload a file and auto-complete the input with its URL.',
                short='Upload a file',
                completion=self.completion_filename)

    async def upload(self, filename: Optional[str]) -> Optional[str]:
        if filename is None:
            filename = open_file_xdg_desktop_portal()
            if filename is None:
                self.api.information('Failed to query which file to upload.', 'Error')
                return None
        try:
            url = await self.core.xmpp['xep_0363'].upload_file(filename)
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

    async def send_upload(self, filename: Optional[str]):
        url = await self.upload(filename)
        if url is not None:
            self.embed.embed_image_url(url)

    @command_args_parser.quoted(0, 1)
    def command_upload(self, args):
        if args:
            filename, = args
            filename = expanduser(filename)
        else:
            filename = None
        asyncio.ensure_future(self.send_upload(filename))

    @staticmethod
    def completion_filename(the_input):
        txt = expanduser(the_input.get_text()[8:])
        files = glob(txt + '*')
        return Completion(the_input.auto_completion, files, quotify=False)


if __name__ == '__main__':
    path = open_file_xdg_desktop_portal()
    print('Obtained path', path)
