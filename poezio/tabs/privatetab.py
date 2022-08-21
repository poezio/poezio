"""
Module for the PrivateTab

A PrivateTab is a private conversation opened with someone from a MUC
(see muctab.py). The conversation happens with both JID being relative
to the MUC (room@server/nick1 and room@server/nick2).

This tab references his parent room, and is modified to keep track of
both participant’s nicks. It also has slightly different features than
the ConversationTab (such as tab-completion on nicks from the room).

"""
import asyncio
import curses
import logging
from datetime import datetime
from typing import Dict, Callable

from slixmpp import JID
from slixmpp.stanza import Message as SMessage

from poezio.tabs import OneToOneTab, MucTab, Tab

from poezio import common
from poezio import windows
from poezio import xhtml
from poezio.config import config, get_image_cache
from poezio.core.structs import Command
from poezio.decorators import refresh_wrapper
from poezio.theming import get_theme, dump_tuple
from poezio.decorators import command_args_parser
from poezio.text_buffer import CorrectionError
from poezio.ui.types import (
    Message,
    PersistentInfoMessage,
)

log = logging.getLogger(__name__)


class PrivateTab(OneToOneTab):
    """
    The tab containing a private conversation (someone from a MUC)
    """
    plugin_commands: Dict[str, Command] = {}
    plugin_keys: Dict[str, Callable] = {}
    message_type = 'chat'
    additional_information: Dict[str, Callable[[str], str]] = {}

    def __init__(self, core, jid, nick, initial=None):
        OneToOneTab.__init__(self, core, jid, initial)
        self.own_nick = nick
        self.info_header = windows.PrivateInfoWin()
        self.input = windows.MessageInput()
        # keys
        self.key_func['^I'] = self.completion
        # commands
        self.register_command(
            'info',
            self.command_info,
            desc=
            'Display some information about the user in the MUC: their role, affiliation, status and status message.',
            shortdesc='Info about the user.')
        self.register_command(
            'version',
            self.command_version,
            desc=
            'Get the software version of the current interlocutor (usually its XMPP client and Operating System).',
            shortdesc='Get the software version of a jid.')
        self.resize()
        self.parent_muc = self.core.tabs.by_name_and_class(self.jid.bare, MucTab)
        self.on = True
        self.update_commands()
        self.update_keys()

    @property
    def log_name(self) -> str:
        """Overriden from ChatTab because this is a case where we want the full JID"""
        return self.jid.full

    def remote_user_color(self):
        user = self.parent_muc.get_user_by_name(self.jid.resource)
        if user:
            return dump_tuple(user.color)
        return super().remote_user_color()

    @property
    def general_jid(self) -> JID:
        return self.jid

    def get_dest_jid(self) -> JID:
        return self.jid

    @property
    def nick(self) -> str:
        return self.get_nick()

    def ack_message(self, msg_id: str, msg_jid: JID):
        if JID(msg_jid).bare == self.core.xmpp.boundjid.bare:
            msg_jid = JID(self.jid.bare)
            msg_jid.resource = self.own_nick
        super().ack_message(msg_id, msg_jid)

    @staticmethod
    @refresh_wrapper.always
    def add_information_element(plugin_name, callback):
        """
        Lets a plugin add its own information to the PrivateInfoWin
        """
        PrivateTab.additional_information[plugin_name] = callback

    @staticmethod
    @refresh_wrapper.always
    def remove_information_element(plugin_name):
        del PrivateTab.additional_information[plugin_name]

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
        after = config.getstr('after_completion') + ' '
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

    async def handle_message(self, message: SMessage, display: bool = True):
        sent = message['from'].bare == self.core.xmpp.boundjid.bare
        jid = message['to'] if sent else message['from']
        with_nick = jid.resource
        sender_nick = with_nick
        if sent:
            sender_nick = (self.own_nick or self.core.own_nick)
        room_from = jid.bare
        use_xhtml = config.get_by_tabname(
            'enable_xhtml_im',
            jid.bare
        )
        tmp_dir = get_image_cache()
        if not sent:
            await self.core.events.trigger_async('private_msg', message, self)
        body = xhtml.get_body_from_message_stanza(
            message, use_xhtml=use_xhtml, extract_images_to=tmp_dir)
        if not body or not self:
            return
        delayed, date = common.find_delayed_tag(message)
        replaced = False
        user = self.parent_muc.get_user_by_name(with_nick)
        if message.get_plugin('replace', check=True):
            replaced_id = message['replace']['id']
            if replaced_id != '' and config.get_by_tabname(
                    'group_corrections', room_from):
                try:
                    self.modify_message(
                        body,
                        replaced_id,
                        message['id'],
                        user=user,
                        time=date,
                        jid=message['from'],
                        nickname=sender_nick)
                    replaced = True
                except CorrectionError:
                    log.debug('Unable to correct a message', exc_info=True)
        if not replaced:
            msg = Message(
                txt=body,
                time=date,
                history=delayed,
                nickname=sender_nick,
                nick_color=get_theme().COLOR_OWN_NICK if sent else None,
                user=user,
                identifier=message['id'],
                jid=message['from'],
            )
            if display:
                self.add_message(msg)
            else:
                self.log_message(msg)
        if sent:
            self.set_last_sent_message(message, correct=replaced)
        else:
            self.last_remote_message = datetime.now()

    @refresh_wrapper.always
    @command_args_parser.raw
    async def command_say(self, line: str, attention: bool = False, correct: bool = False) -> None:
        if not self.on:
            return
        await self._initial_log.wait()
        our_jid = JID(self.jid.bare)
        our_jid.resource = self.own_nick
        msg: SMessage = self.core.xmpp.make_message(
            mto=self.jid.full,
            mfrom=our_jid,
        )
        msg['type'] = 'chat'
        msg['body'] = line
        msg.enable('muc')
        # trigger the event BEFORE looking for colors.
        # This lets a plugin insert \x19xxx} colors, that will
        # be converted in xhtml.
        self.core.events.trigger('private_say', msg, self)
        if not msg['body']:
            return
        if correct or msg['replace']['id'] and self.last_sent_message:
            msg['replace']['id'] = self.last_sent_message['id']  # type: ignore
        else:
            del msg['replace']

        if msg['body'].find('\x19') != -1:
            msg.enable('html')
            msg['html']['body'] = xhtml.poezio_colors_to_html(msg['body'])
            msg['body'] = xhtml.clean_text(msg['body'])
        if config.get_by_tabname('send_chat_states', self.general_jid):
            if self.inactive:
                self.send_chat_state('inactive', always_send=True)
            else:
                msg['chat_state'] = 'active'
        if attention:
            msg['attention'] = True
        self.core.events.trigger('private_say_after', msg, self)
        if not msg['body']:
            return
        self.set_last_sent_message(msg, correct=correct)
        await self.core.handler.on_groupchat_private_message(msg, sent=True)
        # Our receipts slixmpp hack
        msg._add_receipt = True  # type: ignore
        msg.send()
        self.cancel_paused_delay()

    @command_args_parser.quoted(0, 1)
    async def command_version(self, args):
        """
        /version
        """
        if args:
            return await self.core.command.version(args[0])
        jid = self.jid.full
        iq = await self.core.xmpp.plugin['xep_0092'].get_version(jid)
        self.core.handler.on_version_result(iq)

    @command_args_parser.quoted(0, 1)
    def command_info(self, arg):
        """
        /info
        """
        if arg and arg[0]:
            self.parent_muc.command_info(arg[0])
        else:
            user = self.jid.resource
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
            0, self._text_buffer, force=self.ui_config_changed)
        self.ui_config_changed = False
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
        self.info_header.refresh(self.jid.full, self.text_win, self.chatstate,
                                 PrivateTab.additional_information)
        if display_info_win:
            self.info_win.refresh()

        self.refresh_tab_win()
        self.input.refresh()

    def refresh_info_header(self):
        self.info_header.refresh(self.jid.full, self.text_win, self.chatstate,
                                 PrivateTab.additional_information)
        self.input.refresh()

    def get_nick(self):
        return self.jid.resource

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
        tab = self.core.tabs.by_name_and_class(self.jid.bare, MucTab)
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
        tab = self.core.tabs.by_name_and_class(self.jid.bare, MucTab)
        if tab and tab.joined and config.get_by_tabname(
                'send_chat_states', self.general_jid) and self.on:
            self.send_chat_state('inactive')
        self.check_scrolled()

    def on_gain_focus(self):
        self.state = 'current'
        curses.curs_set(1)
        tab = self.core.tabs.by_name_and_class(self.jid.bare, MucTab)
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

    @refresh_wrapper.conditional
    def rename_user(self, old_nick, user):
        """
        The user changed her nick in the corresponding muc: update the tab’s name and
        display a message.
        """
        self.add_message(
            PersistentInfoMessage(
                '\x19%(nick_col)s}%(old)s\x19%(info_col)s} is now '
                'known as \x19%(nick_col)s}%(new)s' % {
                    'old': old_nick,
                    'new': user.nick,
                    'nick_col': dump_tuple(user.color),
                    'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
                },
            ),
        )
        new_jid = self.jid.bare + '/' + user.nick
        self._name = new_jid
        return self.core.tabs.current_tab is self

    @refresh_wrapper.conditional
    def user_left(self, status_message, user):
        """
        The user left the associated MUC
        """
        self.deactivate()
        theme = get_theme()
        if config.get_by_tabname('display_user_color_in_join_part',
                                 self.general_jid):
            color = dump_tuple(user.color)
        else:
            color = dump_tuple(theme.COLOR_REMOTE_USER)

        if not status_message:
            self.add_message(
                PersistentInfoMessage(
                    '\x19%(quit_col)s}%(spec)s \x19%(nick_col)s}'
                    '%(nick)s\x19%(info_col)s} has left the room' % {
                        'nick': user.nick,
                        'spec': theme.CHAR_QUIT,
                        'nick_col': color,
                        'quit_col': dump_tuple(theme.COLOR_QUIT_CHAR),
                        'info_col': dump_tuple(theme.COLOR_INFORMATION_TEXT)
                    },
                ),
            )
        else:
            self.add_message(
                PersistentInfoMessage(
                    '\x19%(quit_col)s}%(spec)s \x19%(nick_col)s}'
                    '%(nick)s\x19%(info_col)s} has left the room'
                    ' (%(status)s)' % {
                        'status': status_message,
                        'nick': user.nick,
                        'spec': theme.CHAR_QUIT,
                        'nick_col': color,
                        'quit_col': dump_tuple(theme.COLOR_QUIT_CHAR),
                        'info_col': dump_tuple(theme.COLOR_INFORMATION_TEXT)
                    },
                ),
            )
        return self.core.tabs.current_tab is self

    @refresh_wrapper.conditional
    def user_rejoined(self, nick):
        """
        The user (or at least someone with the same nick) came back in the MUC
        """
        self.activate()
        tab = self.parent_muc
        theme = get_theme()
        color = dump_tuple(theme.COLOR_REMOTE_USER)
        if tab and config.get_by_tabname('display_user_color_in_join_part',
                                         self.general_jid):
            user = tab.get_user_by_name(nick)
            if user:
                color = dump_tuple(user.color)
        self.add_message(
            PersistentInfoMessage(
                '\x19%(join_col)s}%(spec)s \x19%(color)s}%(nick)s\x19'
                '%(info_col)s} joined the room' % {
                    'nick': nick,
                    'color': color,
                    'spec': theme.CHAR_JOIN,
                    'join_col': dump_tuple(theme.COLOR_JOIN_CHAR),
                    'info_col': dump_tuple(theme.COLOR_INFORMATION_TEXT)
                },
            ),
        )
        return self.core.tabs.current_tab is self

    def activate(self, reason=None):
        self.on = True
        if reason:
            self.add_message(PersistentInfoMessage(reason))

    def deactivate(self, reason=None):
        self.on = False
        if reason:
            self.add_message(PersistentInfoMessage(reason))

    def matching_names(self):
        return [(3, self.jid.resource), (4, self.name)]

    def add_error(self, error_message):
        theme = get_theme()
        error = '\x19%s}%s\x19o' % (dump_tuple(theme.COLOR_CHAR_NACK),
                                    error_message)
        self.add_message(
            Message(
                error,
                highlight=True,
                nickname='Error',
                nick_color=theme.COLOR_ERROR_MSG,
            ),
        )
        self.core.refresh_window()
