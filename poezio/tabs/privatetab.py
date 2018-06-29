"""
Module for the PrivateTab

A PrivateTab is a private conversation opened with someone from a MUC
(see muctab.py). The conversation happens with both JID being relative
to the MUC (room@server/nick1 and room@server/nick2).

This tab references his parent room, and is modified to keep track of
both participant’s nicks. It also has slightly different features than
the ConversationTab (such as tab-completion on nicks from the room).

"""
import logging
log = logging.getLogger(__name__)

import curses

from poezio.tabs import OneToOneTab, MucTab, Tab

from poezio import windows
from poezio import xhtml
from poezio.common import safeJID
from poezio.config import config
from poezio.decorators import refresh_wrapper
from poezio.logger import logger
from poezio.theming import get_theme, dump_tuple
from poezio.decorators import command_args_parser


class PrivateTab(OneToOneTab):
    """
    The tab containg a private conversation (someone from a MUC)
    """
    message_type = 'chat'
    plugin_commands = {}
    additional_information = {}
    plugin_keys = {}

    def __init__(self, core, name, nick):
        OneToOneTab.__init__(self, core, name)
        self.own_nick = nick
        self.name = name
        self.text_win = windows.TextWin()
        self._text_buffer.add_window(self.text_win)
        self.info_header = windows.PrivateInfoWin()
        self.input = windows.MessageInput()
        # keys
        self.key_func['^I'] = self.completion
        # commands
        self.register_command(
            'info',
            self.command_info,
            desc=
            'Display some information about the user in the MUC: its/his/her role, affiliation, status and status message.',
            shortdesc='Info about the user.')
        self.register_command(
            'version',
            self.command_version,
            desc=
            'Get the software version of the current interlocutor (usually its XMPP client and Operating System).',
            shortdesc='Get the software version of a jid.')
        self.resize()
        self.parent_muc = self.core.tabs.by_name_and_class(
            safeJID(name).bare, MucTab)
        self.on = True
        self.update_commands()
        self.update_keys()

    def remote_user_color(self):
        user = self.parent_muc.get_user_by_name(safeJID(self.name).resource)
        if user:
            return dump_tuple(user.color)
        return super().remote_user_color()

    @property
    def general_jid(self):
        return self.name

    def get_dest_jid(self):
        return self.name

    @property
    def nick(self):
        return self.get_nick()

    @staticmethod
    def add_information_element(plugin_name, callback):
        """
        Lets a plugin add its own information to the PrivateInfoWin
        """
        PrivateTab.additional_information[plugin_name] = callback

    @staticmethod
    def remove_information_element(plugin_name):
        del PrivateTab.additional_information[plugin_name]

    def load_logs(self, log_nb):
        logs = logger.get_logs(
            safeJID(self.name).full.replace('/', '\\'), log_nb)
        return logs

    def log_message(self, txt, nickname, time=None, typ=1):
        """
        Log the messages in the archives.
        """
        if not logger.log_message(
                self.name, nickname, txt, date=time, typ=typ):
            self.core.information('Unable to write in the log file', 'Error')

    def on_close(self):
        super().on_close()
        self.parent_muc.privates.remove(self)

    def completion(self):
        """
        Called when Tab is pressed, complete the nickname in the input
        """
        if self.complete_commands(self.input):
            return

        # If we are not completing a command or a command's argument, complete a nick
        compare_users = lambda x: x.last_talked
        word_list = [user.nick for user in sorted(self.parent_muc.users, key=compare_users, reverse=True)\
                         if user.nick != self.own_nick]
        after = config.get('after_completion') + ' '
        input_pos = self.input.pos
        if ' ' not in self.input.get_text()[:input_pos] or (self.input.last_completion and\
                     self.input.get_text()[:input_pos] == self.input.last_completion + after):
            add_after = after
        else:
            add_after = ''
        self.input.auto_completion(word_list, add_after, quotify=False)
        empty_after = self.input.get_text() == '' or (
            self.input.get_text().startswith('/')
            and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)

    @command_args_parser.raw
    def command_say(self, line, attention=False, correct=False):
        if not self.on:
            return
        msg = self.core.xmpp.make_message(self.name)
        msg['type'] = 'chat'
        msg['body'] = line
        # trigger the event BEFORE looking for colors.
        # This lets a plugin insert \x19xxx} colors, that will
        # be converted in xhtml.
        self.core.events.trigger('private_say', msg, self)
        if not msg['body']:
            self.cancel_paused_delay()
            self.text_win.refresh()
            self.input.refresh()
            return
        user = self.parent_muc.get_user_by_name(self.own_nick)
        replaced = False
        if correct or msg['replace']['id']:
            msg['replace']['id'] = self.last_sent_message['id']
            if config.get_by_tabname('group_corrections', self.name):
                try:
                    self.modify_message(
                        msg['body'],
                        self.last_sent_message['id'],
                        msg['id'],
                        user=user,
                        jid=self.core.xmpp.boundjid,
                        nickname=self.own_nick)
                    replaced = True
                except:
                    log.error('Unable to correct a message', exc_info=True)
        else:
            del msg['replace']

        if msg['body'].find('\x19') != -1:
            msg.enable('html')
            msg['html']['body'] = xhtml.poezio_colors_to_html(msg['body'])
            msg['body'] = xhtml.clean_text(msg['body'])
        if config.get_by_tabname('send_chat_states', self.general_jid):
            needed = 'inactive' if self.inactive else 'active'
            msg['chat_state'] = needed
        if attention:
            msg['attention'] = True
        self.core.events.trigger('private_say_after', msg, self)
        if not msg['body']:
            self.cancel_paused_delay()
            self.text_win.refresh()
            self.input.refresh()
            return
        if not replaced:
            self.add_message(
                msg['body'],
                nickname=self.own_nick or self.core.own_nick,
                forced_user=user,
                nick_color=get_theme().COLOR_OWN_NICK,
                identifier=msg['id'],
                jid=self.core.xmpp.boundjid,
                typ=1)

        self.last_sent_message = msg
        msg._add_receipt = True
        msg.send()
        self.cancel_paused_delay()
        self.text_win.refresh()
        self.input.refresh()

    @command_args_parser.quoted(0, 1)
    def command_version(self, args):
        """
        /version
        """
        if args:
            return self.core.command.version(args[0])
        jid = safeJID(self.name)
        self.core.xmpp.plugin['xep_0092'].get_version(
            jid, callback=self.core.handler.on_version_result)

    @command_args_parser.quoted(0, 1)
    def command_info(self, arg):
        """
        /info
        """
        if arg and arg[0]:
            self.parent_muc.command_info(arg[0])
        else:
            user = safeJID(self.name).resource
            self.parent_muc.command_info(user)

    def resize(self):
        self.need_resize = False

        if self.size.tab_degrade_y:
            info_win_height = 0
            tab_win_height = 0
        else:
            info_win_height = self.core.information_win_size
            tab_win_height = Tab.tab_win_height()

        self.text_win.resize(
            self.height - 2 - info_win_height - tab_win_height, self.width, 0,
            0)
        self.text_win.rebuild_everything(self._text_buffer)
        self.info_header.resize(
            1, self.width, self.height - 2 - info_win_height - tab_win_height,
            0)
        self.input.resize(1, self.width, self.height - 1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        display_info_win = not self.size.tab_degrade_y

        self.text_win.refresh()
        self.info_header.refresh(self.name, self.text_win, self.chatstate,
                                 PrivateTab.additional_information)
        if display_info_win:
            self.info_win.refresh()

        self.refresh_tab_win()
        self.input.refresh()

    def refresh_info_header(self):
        self.info_header.refresh(self.name, self.text_win, self.chatstate,
                                 PrivateTab.additional_information)
        self.input.refresh()

    def get_nick(self):
        return safeJID(self.name).resource

    def on_input(self, key, raw):
        if not raw and key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key, raw=raw)
        if not self.on:
            return False
        empty_after = self.input.get_text() == '' or (
            self.input.get_text().startswith('/')
            and not self.input.get_text().startswith('//'))
        tab = self.core.tabs.by_name_and_class(safeJID(self.name).bare, MucTab)
        if tab and tab.joined:
            self.send_composing_chat_state(empty_after)
        return False

    def on_lose_focus(self):
        if self.input.text:
            self.state = 'nonempty'
        else:
            self.state = 'normal'

        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        tab = self.core.tabs.by_name_and_class(safeJID(self.name).bare, MucTab)
        if tab and tab.joined and config.get_by_tabname(
                'send_chat_states', self.general_jid) and self.on:
            self.send_chat_state('inactive')
        self.check_scrolled()

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(1)
        tab = self.core.tabs.by_name_and_class(safeJID(self.name).bare, MucTab)
        if tab and tab.joined and config.get_by_tabname(
                'send_chat_states',
                self.general_jid,
        ) and not self.input.get_text() and self.on:
            self.send_chat_state('active')

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height - 3:
            return
        self.text_win.resize(
            self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), self.width, 0, 0)
        self.info_header.resize(
            1, self.width, self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), 0)

    def get_text_window(self):
        return self.text_win

    @refresh_wrapper.conditional
    def rename_user(self, old_nick, user):
        """
        The user changed her nick in the corresponding muc: update the tab’s name and
        display a message.
        """
        self.add_message(
            '\x19%(nick_col)s}%(old)s\x19%(info_col)s} is now '
            'known as \x19%(nick_col)s}%(new)s' % {
                'old': old_nick,
                'new': user.nick,
                'nick_col': dump_tuple(user.color),
                'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
            },
            typ=2)
        new_jid = safeJID(self.name).bare + '/' + user.nick
        self.name = new_jid
        return self.core.tabs.current_tab is self

    @refresh_wrapper.conditional
    def user_left(self, status_message, user):
        """
        The user left the associated MUC
        """
        self.deactivate()
        if config.get_by_tabname('display_user_color_in_join_part',
                                 self.general_jid):
            color = dump_tuple(user.color)
        else:
            color = dump_tuple(get_theme().COLOR_REMOTE_USER)

        if not status_message:
            self.add_message(
                '\x19%(quit_col)s}%(spec)s \x19%(nick_col)s}'
                '%(nick)s\x19%(info_col)s} has left the room' % {
                    'nick': user.nick,
                    'spec': get_theme().CHAR_QUIT,
                    'nick_col': color,
                    'quit_col': dump_tuple(get_theme().COLOR_QUIT_CHAR),
                    'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
                },
                typ=2)
        else:
            self.add_message(
                '\x19%(quit_col)s}%(spec)s \x19%(nick_col)s}'
                '%(nick)s\x19%(info_col)s} has left the room'
                ' (%(status)s)' % {
                    'status': status_message,
                    'nick': user.nick,
                    'spec': get_theme().CHAR_QUIT,
                    'nick_col': color,
                    'quit_col': dump_tuple(get_theme().COLOR_QUIT_CHAR),
                    'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
                },
                typ=2)
        return self.core.tabs.current_tab is self

    @refresh_wrapper.conditional
    def user_rejoined(self, nick):
        """
        The user (or at least someone with the same nick) came back in the MUC
        """
        self.activate()
        self.check_features()
        tab = self.parent_muc
        color = dump_tuple(get_theme().COLOR_REMOTE_USER)
        if tab and config.get_by_tabname('display_user_color_in_join_part',
                                         self.general_jid):
            user = tab.get_user_by_name(nick)
            if user:
                color = dump_tuple(user.color)
        self.add_message(
            '\x19%(join_col)s}%(spec)s \x19%(color)s}%(nick)s\x19'
            '%(info_col)s} joined the room' % {
                'nick': nick,
                'color': color,
                'spec': get_theme().CHAR_JOIN,
                'join_col': dump_tuple(get_theme().COLOR_JOIN_CHAR),
                'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
            },
            typ=2)
        return self.core.tabs.current_tab is self

    def activate(self, reason=None):
        self.on = True
        if reason:
            self.add_message(txt=reason, typ=2)

    def deactivate(self, reason=None):
        self.on = False
        if reason:
            self.add_message(txt=reason, typ=2)

    def matching_names(self):
        return [(3, safeJID(self.name).resource), (4, self.name)]

    def add_error(self, error_message):
        error = '\x19%s}%s\x19o' % (dump_tuple(get_theme().COLOR_CHAR_NACK),
                                    error_message)
        self.add_message(
            error,
            highlight=True,
            nickname='Error',
            nick_color=get_theme().COLOR_ERROR_MSG,
            typ=2)
        self.core.refresh_window()
