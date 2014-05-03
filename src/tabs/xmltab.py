"""
The XMLTab is here for debugging purposes, it shows the incoming and
outgoing stanzas. It has a few useful functions that can filter stanzas
in order to only show the relevant ones, and it can also be frozen or
unfrozen on demand so that the relevant information is not drowned by
the traffic.
"""
from gettext import gettext as _

import logging
log = logging.getLogger(__name__)

import curses
from sleekxmpp.xmlstream import matcher
from sleekxmpp.xmlstream.handler import Callback

from . import Tab

import windows

class XMLTab(Tab):
    def __init__(self):
        Tab.__init__(self)
        self.state = 'normal'
        self.name = 'XMLTab'
        self.text_win = windows.TextWin()
        self.core.xml_buffer.add_window(self.text_win)
        self.info_header = windows.XMLInfoWin()
        self.default_help_message = windows.HelpText("/ to enter a command")
        self.register_command('close', self.close,
                shortdesc=_("Close this tab."))
        self.register_command('clear', self.command_clear,
                shortdesc=_('Clear the current buffer.'))
        self.register_command('reset', self.command_reset,
                shortdesc=_('Reset the stanza filter.'))
        self.register_command('filter_id', self.command_filter_id,
                usage='<id>',
                desc=_('Show only the stanzas with the id <id>.'),
                shortdesc=_('Filter by id.'))
        self.register_command('filter_xpath', self.command_filter_xpath,
                usage='<xpath>',
                desc=_('Show only the stanzas matching the xpath <xpath>.'),
                shortdesc=_('Filter by XPath.'))
        self.register_command('filter_xmlmask', self.command_filter_xmlmask,
                usage=_('<xml mask>'),
                desc=_('Show only the stanzas matching the given xml mask.'),
                shortdesc=_('Filter by xml mask.'))
        self.input = self.default_help_message
        self.key_func['^T'] = self.close
        self.key_func['^I'] = self.completion
        self.key_func["KEY_DOWN"] = self.on_scroll_down
        self.key_func["KEY_UP"] = self.on_scroll_up
        self.key_func["^K"] = self.on_freeze
        self.key_func["/"] = self.on_slash
        self.resize()
        # Used to display the infobar
        self.filter_type = ''
        self.filter = ''

    def on_freeze(self):
        """
        Freeze the display.
        """
        self.text_win.toggle_lock()
        self.refresh()

    def command_filter_xmlmask(self, arg):
        """/filter_xmlmask <xml mask>"""
        try:
            handler = Callback('custom matcher', matcher.MatchXMLMask(arg),
                    self.core.incoming_stanza)
            self.core.xmpp.remove_handler('custom matcher')
            self.core.xmpp.register_handler(handler)
            self.filter_type = "XML Mask Filter"
            self.filter = arg
            self.refresh()
        except:
            self.core.information('Invalid XML Mask', 'Error')
            self.command_reset('')

    def command_filter_id(self, arg):
        """/filter_id <id>"""
        self.core.xmpp.remove_handler('custom matcher')
        handler = Callback('custom matcher', matcher.MatcherId(arg),
                self.core.incoming_stanza)
        self.core.xmpp.register_handler(handler)
        self.filter_type = "Id Filter"
        self.filter = arg
        self.refresh()

    def command_filter_xpath(self, arg):
        """/filter_xpath <xpath>"""
        try:
            handler = Callback('custom matcher', matcher.MatchXPath(
                arg.replace('%n', self.core.xmpp.default_ns)),
                    self.core.incoming_stanza)
            self.core.xmpp.remove_handler('custom matcher')
            self.core.xmpp.register_handler(handler)
            self.filter_type = "XPath Filter"
            self.filter = arg
            self.refresh()
        except:
            self.core.information('Invalid XML Path', 'Error')
            self.command_reset('')

    def command_reset(self, arg):
        """/reset"""
        self.core.xmpp.remove_handler('custom matcher')
        self.core.xmpp.register_handler(self.core.all_stanzas)
        self.filter_type = ''
        self.filter = ''
        self.refresh()

    def on_slash(self):
        """
        '/' is pressed, activate the input
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message, self.execute_slash_command)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.do_command("/") # we add the slash

    def reset_help_message(self, _=None):
        if self.core.current_tab() is self:
            curses.curs_set(0)
        self.input = self.default_help_message
        self.input.refresh()
        self.core.doupdate()
        return True

    def on_scroll_up(self):
        return self.text_win.scroll_up(self.text_win.height-1)

    def on_scroll_down(self):
        return self.text_win.scroll_down(self.text_win.height-1)

    def command_clear(self, args):
        """
        /clear
        """
        self.core.xml_buffer.messages = []
        self.text_win.rebuild_everything(self.core.xml_buffer)
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
        self.core.close_tab()

    def resize(self):
        if self.size.tab_degrade_y:
            info_win_size = 0
            tab_win_height = 0
        else:
            info_win_size = self.core.information_win_size
            tab_win_height = Tab.tab_win_height()

        self.text_win.resize(self.height - info_win_size - tab_win_height - 2,
                             self.width, 0, 0)
        self.text_win.rebuild_everything(self.core.xml_buffer)
        self.info_header.resize(1, self.width,
                                self.height - 2 - info_win_size
                                    - tab_win_height,
                                0)
        self.input.resize(1, self.width, self.height-1, 0)
        self.push_size()

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)

        if self.size.tab_degrade_y:
            display_info_win = False
        else:
            display_info_win = True

        self.text_win.refresh()
        self.info_header.refresh(self.filter_type, self.filter, self.text_win)
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
        self.command_clear('')
        self.core.xml_tab = False

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        self.text_win.resize(self.height-2-self.core.information_win_size - Tab.tab_win_height(), self.width, 0, 0)
        self.info_header.resize(1, self.width, self.height-2-self.core.information_win_size - Tab.tab_win_height(), 0)


