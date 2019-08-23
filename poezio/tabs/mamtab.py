"""
The MAMTab is to query for an archive of messages to/from a particular JID.
"""
import logging
log = logging.getLogger(__name__)

import curses
import os
from datetime import datetime, timedelta

import asyncio
from poezio import mam
from poezio.tabs import Tab

from poezio.text_buffer import TextBuffer
from poezio import windows
from poezio.xhtml import clean_text
from poezio.decorators import command_args_parser, refresh_wrapper
from poezio.common import safeJID


class MAMTab(Tab):
    def __init__(self, core):
        Tab.__init__(self, core)
        self.state = 'normal'
        self.name = 'MAMTab'

        self._text_buffer = TextBuffer()

        self.info_header = windows.MAMInfoWin()
        self.text_win = windows.TextWin()
        self._text_buffer.add_window(self.text_win)
        self.default_help_message = windows.HelpText("/ to enter a command")

        self.register_command('close', self.close, shortdesc="Close this tab.")
        self.register_command('mam_preferences', self.mam_preferences,
            shortdesc='Get the current MAM preferences')
        self.register_command('mam', self.command_mam,
            usage="<jid> [start_timestamp] [end_timestamp]",
            shortdesc='Query an archive of messages using MAM.')
        self.register_command(
            'clear', self.command_clear, shortdesc='Clear the current buffer.')
        self.input = self.default_help_message
        self.key_func['^T'] = self.close
        self.key_func['^I'] = self.completion
        self.key_func["KEY_DOWN"] = self.on_scroll_down
        self.key_func["KEY_UP"] = self.on_scroll_up
        self.key_func["^K"] = self.on_freeze
        self.key_func["/"] = self.on_slash
        self.resize()
        # Used to display the infobar
        self.remote_jid = ''
        self.iq = self.core.xmpp.Iq()

    def on_freeze(self):
        """
        Freeze the display.
        """
        self.text_win.toggle_lock()
        self.refresh()

    def on_slash(self):
        """
        '/' is pressed, activate the input
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message,
                                          self.execute_slash_command)
        self.input.resize(1, self.width, self.height - 1, 0)
        self.input.do_command("/")  # we add the slash

    @refresh_wrapper.always
    def reset_help_message(self, _=None):
        if self.closed:
            return True
        if self.core.tabs.current_tab is self:
            curses.curs_set(0)
        self.input = self.default_help_message
        return True

    def on_scroll_up(self):
        return self.text_win.scroll_up(self.text_win.height - 1)

    def on_scroll_down(self):
        return self.text_win.scroll_down(self.text_win.height - 1)

    @command_args_parser.quoted(0, 2)
    def mam_preferences(self, args):
        """A command to get current MAM preferences and change them."""
        def callback(iq):
            self.iq = iq
            return self.core.information(str(iq['mam_prefs']), 'Info')
        if len(args) == 0:
            return self.core.xmpp.plugin['xep_0313'].get_preferences(callback=callback)
        elif len(args) == 2 and args[0] == 'default':
            if args[1] is 'always' or 'roster' or 'never':
                iq = self.iq
                always = iq['mam_prefs']['always']
                never = iq['mam_prefs']['never']
                self.core.xmpp.plugin['xep_0313'].set_preferences(default=args[1], always=always,
                never=never, callback=callback)
        elif len(args) == 2 and args[0] == 'always':
            jid = safeJID(args[1])
            iq = self.iq
            default = iq['mam_prefs']['default']
            always = iq['mam_prefs']['always']
            always = list(always)
            if args[1] == 'clear':
                always = []
            else:
                always = always
                jid = safeJID(args[1])
                always.append(jid)
            never = iq['mam_prefs']['never']
            self.core.xmpp.plugin['xep_0313'].set_preferences(default=default, always=always,
            never=never, callback=callback)
        elif len(args) == 2 and args[0] == 'never':
            jid = safeJID(args[1])
            iq = self.iq
            default = iq['mam_prefs']['default']
            always = iq['mam_prefs']['always']
            never = iq['mam_prefs']['never']
            if args[1] == 'clear':
                never = []
            else:
                never = never
                jid = safeJID(args[1])
                never.append(jid)
            self.core.xmpp.plugin['xep_0313'].set_preferences(default=default, always=always,
            never=never, callback=callback)
        else:
            self.core.information('Please enter a correct command', 'Error')

    @command_args_parser.quoted(0, 3)
    def command_mam(self, args):
        """Define mam command"""

        if len(args) == 0:
            return self.core.information('Please enter a JID.', 'Error')

        remote_jid = safeJID(args[0])
        end = datetime.now()
        end = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')
        start = datetime.strptime(end, '%Y-%m-%dT%H:%M:%SZ')
        # Default start date is 10 days past the current day.
        start = start + timedelta(days=-10)
        start = datetime.strftime(start, '%Y-%m-%dT%H:%M:%SZ')
        # Format for start and end timestamp is [dd:mm:yyyy]
        if len(args) == 2:
            try:
                start = datetime.strptime(args[1], '%d:%m:%Y')
                start = datetime.strftime(start, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                pass
        elif len(args) == 3:
            try:
                start = datetime.strptime(args[1], '%d:%m:%Y')
                start = datetime.strftime(start, '%Y-%m-%dT%H:%M:%SZ')
                end = datetime.strptime(args[2], '%d:%m:%Y')
                end = datetime.strftime(end, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                pass

        def callback(results):
            asyncio.ensure_future(mam.add_messages_to_buffer(self, False, results, 10))

        asyncio.ensure_future(mam.query(
            self.core,
            True,
            remote_jid,
            10,
            reverse=False,
            start=start,
            end=end,
            callback=callback))

    @command_args_parser.ignored
    def command_clear(self):
        """
        /clear
        """
        self._text_buffer.messages = []
        self.text_win.rebuild_everything(self._text_buffer)
        self.refresh()
        self.core.doupdate()

    def execute_slash_command(self, txt):
        if txt.startswith('/'):
            self.input.key_enter()
            self.execute_command(txt)
        return self.reset_help_message()

    def completion(self):
        if isinstance(self.input, windows.Input):
            self.complete_commands(self.input)

    def on_input(self, key, raw):
        res = self.input.do_command(key, raw=raw)
        if res:
            return True
        if not raw and key in self.key_func:
            return self.key_func[key]()

    def close(self, arg=None):
        self.core.close_tab(self)

    def resize(self):
        self.need_resize = False
        if self.size.tab_degrade_y:
            info_win_size = 0
            tab_win_height = 0
        else:
            info_win_size = self.core.information_win_size
            tab_win_height = Tab.tab_win_height()

        self.text_win.resize(self.height - info_win_size - tab_win_height - 2,
                             self.width, 0, 0)
        self.text_win.rebuild_everything(self._text_buffer)
        self.info_header.resize(
            1, self.width, self.height - 2 - info_win_size - tab_win_height, 0)
        self.input.resize(1, self.width, self.height - 1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)

        if self.size.tab_degrade_y:
            display_info_win = False
        else:
            display_info_win = True

        self.text_win.refresh()
        self.info_header.refresh(self.remote_jid, self.text_win)
        self.refresh_tab_win()
        if display_info_win:
            self.info_win.refresh()
        self.input.refresh()

    def on_lose_focus(self):
        self.state = 'normal'

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(0)

    def on_close(self):
        super().on_close()
        self.command_clear()
        self.core.mam_tab = False

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height - 3:
            return
        self.text_win.resize(
            self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), self.width, 0, 0)
        self.info_header.resize(
            1, self.width, self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), 0)
