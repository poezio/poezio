"""
The XMLTab is here for debugging purposes, it shows the incoming and
outgoing stanzas. It has a few useful functions that can filter stanzas
in order to only show the relevant ones, and it can also be frozen or
unfrozen on demand so that the relevant information is not drowned by
the traffic.
"""
import logging
log = logging.getLogger(__name__)

import curses
import os
from slixmpp.xmlstream import matcher
from slixmpp.xmlstream.tostring import tostring
from slixmpp.xmlstream.stanzabase import ElementBase
from xml.etree import ElementTree as ET

from poezio.tabs import Tab

from poezio import text_buffer
from poezio import windows
from poezio.xhtml import clean_text
from poezio.decorators import command_args_parser, refresh_wrapper
from poezio.common import safeJID


class MatchJID:
    def __init__(self, jid, dest=''):
        self.jid = jid
        self.dest = dest

    def match(self, xml):
        from_ = safeJID(xml['from'])
        to_ = safeJID(xml['to'])
        if self.jid.full == self.jid.bare:
            from_ = from_.bare
            to_ = to_.bare

        if self.dest == 'from':
            return from_ == self.jid
        elif self.dest == 'to':
            return to_ == self.jid
        return self.jid in (from_, to_)

    def __repr__(self):
        return '%s%s%s' % (self.dest, ': ' if self.dest else '', self.jid)


MATCHERS_MAPPINGS = {
    MatchJID: ('JID', repr),
    matcher.MatcherId: ('ID', lambda obj: obj._criteria),
    matcher.MatchXMLMask: ('XMLMask', lambda obj: tostring(obj._criteria)),
    matcher.MatchXPath: ('XPath', lambda obj: obj._criteria)
}


class XMLTab(Tab):
    def __init__(self, core):
        Tab.__init__(self, core)
        self.state = 'normal'
        self.name = 'XMLTab'
        self.filters = []

        self.core_buffer = self.core.xml_buffer
        self.filtered_buffer = text_buffer.TextBuffer()

        self.info_header = windows.XMLInfoWin()
        self.text_win = windows.XMLTextWin()
        self.core_buffer.add_window(self.text_win)
        self.default_help_message = windows.HelpText("/ to enter a command")

        self.register_command('close', self.close, shortdesc="Close this tab.")
        self.register_command(
            'clear', self.command_clear, shortdesc='Clear the current buffer.')
        self.register_command(
            'filter_reset',
            self.command_filter_reset,
            shortdesc='Reset the stanza filter.')
        self.register_command(
            'filter_id',
            self.command_filter_id,
            usage='<id>',
            desc='Show only the stanzas with the id <id>.',
            shortdesc='Filter by id.')
        self.register_command(
            'filter_xpath',
            self.command_filter_xpath,
            usage='<xpath>',
            desc='Show only the stanzas matching the xpath <xpath>.'
            ' Any occurrences of %n will be replaced by jabber:client.',
            shortdesc='Filter by XPath.')
        self.register_command(
            'filter_jid',
            self.command_filter_jid,
            usage='<jid>',
            desc=
            'Show only the stanzas matching the jid <jid> in from= or to=.',
            shortdesc='Filter by JID.')
        self.register_command(
            'filter_from',
            self.command_filter_from,
            usage='<jid>',
            desc='Show only the stanzas matching the jid <jid> in from=.',
            shortdesc='Filter by JID from.')
        self.register_command(
            'filter_to',
            self.command_filter_to,
            usage='<jid>',
            desc='Show only the stanzas matching the jid <jid> in to=.',
            shortdesc='Filter by JID to.')
        self.register_command(
            'filter_xmlmask',
            self.command_filter_xmlmask,
            usage='<xml mask>',
            desc='Show only the stanzas matching the given xml mask.',
            shortdesc='Filter by xml mask.')
        self.register_command(
            'dump',
            self.command_dump,
            usage='<filename>',
            desc='Writes the content of the XML buffer into a file.',
            shortdesc='Write in a file.')
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

    def gen_filter_repr(self):
        if not self.filters:
            self.filter_type = ''
            self.filter = ''
            return
        filter_types = map(lambda x: MATCHERS_MAPPINGS[type(x)][0],
                           self.filters)
        filter_strings = map(lambda x: MATCHERS_MAPPINGS[type(x)][1](x),
                             self.filters)
        self.filter_type = ','.join(filter_types)
        self.filter = ','.join(filter_strings)

    def update_filters(self, matcher):
        if not self.filters:
            messages = self.core_buffer.messages[:]
            self.filtered_buffer.messages = []
            self.core_buffer.del_window(self.text_win)
            self.filtered_buffer.add_window(self.text_win)
        else:
            messages = self.filtered_buffer.messages
            self.filtered_buffer.messages = []
        self.filters.append(matcher)
        new_messages = []
        for msg in messages:
            try:
                if msg.txt.strip() and self.match_stanza(
                        ElementBase(ET.fromstring(clean_text(msg.txt)))):
                    new_messages.append(msg)
            except ET.ParseError:
                log.debug('Malformed XML : %s', msg.txt, exc_info=True)
        self.filtered_buffer.messages = new_messages
        self.text_win.rebuild_everything(self.filtered_buffer)
        self.gen_filter_repr()

    def on_freeze(self):
        """
        Freeze the display.
        """
        self.text_win.toggle_lock()
        self.refresh()

    def match_stanza(self, stanza):
        for matcher_ in self.filters:
            if not matcher_.match(stanza):
                return False
        return True

    @command_args_parser.raw
    def command_filter_xmlmask(self, mask):
        """/filter_xmlmask <xml mask>"""
        try:
            self.update_filters(matcher.MatchXMLMask(mask))
            self.refresh()
        except Exception as e:
            self.core.information('Invalid XML Mask: %s' % e, 'Error')
            self.command_filter_reset()

    @command_args_parser.raw
    def command_filter_to(self, jid):
        """/filter_jid_to <jid>"""
        jid_obj = safeJID(jid)
        if not jid_obj:
            return self.core.information('Invalid JID: %s' % jid, 'Error')

        self.update_filters(MatchJID(jid_obj, dest='to'))
        self.refresh()

    @command_args_parser.raw
    def command_filter_from(self, jid):
        """/filter_jid_from <jid>"""
        jid_obj = safeJID(jid)
        if not jid_obj:
            return self.core.information('Invalid JID: %s' % jid, 'Error')

        self.update_filters(MatchJID(jid_obj, dest='from'))
        self.refresh()

    @command_args_parser.raw
    def command_filter_jid(self, jid):
        """/filter_jid <jid>"""
        jid_obj = safeJID(jid)
        if not jid_obj:
            return self.core.information('Invalid JID: %s' % jid, 'Error')

        self.update_filters(MatchJID(jid_obj))
        self.refresh()

    @command_args_parser.quoted(1)
    def command_filter_id(self, args):
        """/filter_id <id>"""
        if args is None:
            return self.core.command.help('filter_id')

        self.update_filters(matcher.MatcherId(args[0]))
        self.refresh()

    @command_args_parser.raw
    def command_filter_xpath(self, xpath):
        """/filter_xpath <xpath>"""
        try:
            self.update_filters(
                matcher.MatchXPath(
                    xpath.replace('%n', self.core.xmpp.default_ns)))
            self.refresh()
        except:
            self.core.information('Invalid XML Path', 'Error')
            self.command_filter_reset()

    @command_args_parser.ignored
    def command_filter_reset(self):
        """/filter_reset"""
        if self.filters:
            self.filters = []
            self.filtered_buffer.del_window(self.text_win)
            self.core_buffer.add_window(self.text_win)
            self.text_win.rebuild_everything(self.core_buffer)
        self.filter_type = ''
        self.filter = ''
        self.refresh()

    @command_args_parser.quoted(1)
    def command_dump(self, args):
        """/dump <filename>"""
        if args is None:
            return self.core.command.help('dump')
        if self.filters:
            xml = self.filtered_buffer.messages[:]
        else:
            xml = self.core_buffer.messages[:]
        text = '\n'.join(
            ('%s %s %s' % (msg.str_time, msg.nickname, clean_text(msg.txt))
             for msg in xml))
        filename = os.path.expandvars(os.path.expanduser(args[0]))
        try:
            with open(filename, 'w') as fd:
                fd.write(text)
        except Exception as e:
            self.core.information('Could not write the XML dump: %s' % e,
                                  'Error')

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

    @command_args_parser.ignored
    def command_clear(self):
        """
        /clear
        """
        self.core_buffer.messages = []
        self.filtered_buffer.messages = []
        self.text_win.rebuild_everything(self.filtered_buffer)
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
        self.text_win.rebuild_everything(self.core_buffer)
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
        super().on_close()
        self.command_clear()
        self.core.xml_tab = False

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height - 3:
            return
        self.text_win.resize(
            self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), self.width, 0, 0)
        self.info_header.resize(
            1, self.width, self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), 0)
