#!/usr/bin/env python3

import io
import logging
import qrcode
import sys

from poezio import windows
from poezio.tabs import Tab
from poezio.common import safeJID
from poezio.core.structs import Command
from poezio.decorators import command_args_parser
from poezio.plugin import BasePlugin
from poezio.theming import get_theme, to_curses_attr
from poezio.windows.base_wins import Win

log = logging.getLogger(__name__)

class QrWindow(Win):
    __slots__ = ('qr', 'invert', 'inverted')

    str_invert = " Invert "
    str_close = " Close "

    def __init__(self, qr: str) -> None:
        self.qr = qr
        self.invert = True
        self.inverted = True

    def refresh(self) -> None:
        self._win.erase()
        # draw QR code
        code = qrcode.QRCode()
        code.add_data(self.qr)
        out = io.StringIO()
        code.print_ascii(out, invert=self.inverted)
        self.addstr("   " + self.qr + "\n")
        self.addstr(out.getvalue(), to_curses_attr((15, 0)))
        self.addstr("   ")

        col = to_curses_attr(get_theme().COLOR_TAB_NORMAL)

        if self.invert:
            self.addstr(self.str_invert, col)
        else:
            self.addstr(self.str_invert)

        self.addstr("   ")

        if self.invert:
            self.addstr(self.str_close)
        else:
            self.addstr(self.str_close, col)

        self._refresh()

    def toggle_choice(self) -> None:
        self.invert = not self.invert

    def engage(self) -> bool:
        if self.invert:
            self.inverted = not self.inverted
            return False
        else:
            return True

class QrTab(Tab):
    plugin_commands = {}  # type: Dict[str, Command]
    plugin_keys = {}  # type: Dict[str, Callable]

    def __init__(self, core, qr):
        Tab.__init__(self, core)
        self.state = 'highlight'
        self.text = qr
        self.name = qr
        self.topic_win = windows.Topic()
        self.topic_win.set_message(qr)
        self.qr_win = QrWindow(qr)
        self.help_win = windows.HelpText(
            "Choose with arrow keys and press enter")
        self.key_func['^I'] = self.toggle_choice
        self.key_func[' '] = self.toggle_choice
        self.key_func['KEY_LEFT'] = self.toggle_choice
        self.key_func['KEY_RIGHT'] = self.toggle_choice
        self.key_func['^M'] = self.engage
        self.resize()
        self.update_commands()
        self.update_keys()

    def resize(self):
        self.need_resize = False
        self.topic_win.resize(1, self.width, 0, 0)
        self.qr_win.resize(self.height-3, self.width, 1, 0)
        self.help_win.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        self.refresh_tab_win()
        self.info_win.refresh()
        self.topic_win.refresh()
        self.qr_win.refresh()
        self.help_win.refresh()

    def on_input(self, key, raw):
        if not raw and key in self.key_func:
            return self.key_func[key]()

    def toggle_choice(self):
        log.debug('  TAB   toggle_choice: %s', self.__class__.__name__)
        self.qr_win.toggle_choice()
        self.refresh()
        self.core.doupdate()

    def engage(self):
        log.debug('  TAB   engage: %s', self.__class__.__name__)
        if self.qr_win.engage():
            self.core.close_tab(self)
        else:
            self.refresh()
            self.core.doupdate()

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command(
            'qr',
            self.command_qr,
            usage='<message>',
            short='Display a QR code',
            help='Display a QR code of <message> in a new tab')
        self.api.add_command(
            'invitation',
            self.command_invite,
            usage='[<server>]',
            short='Invite a user',
            help='Generate a XEP-0401 invitation on your server or on <server> and display a QR code')

    def command_qr(self, msg):
        t = QrTab(self.core, msg)
        self.core.add_tab(t, True)
        self.core.doupdate()

    def on_next(self, iq, adhoc_session):
        status = iq['command']['status']
        xform = iq.xml.find(
            '{http://jabber.org/protocol/commands}command/{jabber:x:data}x')
        if xform is not None:
            form = self.core.xmpp.plugin['xep_0004'].build_form(xform)
        else:
            form = None
        uri = None
        if status == 'completed' and form:
            for field in form:
                log.debug('  field: %s -> %s', field['var'], field['value'])
                if field['var'] == 'landing-url' and field['value']:
                    uri = field.get_value(convert=False)
                if field['var'] == 'uri' and field['value'] and uri is None:
                    uri = field.get_value(convert=False)
        if uri:
            t = QrTab(self.core, uri)
            self.core.add_tab(t, True)
            self.core.doupdate()
        else:
            self.core.handler.next_adhoc_step(iq, adhoc_session)
        

    @command_args_parser.quoted(0, 1, defaults=[])
    def command_invite(self, args):
        server = self.core.xmpp.boundjid.domain
        if len(args) > 0:
            server = safeJID(args[0])
        session = {
            'next' : self.on_next,
            'error': self.core.handler.adhoc_error
        }
        self.core.xmpp.plugin['xep_0050'].start_command(server, 'urn:xmpp:invite#invite', session)

