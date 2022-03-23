"""
Module for the MucTab

A MucTab is a tab for multi-user chats as defined in XEP-0045.

It keeps track of many things such as part/joins, maintains an
user list, and updates private tabs when necessary.
"""

from __future__ import annotations

import asyncio
import bisect
import curses
import logging
import os
import random
import re
import functools
from copy import copy
from dataclasses import dataclass
from datetime import datetime
from typing import (
    cast,
    Any,
    Dict,
    Callable,
    List,
    Optional,
    Tuple,
    Union,
    Set,
    Type,
    Pattern,
    TYPE_CHECKING,
)

from slixmpp import InvalidJID, JID, Presence, Iq, Message as SMessage
from slixmpp.exceptions import IqError, IqTimeout
from poezio.tabs import ChatTab, Tab, SHOW_NAME

from poezio import common
from poezio import multiuserchat as muc
from poezio import timed_events
from poezio import windows
from poezio import xhtml
from poezio.common import to_utc
from poezio.config import config, get_image_cache
from poezio.core.structs import Command
from poezio.decorators import refresh_wrapper, command_args_parser
from poezio.logger import logger
from poezio.log_loader import LogLoader, MAMFiller
from poezio.roster import roster
from poezio.text_buffer import CorrectionError
from poezio.theming import get_theme, dump_tuple
from poezio.user import User
from poezio.core.structs import Completion, Status
from poezio.ui.types import (
    BaseMessage,
    InfoMessage,
    Message,
    MucOwnJoinMessage,
    MucOwnLeaveMessage,
    PersistentInfoMessage,
)

if TYPE_CHECKING:
    from poezio.core.core import Core
    from slixmpp.plugins.xep_0004 import Form

log = logging.getLogger(__name__)

NS_MUC_USER = 'http://jabber.org/protocol/muc#user'

COMPARE_USERS_LAST_TALKED = lambda x: x.last_talked


@dataclass
class MessageData:
    message: SMessage
    delayed: bool
    date: Optional[datetime]
    nick: str
    user: Optional[User]
    room_from: str
    body: str
    is_history: bool


class MucTab(ChatTab):
    """
    The tab containing a multi-user-chat room.
    It contains a userlist, an input, a topic, an information and a chat zone
    """
    message_type = 'groupchat'
    plugin_commands: Dict[str, Command] = {}
    plugin_keys: Dict[str, Callable[..., Any]] = {}
    additional_information: Dict[str, Callable[[str], str]] = {}
    lagged: bool = False

    def __init__(self, core: Core, jid: JID, nick: str, password: Optional[str] = None) -> None:
        ChatTab.__init__(self, core, jid)
        self.joined = False
        self._state = 'disconnected'
        # our nick in the MUC
        self.own_nick = nick
        # self User object
        self.own_user: Optional[User] = None
        self.password = password
        # buffered presences
        self.presence_buffer: List[Presence] = []
        # userlist
        self.users: List[User] = []
        # private conversations
        self.privates: List[Tab] = []
        self.topic = ''
        self.topic_from = ''
        # Self ping event, so we can cancel it when we leave the room
        self.self_ping_event: Optional[timed_events.DelayedEvent] = None
        # UI stuff
        self.topic_win = windows.Topic()
        self.v_separator = windows.VerticalSeparator()
        self.user_win = windows.UserList()
        self.info_header = windows.MucInfoWin()
        self.input: windows.MessageInput = windows.MessageInput()
        # List of ignored users
        self.ignores: List[User] = []
        # keys
        self.register_keys()
        self.update_keys()
        # commands
        self.register_commands()
        self.update_commands()
        self.resize()

    @property
    def general_jid(self) -> JID:
        return self.jid

    def check_send_chat_state(self) -> bool:
        "If we should send a chat state"
        return self.joined

    @property
    def last_connection(self) -> Optional[datetime]:
        last_message = self._text_buffer.last_message
        if last_message:
            return last_message.time
        return None

    @staticmethod
    @refresh_wrapper.always
    def add_information_element(plugin_name: str, callback: Callable[[str], str]) -> None:
        """
        Lets a plugin add its own information to the MucInfoWin
        """
        MucTab.additional_information[plugin_name] = callback

    @staticmethod
    @refresh_wrapper.always
    def remove_information_element(plugin_name: str) -> None:
        """
        Lets a plugin add its own information to the MucInfoWin
        """
        del MucTab.additional_information[plugin_name]

    def cancel_config(self, form: Form) -> None:
        """
        The user do not want to send their config, send an iq cancel
        """
        asyncio.create_task(self.core.xmpp['xep_0045'].cancel_config(self.jid))
        self.core.close_tab()

    def send_config(self, form: Form) -> None:
        """
        The user sends their config to the server
        """
        asyncio.create_task(self.core.xmpp['xep_0045'].set_room_config(self.jid, form))
        self.core.close_tab()

    def join(self) -> None:
        """
        Join the room
        """
        seconds: Optional[int]
        status = self.core.get_status()
        if self.last_connection:
            delta = to_utc(datetime.now()) - to_utc(self.last_connection)
            seconds = delta.seconds + delta.days * 24 * 3600
        else:
            last_message = self._text_buffer.find_last_message()
            seconds = None
            if last_message is not None:
                seconds = (datetime.now() - last_message.time).seconds
        use_log = config.get_by_tabname('mam_sync', self.general_jid)
        mam_sync = config.get_by_tabname('mam_sync', self.general_jid)
        if self.mam_filler is None and use_log and mam_sync:
            limit = config.get_by_tabname('mam_sync_limit', self.jid)
            self.mam_filler = MAMFiller(logger, self, limit)
        muc.join_groupchat(
            self.core,
            self.jid,
            self.own_nick,
            self.password or '',
            status=status.message,
            show=status.show,
            seconds=seconds)

    def leave_room(self, message: str) -> None:
        if self.joined:
            theme = get_theme()
            info_col = dump_tuple(theme.COLOR_INFORMATION_TEXT)
            char_quit = theme.CHAR_QUIT
            spec_col = dump_tuple(theme.COLOR_QUIT_CHAR)

            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(theme.COLOR_OWN_NICK)
            else:
                color = "3"

            if message:
                msg = ('\x19%(color_spec)s}%(spec)s\x19%(info_col)s} '
                       'You (\x19%(color)s}%(nick)s\x19%(info_col)s})'
                       ' left the room'
                       ' (\x19o%(reason)s\x19%(info_col)s})') % {
                           'info_col': info_col,
                           'reason': message,
                           'spec': char_quit,
                           'color': color,
                           'color_spec': spec_col,
                           'nick': self.own_nick,
                       }
            else:
                msg = ('\x19%(color_spec)s}%(spec)s\x19%(info_col)s} '
                       'You (\x19%(color)s}%(nick)s\x19%(info_col)s})'
                       ' left the room') % {
                           'info_col': info_col,
                           'spec': char_quit,
                           'color': color,
                           'color_spec': spec_col,
                           'nick': self.own_nick,
                       }
            self.add_message(MucOwnLeaveMessage(msg))
            self.disconnect()
            muc.leave_groupchat(self.core.xmpp, self.jid, self.own_nick,
                                message)
            self.core.disable_private_tabs(self.jid.bare, reason=msg)
        else:
            self.presence_buffer = []
            self.users = []
            muc.leave_groupchat(self.core.xmpp, self.jid, self.own_nick,
                                message)

    async def change_affiliation(
        self,
        nick_or_jid: Union[str, JID],
        affiliation: str,
        reason: str = ''
    ) -> None:
        """
        Change the affiliation of a nick or JID
        """
        if not self.joined:
            return

        valid_affiliations = ('outcast', 'none', 'member', 'admin', 'owner')
        if affiliation not in valid_affiliations:
            self.core.information(
                'The affiliation must be one of ' +
                ', '.join(valid_affiliations), 'Error')
            return
        jid = None
        nick = None
        for user in self.users:
            if user.nick == nick_or_jid:
                jid = user.jid
                nick = user.nick
                break
        if jid is None:
            try:
                jid = JID(nick_or_jid)
            except InvalidJID:
                self.core.information(
                    f'Invalid JID or missing occupant: {nick_or_jid}',
                    'Error'
                )
                return

        try:
            if affiliation != 'member':
                nick = None
            await self.core.xmpp['xep_0045'].set_affiliation(
                self.jid,
                jid=jid,
                nick=nick,
                affiliation=affiliation,
                reason=reason
            )
            self.core.information(
                f"Affiliation of {jid} set to {affiliation} successfully",
                "Info"
            )
        except (IqError, IqTimeout) as exc:
            self.core.information(
                f"Could not set affiliation '{affiliation}' for '{jid}': {exc}",
                "Warning",
            )

    async def change_role(self, nick: str, role: str, reason: str = '') -> None:
        """
        Change the role of a nick
        """

        valid_roles = ('none', 'visitor', 'participant', 'moderator')

        if not self.joined or role not in valid_roles:
            self.core.information(
                'The role must be one of ' + ', '.join(valid_roles), 'Error')
            return

        try:
            target_jid = copy(self.jid)
            target_jid.resource = nick
        except InvalidJID:
            self.core.information('Invalid nick', 'Info')
            return

        try:
            await self.core.xmpp['xep_0045'].set_role(
                self.jid, nick, role=role, reason=reason
            )
            self.core.information(
                f'Role of {nick} changed to {role} successfully.'
                'Info'
            )
        except (IqError, IqTimeout) as e:
            self.core.information(
                "Could not set role '%s' for '%s': %s" % (role, nick, e),
                "Warning")

    @refresh_wrapper.conditional
    def print_info(self, nick: str) -> bool:
        """Print information about a user"""
        user = self.get_user_by_name(nick)
        if not user:
            return False

        theme = get_theme()
        inf = '\x19' + dump_tuple(theme.COLOR_INFORMATION_TEXT) + '}'
        if user.jid:
            user_jid = '%s (\x19%s}%s\x19o%s)' % (
                inf, dump_tuple(theme.COLOR_MUC_JID), user.jid, inf)
        else:
            user_jid = ''
        info = ('\x19%(user_col)s}%(nick)s\x19o%(jid)s%(info)s: show: '
                '\x19%(show_col)s}%(show)s\x19o%(info)s, affiliation: '
                '\x19%(role_col)s}%(affiliation)s\x19o%(info)s, role: '
                '\x19%(role_col)s}%(role)s\x19o%(status)s') % {
                    'user_col': dump_tuple(user.color),
                    'nick': nick,
                    'jid': user_jid,
                    'info': inf,
                    'show_col': dump_tuple(theme.color_show(user.show)),
                    'show': user.show or 'Available',
                    'role_col': dump_tuple(theme.color_role(user.role)),
                    'affiliation': user.affiliation or 'None',
                    'role': user.role or 'None',
                    'status': '\n%s' % user.status if user.status else ''
                }
        self.add_message(InfoMessage(info))
        return True

    def change_topic(self, topic: str) -> None:
        """Change the current topic"""
        self.core.xmpp.plugin['xep_0045'].set_subject(self.jid, topic)

    @refresh_wrapper.always
    def show_topic(self) -> None:
        """
        Print the current topic
        """
        theme = get_theme()
        info_text = dump_tuple(theme.COLOR_INFORMATION_TEXT)
        norm_text = dump_tuple(theme.COLOR_NORMAL_TEXT)
        if self.topic_from:
            user = self.get_user_by_name(self.topic_from)
            if user:
                user_text = dump_tuple(user.color)
                user_string = '\x19%s}(set by \x19%s}%s\x19%s})' % (
                    info_text, user_text, user.nick, info_text)
            else:
                user_string = self.topic_from
        else:
            user_string = ''

        self.add_message(
            InfoMessage(
                "The subject of the room is: \x19%s}%s %s" %
                (norm_text, self.topic, user_string),
            ),
        )

    @refresh_wrapper.always
    def recolor(self) -> None:
        """Recolor the current MUC users"""
        for user in self.users:
            if user is self.own_user:
                continue
            color = self.search_for_color(user.nick)
            if color != '':
                continue
            user.set_deterministic_color()
        self.text_win.rebuild_everything(self._text_buffer)

    @refresh_wrapper.conditional
    def set_nick_color(self, nick: str, color: str) -> bool:
        "Set a custom color for a nick, permanently"
        user = self.get_user_by_name(nick)
        if color not in xhtml.colors and color not in ('unset', 'random'):
            return False
        if nick == self.own_nick:
            return False
        if color == 'unset':
            if config.remove_and_save(nick, 'muc_colors'):
                self.core.information('Color for nick %s unset' % (nick),
                                      'Info')
        else:
            if color == 'random':
                color = random.choice(list(xhtml.colors))
            if user:
                user.change_color(color)
            config.set_and_save(nick, color, 'muc_colors')
            nick_color_aliases = config.get_by_tabname('nick_color_aliases',
                                                       self.jid)
            if nick_color_aliases:
                # if any user in the room has a nick which is an alias of the
                # nick, update its color
                for tab in self.core.get_tabs(MucTab):
                    for u in tab.users:
                        nick_alias = re.sub('^_*', '', u.nick)
                        nick_alias = re.sub('_*$', '', nick_alias)
                        if nick_alias == nick:
                            u.change_color(color)
        self.text_win.rebuild_everything(self._text_buffer)
        return True

    def on_input(self, key: str, raw: bool) -> bool:
        if not raw and key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key, raw=raw)
        empty_after = self.input.get_text() == ''
        empty_after = empty_after or (
            self.input.get_text().startswith('/')
            and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)
        return False

    def get_nick(self) -> str:
        if config.getbool('show_muc_jid'):
            return cast(str, self.jid)
        bookmark = self.core.bookmarks[self.jid]
        if bookmark is not None and bookmark.name:
            return bookmark.name
        # TODO: send the disco#info identity name here, if it exists.
        return self.jid.node

    def on_lose_focus(self) -> None:
        if self.joined:
            if self.input.text:
                self.state = 'nonempty'
            elif self.lagged:
                self.state = 'disconnected'
            else:
                self.state = 'normal'
        else:
            self.state = 'disconnected'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        if config.get_by_tabname('send_chat_states', self.general_jid):
            self.send_chat_state('inactive')
        self.check_scrolled()

    def on_gain_focus(self) -> None:
        self.state = 'current'
        if (self.text_win.built_lines and self.text_win.built_lines[-1] is None
                and not config.getbool('show_useless_separator')):
            self.text_win.remove_line_separator()
        curses.curs_set(1)
        if self.joined and config.get_by_tabname(
                'send_chat_states',
                self.general_jid) and not self.input.get_text():
            self.send_chat_state('active')

    async def handle_message(self, message: SMessage) -> bool:
        """Parse an incoming message

        Returns False if the message was dropped silently.
        """
        room_from = message['from'].bare
        nick_from = message['mucnick']
        user = self.get_user_by_name(nick_from)
        if user and user in self.ignores:
            return False

        await self.core.events.trigger_async('muc_msg', message, self)
        use_xhtml = config.get_by_tabname('enable_xhtml_im', room_from)
        tmp_dir = get_image_cache()
        body = xhtml.get_body_from_message_stanza(
            message, use_xhtml=use_xhtml, extract_images_to=tmp_dir)

        # TODO: #3314. Is this a MUC reflection?
        # Is this an encrypted message? Is so ignore.
        #   It is not possible in the OMEMO case to decrypt these messages
        #   since we don't encrypt for our own device (something something
        #   forward secrecy), but even for non-FS encryption schemes anyway
        #   messages shouldn't have changed after a round-trip to the room.
        # Otherwire replace the matching message we sent.
        if not body:
            return False

        old_state = self.state
        delayed, date = common.find_delayed_tag(message)
        is_history = not self.joined and delayed

        mdata = MessageData(
            message, delayed, date, nick_from, user, room_from, body,
            is_history
        )

        replaced = False
        if message.xml.find('{urn:xmpp:message-correct:0}replace') is not None:
            replaced = await self._handle_correction_message(mdata)
        if not replaced:
            await self._handle_normal_message(mdata)
        if mdata.nick == self.own_nick:
            self.set_last_sent_message(message, correct=replaced)
        self._refresh_after_message(old_state)
        return True

    def _refresh_after_message(self, old_state: str) -> None:
        """Refresh the appropriate UI after a message is received"""
        if self is self.core.tabs.current_tab:
            self.refresh()
        elif self.state != old_state:
            self.core.refresh_tab_win()
            current = self.core.tabs.current_tab
            current.refresh_input()
        self.core.doupdate()

    async def _handle_correction_message(self, message: MessageData) -> bool:
        """Process a correction message.

        Returns true if a message was actually corrected.
        """
        replaced_id = message.message['replace']['id']
        if replaced_id != '' and config.get_by_tabname(
                'group_corrections', message.room_from):
            try:
                delayed_date = message.date or datetime.now()
                modify_hl = self.modify_message(
                    message.body,
                    replaced_id,
                    message.message['id'],
                    time=delayed_date,
                    delayed=message.delayed,
                    nickname=message.nick,
                    user=message.user
                )
                if modify_hl:
                    await self.core.events.trigger_async(
                        'highlight',
                        message.message,
                        self
                    )
                return True
            except CorrectionError:
                log.debug('Unable to correct a message', exc_info=True)
        return False

    async def _handle_normal_message(self, message: MessageData) -> None:
        """
        Process the non-correction groupchat message.
        """
        ui_msg: Union[InfoMessage, Message]
        # Messages coming from MUC barejid (Server maintenance, IRC mode
        # changes from biboumi, etc.) have no nick/resource and are displayed
        # as info messages.
        highlight = False
        if message.nick:
            highlight = self.message_is_highlight(
                message.body, message.nick, message.is_history
            )
            ui_msg = Message(
                txt=message.body,
                time=message.date,
                nickname=message.nick,
                history=message.is_history,
                delayed=message.delayed,
                identifier=message.message['id'],
                jid=message.message['from'],
                user=message.user,
                highlight=highlight,
            )
        else:
            ui_msg = InfoMessage(
                txt=message.body,
                time=message.date,
                identifier=message.message['id'],
            )
        self.add_message(ui_msg)
        if highlight:
            await self.core.events.trigger_async('highlight', message, self)

    def handle_presence(self, presence: Presence) -> None:
        """Handle MUC presence"""
        self.reset_lag()
        status_codes = presence['muc']['status_codes']
        if presence['type'] == 'error':
            self.core.room_error(presence, self.jid.bare)
        elif not self.joined:
            own = 110 in status_codes
            if own or len(self.presence_buffer) >= 10:
                self.process_presence_buffer(presence, own)
            else:
                self.presence_buffer.append(presence)
                return
        else:
            try:
                self.handle_presence_joined(presence, status_codes)
            except PresenceError:
                self.core.room_error(presence, presence['from'].bare)
        if self.core.tabs.current_tab is self:
            self.text_win.refresh()
            self.user_win.refresh_if_changed(self.users)
            self.info_header.refresh(
                self, self.text_win, user=self.own_user,
                information=MucTab.additional_information)
            self.input.refresh()
            self.core.doupdate()

    def process_presence_buffer(self, last_presence: Presence, own: bool) -> None:
        """
        Batch-process all the initial presences
        """
        for stanza in self.presence_buffer:
            try:
                self.handle_presence_unjoined(stanza)
            except PresenceError:
                self.core.room_error(stanza, stanza['from'].bare)
        self.presence_buffer = []
        self.handle_presence_unjoined(last_presence, own)
        self.users.sort()
        # Enable the self ping event, to regularly check if we
        # are still in the room.
        if own:
            self.enable_self_ping_event()
        if self.core.tabs.current_tab is not self:
            self.refresh_tab_win()
            self.core.tabs.current_tab.refresh_input()
            self.core.doupdate()

    def handle_presence_unjoined(self, presence: Presence, own: bool = False) -> None:
        """
        Presence received while we are not in the room (before code=110)
        """
        # If presence is coming from MUC barejid, ignore.
        if not presence['from'].resource:
            return None
        dissected_presence = dissect_presence(presence)
        from_nick, _, affiliation, show, status, role, jid, typ = dissected_presence
        if typ == 'unavailable':
            return
        user_color = self.search_for_color(from_nick)
        new_user = User(from_nick, affiliation, show, status, role, jid,
                        user_color)
        self.users.append(new_user)
        self.core.events.trigger('muc_join', presence, self)
        if own:
            status_codes = presence['muc']['status_codes']
            self.own_join(from_nick, new_user, status_codes)

    def own_join(self, from_nick: str, new_user: User, status_codes: Set[int]) -> None:
        """
        Handle the last presence we received, entering the room
        """
        self.own_nick = from_nick
        self.own_user = new_user
        self.joined = True
        if self.jid in self.core.initial_joins:
            self.core.initial_joins.remove(self.jid)
            self._state = 'normal'
        elif self != self.core.tabs.current_tab:
            self._state = 'joined'
        if (self.core.tabs.current_tab is self
                and self.core.status.show not in ('xa', 'away')):
            self.send_chat_state('active')
        theme = get_theme()
        new_user.color = theme.COLOR_OWN_NICK

        if config.get_by_tabname('display_user_color_in_join_part',
                                 self.general_jid):
            color = dump_tuple(new_user.color)
        else:
            color = "3"

        info_col = dump_tuple(theme.COLOR_INFORMATION_TEXT)
        warn_col = dump_tuple(theme.COLOR_WARNING_TEXT)
        spec_col = dump_tuple(theme.COLOR_JOIN_CHAR)
        enable_message = ('\x19%(color_spec)s}%(spec)s\x19%(info_col)s} You '
                          '(\x19%(nick_col)s}%(nick)s\x19%(info_col)s}) joined'
                          ' the room') % {
                              'nick': from_nick,
                              'spec': theme.CHAR_JOIN,
                              'color_spec': spec_col,
                              'nick_col': color,
                              'info_col': info_col,
                          }
        self.add_message(MucOwnJoinMessage(enable_message))
        self.core.enable_private_tabs(self.jid.bare, enable_message)
        if 201 in status_codes:
            self.add_message(
                PersistentInfoMessage('Info: The room has been created'),
            )
        if 170 in status_codes:
            self.add_message(
                InfoMessage(
                    '\x19%(warn_col)s}Warning:\x19%(info_col)s}'
                    ' This room is publicly logged' % {
                        'info_col': info_col,
                        'warn_col': warn_col
                    }
                ),
            )
        if 100 in status_codes:
            self.add_message(
                InfoMessage(
                    '\x19%(warn_col)s}Warning:\x19%(info_col)s}'
                    ' This room is not anonymous.' % {
                        'info_col': info_col,
                        'warn_col': warn_col
                    },
                ),
            )
        asyncio.create_task(LogLoader(
            logger, self, config.get_by_tabname('use_log', self.general_jid)
        ).tab_open())

    def handle_presence_joined(self, presence: Presence, status_codes: Set[int]) -> None:
        """
        Handle new presences when we are already in the room
        """
        # If presence is coming from MUC barejid, ignore.
        if not presence['from'].resource:
            return None
        dissected_presence = dissect_presence(presence)
        from_nick, from_room, affiliation, show, status, role, jid, typ = dissected_presence
        change_nick = 303 in status_codes
        kick = 307 in status_codes and typ == 'unavailable'
        ban = 301 in status_codes and typ == 'unavailable'
        shutdown = 332 in status_codes and typ == 'unavailable'
        server_initiated = 333 in status_codes and typ == 'unavailable'
        non_member = 322 in status_codes and typ == 'unavailable'
        user = self.get_user_by_name(from_nick)
        # New user
        if not user and typ != "unavailable":
            user_color = self.search_for_color(from_nick)
            self.core.events.trigger('muc_join', presence, self)
            self.on_user_join(from_nick, affiliation, show, status, role, jid,
                              user_color)
        elif user is None:
            log.error('BUG: User %s in %s is None', from_nick, self.jid)
            return
        elif change_nick:
            self.core.events.trigger('muc_nickchange', presence, self)
            self.on_user_nick_change(presence, user, from_nick)
        elif ban:
            self.core.events.trigger('muc_ban', presence, self)
            self.core.on_user_left_private_conversation(
                from_room, user, status)
            self.on_user_banned(presence, user, from_nick)
        elif kick and not server_initiated:
            self.core.events.trigger('muc_kick', presence, self)
            self.core.on_user_left_private_conversation(
                from_room, user, status)
            self.on_user_kicked(presence, user, from_nick)
        elif shutdown:
            self.core.events.trigger('muc_shutdown', presence, self)
            self.on_muc_shutdown()
        elif non_member:
            self.core.events.trigger('muc_shutdown', presence, self)
            self.on_non_member_kicked()
        # user quit
        elif typ == 'unavailable':
            self.on_user_leave_groupchat(user, jid, status, from_nick,
                                         JID(from_room), server_initiated)
            ns = 'http://jabber.org/protocol/muc#user'
            if presence.xml.find(f'{{{ns}}}x/{{{ns}}}destroy') is not None:
                info = f'Room {self.jid} was destroyed.'
                if presence['muc']['destroy']:
                    reason = presence['muc']['destroy']['reason']
                    altroom = presence['muc']['destroy']['jid']
                    if reason:
                        info += f' “{reason}”.'
                    if altroom:
                        info += f' The new address now is {altroom}.'
                self.core.information(info, 'Info')
        # status change
        else:
            self.on_user_change_status(user, from_nick, from_room, affiliation,
                                       role, show, status)

    def on_non_member_kicked(self) -> None:
        """We have been kicked because the MUC is members-only"""
        self.add_message(
            MucOwnLeaveMessage(
                'You have been kicked because you '
                'are not a member and the room is now members-only.'
            )
        )
        self.disconnect()

    def on_muc_shutdown(self) -> None:
        """We have been kicked because the MUC service is shutting down"""
        self.add_message(
            MucOwnLeaveMessage(
                'You have been kicked because the'
                ' MUC service is shutting down.'
            )
        )
        self.disconnect()

    def on_user_join(self, from_nick: str, affiliation: str, show: str, status: str, role: str, jid: JID,
                     color: str) -> None:
        """
        When a new user joins the groupchat
        """
        user = User(from_nick, affiliation, show, status, role, jid,
                    color)
        bisect.insort_left(self.users, user)
        hide_exit_join = config.get_by_tabname('hide_exit_join',
                                               self.general_jid)
        if hide_exit_join != 0:
            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(user.color)
            else:
                color = "3"
            theme = get_theme()
            info_col = dump_tuple(theme.COLOR_INFORMATION_TEXT)
            spec_col = dump_tuple(theme.COLOR_JOIN_CHAR)
            char_join = theme.CHAR_JOIN
            if not jid.full:
                msg = ('\x19%(color_spec)s}%(spec)s \x19%(color)s}%(nick)s'
                       '\x19%(info_col)s} joined the room') % {
                           'nick': from_nick,
                           'spec': char_join,
                           'color': color,
                           'info_col': info_col,
                           'color_spec': spec_col,
                       }
            else:
                msg = ('\x19%(color_spec)s}%(spec)s \x19%(color)s}%(nick)s'
                       '\x19%(info_col)s} (\x19%(jid_color)s}%(jid)s\x19'
                       '%(info_col)s}) joined the room') % {
                           'spec': char_join,
                           'nick': from_nick,
                           'color': color,
                           'jid': jid.full,
                           'info_col': info_col,
                           'jid_color': dump_tuple(theme.COLOR_MUC_JID),
                           'color_spec': spec_col,
                       }
            self.add_message(PersistentInfoMessage(msg))
        self.core.on_user_rejoined_private_conversation(self.jid.bare, from_nick)

    def on_user_nick_change(self, presence: Presence, user: User, from_nick: str) -> None:
        new_nick = presence['muc']['item']['nick']
        if not new_nick:
            return  # should not happen
        old_color_tuple = user.color
        if user.nick == self.own_nick:
            self.own_nick = new_nick
            # also change our nick in all private discussions of this room
            self.core.handler.on_muc_own_nickchange(self)
            user.change_nick(new_nick)
        else:
            user.change_nick(new_nick)
            color = config.getstr(new_nick, section='muc_colors') or None
            user.change_color(color)
        self.users.remove(user)
        bisect.insort_left(self.users, user)

        if config.get_by_tabname('display_user_color_in_join_part',
                                 self.general_jid):
            color = dump_tuple(user.color)
            old_color = dump_tuple(old_color_tuple)
        else:
            old_color = color = "3"
        info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        self.add_message(
            PersistentInfoMessage(
                '\x19%(old_color)s}%(old)s\x19%(info_col)s} is'
                ' now known as \x19%(color)s}%(new)s' % {
                    'old': from_nick,
                    'new': new_nick,
                    'color': color,
                    'old_color': old_color,
                    'info_col': info_col
                },
            )
        )
        # rename the private tabs if needed
        self.core.rename_private_tabs(self.jid.bare, from_nick, user)

    def on_user_banned(self, presence: Presence, user: User, from_nick: str) -> None:
        """
        When someone is banned from a muc
        """
        cls: Type[InfoMessage] = PersistentInfoMessage
        self.users.remove(user)
        by = presence['muc']['item'].get_plugin('actor', check=True)
        reason = presence['muc']['item']['reason']
        by_repr: Union[JID, str, None] = None
        if by is not None:
            by_repr = by['jid'] or by['nick'] or None

        theme = get_theme()
        info_col = dump_tuple(theme.COLOR_INFORMATION_TEXT)
        char_kick = theme.CHAR_KICK

        if from_nick == self.own_nick:  # we are banned
            cls = MucOwnLeaveMessage
            if by:
                kick_msg = ('\x191}%(spec)s \x193}You\x19%(info_col)s}'
                            ' have been banned by \x194}%(by)s') % {
                                'spec': char_kick,
                                'by': by_repr,
                                'info_col': info_col
                            }
            else:
                kick_msg = ('\x191}%(spec)s \x193}You\x19'
                            '%(info_col)s} have been banned.') % {
                                'spec': char_kick,
                                'info_col': info_col
                            }
            self.core.disable_private_tabs(self.jid.bare, reason=kick_msg)
            self.disconnect()
            self.refresh_tab_win()
            self.core.tabs.current_tab.refresh_input()
            if config.get_by_tabname('autorejoin', self.general_jid):
                delay = config.get_by_tabname('autorejoin_delay',
                                              self.general_jid)
                delay = common.parse_str_to_secs(delay)
                if delay <= 0:
                    muc.join_groupchat(self.core, self.jid, self.own_nick)
                else:
                    self.core.add_timed_event(
                        timed_events.DelayedEvent(delay, muc.join_groupchat,
                                                  self.core, self.jid,
                                                  self.own_nick))

        else:
            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(user.color)
            else:
                color = "3"

            if by_repr:
                kick_msg = ('\x191}%(spec)s \x19%(color)s}'
                            '%(nick)s\x19%(info_col)s} '
                            'has been banned by \x194}%(by)s') % {
                                'spec': char_kick,
                                'nick': from_nick,
                                'color': color,
                                'by': by_repr,
                                'info_col': info_col
                            }
            else:
                kick_msg = ('\x191}%(spec)s \x19%(color)s}%(nick)s'
                            '\x19%(info_col)s} has been banned') % {
                                'spec': char_kick,
                                'nick': from_nick,
                                'color': color,
                                'info_col': info_col
                            }
        if reason:
            kick_msg += ('\x19%(info_col)s} Reason: \x196}'
                         '%(reason)s\x19%(info_col)s}') % {
                             'reason': reason,
                             'info_col': info_col
                         }
        self.add_message(cls(kick_msg))

    def on_user_kicked(self, presence: Presence, user: User, from_nick: str) -> None:
        """
        When someone is kicked from a muc
        """
        cls: Type[InfoMessage] = PersistentInfoMessage
        self.users.remove(user)
        actor_elem = presence['muc']['item'].get_plugin('actor', check=True)
        reason = presence['muc']['item']['reason']
        by = None
        theme = get_theme()
        info_col = dump_tuple(theme.COLOR_INFORMATION_TEXT)
        char_kick = theme.CHAR_KICK
        if actor_elem is not None:
            by = actor_elem['nick'] or actor_elem.get['jid'] or None
        if from_nick == self.own_nick:  # we are kicked
            cls = MucOwnLeaveMessage
            if by:
                kick_msg = ('\x191}%(spec)s \x193}You\x19'
                            '%(info_col)s} have been kicked'
                            ' by \x193}%(by)s') % {
                                'spec': char_kick,
                                'by': by,
                                'info_col': info_col
                            }
            else:
                kick_msg = ('\x191}%(spec)s \x193}You\x19%(info_col)s}'
                            ' have been kicked.') % {
                                'spec': char_kick,
                                'info_col': info_col
                            }
            self.core.disable_private_tabs(self.jid.bare, reason=kick_msg)
            self.disconnect()
            self.refresh_tab_win()
            self.core.tabs.current_tab.refresh_input()
            # try to auto-rejoin
            if config.get_by_tabname('autorejoin', self.general_jid):
                delay = config.get_by_tabname('autorejoin_delay',
                                              self.general_jid)
                delay = common.parse_str_to_secs(delay)
                if delay <= 0:
                    muc.join_groupchat(self.core, self.jid, self.own_nick)
                else:
                    self.core.add_timed_event(
                        timed_events.DelayedEvent(delay, muc.join_groupchat,
                                                  self.core, self.jid,
                                                  self.own_nick))
        else:
            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(user.color)
            else:
                color = "3"
            if by:
                kick_msg = ('\x191}%(spec)s \x19%(color)s}%(nick)s'
                            '\x19%(info_col)s} has been kicked by '
                            '\x193}%(by)s') % {
                                'spec': char_kick,
                                'nick': from_nick,
                                'color': color,
                                'by': by,
                                'info_col': info_col
                            }
            else:
                kick_msg = ('\x191}%(spec)s \x19%(color)s}%(nick)s'
                            '\x19%(info_col)s} has been kicked') % {
                                'spec': char_kick,
                                'nick': from_nick,
                                'color': color,
                                'info_col': info_col
                            }
        if reason:
            kick_msg += ('\x19%(info_col)s} Reason: \x196}'
                         '%(reason)s') % {
                             'reason': reason,
                             'info_col': info_col
                         }
        self.add_message(cls(kick_msg))

    def on_user_leave_groupchat(self,
                                user: User,
                                jid: JID,
                                status: str,
                                from_nick: str,
                                from_room: JID,
                                server_initiated: bool = False) -> None:
        """
        When a user leaves a groupchat
        """
        self.users.remove(user)
        if self.own_nick == user.nick:
            # We are now out of the room.
            # Happens with some buggy (? not sure) servers
            self.disconnect()
            self.core.disable_private_tabs(from_room.bare)
            self.refresh_tab_win()

        hide_exit_join = config.get_by_tabname('hide_exit_join',
                                               self.general_jid)

        if hide_exit_join <= -1 or user.has_talked_since(hide_exit_join):
            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(user.color)
            else:
                color = "3"
            theme = get_theme()
            info_col = dump_tuple(theme.COLOR_INFORMATION_TEXT)
            spec_col = dump_tuple(theme.COLOR_QUIT_CHAR)

            error_leave_txt = ''
            if server_initiated:
                error_leave_txt = ' due to an error'

            if not jid.full:
                leave_msg = ('\x19%(color_spec)s}%(spec)s \x19%(color)s}'
                             '%(nick)s\x19%(info_col)s} has left the '
                             'room%(error_leave)s') % {
                                 'nick': from_nick,
                                 'color': color,
                                 'spec': theme.CHAR_QUIT,
                                 'info_col': info_col,
                                 'color_spec': spec_col,
                                 'error_leave': error_leave_txt,
                             }
            else:
                jid_col = dump_tuple(theme.COLOR_MUC_JID)
                leave_msg = ('\x19%(color_spec)s}%(spec)s \x19%(color)s}'
                             '%(nick)s\x19%(info_col)s} (\x19%(jid_col)s}'
                             '%(jid)s\x19%(info_col)s}) has left the '
                             'room%(error_leave)s') % {
                                 'spec': theme.CHAR_QUIT,
                                 'nick': from_nick,
                                 'color': color,
                                 'jid': jid.full,
                                 'info_col': info_col,
                                 'color_spec': spec_col,
                                 'jid_col': jid_col,
                                 'error_leave': error_leave_txt,
                             }
            if status:
                leave_msg += ' (\x19o%s\x19%s})' % (status, info_col)
            self.add_message(PersistentInfoMessage(leave_msg))
        self.core.on_user_left_private_conversation(from_room.bare, user, status)

    def on_user_change_status(self, user: User, from_nick: str, from_room: str, affiliation: str,
                              role: str, show: str, status: str) -> None:
        """
        When a user changes her status
        """
        # build the message
        display_message = False  # flag to know if something significant enough
        # to be displayed has changed
        if config.get_by_tabname('display_user_color_in_join_part',
                                 self.general_jid):
            color = dump_tuple(user.color)
        else:
            color = "3"
        info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        if from_nick == self.own_nick:
            msg = '\x19%(color)s}You\x19%(info_col)s} changed: ' % {
                'info_col': info_col,
                'color': color
            }
        else:
            msg = '\x19%(color)s}%(nick)s\x19%(info_col)s} changed: ' % {
                'nick': from_nick,
                'color': color,
                'info_col': info_col
            }
        if affiliation != user.affiliation:
            msg += 'affiliation: %s, ' % affiliation
            display_message = True
        if role != user.role:
            msg += 'role: %s, ' % role
            display_message = True
        if show != user.show and show in SHOW_NAME:
            msg += 'show: %s, ' % SHOW_NAME[show]
            display_message = True
        if status != user.status:
            # if the user sets his status to nothing
            if status:
                msg += 'status: %s, ' % status
                display_message = True
            elif show in SHOW_NAME and show == user.show:
                msg += 'show: %s, ' % SHOW_NAME[show]
                display_message = True
        if not display_message:
            return
        msg = msg[:-2]  # remove the last ", "
        hide_status_change = config.get_by_tabname('hide_status_change',
                                                   self.general_jid)
        if hide_status_change < -1:
            hide_status_change = -1
        if ((hide_status_change == -1
             or user.has_talked_since(hide_status_change)
             or user.nick == self.own_nick) and
            (affiliation != user.affiliation or role != user.role
             or show != user.show or status != user.status)) or (
                 affiliation != user.affiliation or role != user.role):
            # display the message in the room
            self.add_message(InfoMessage(msg))
        self.core.on_user_changed_status_in_private(
            JID('%s/%s' % (from_room, from_nick)), Status(show, status)
        )
        self.users.remove(user)
        # finally, effectively change the user status
        user.update(affiliation, show, status, role)
        bisect.insort_left(self.users, user)

    def disconnect(self) -> None:
        """
        Set the state of the room as not joined, so
        we can know if we can join it, send messages to it, etc
        """
        self.presence_buffer = []
        self.users = []
        if self is not self.core.tabs.current_tab:
            self.state = 'disconnected'
        self.joined = False
        self.disable_self_ping_event()

    def get_single_line_topic(self) -> str:
        """
        Return the topic as a single-line string (for the window header)
        """
        return self.topic.replace('\n', '|')

    def get_user_by_name(self, nick: str) -> Optional[User]:
        """
        Gets the user associated with the given nick, or None if not found
        """
        for user in self.users:
            if user.nick == nick:
                return user
        return None

    def add_message(self, msg: BaseMessage) -> None:
        """Add a message to the text buffer and set various tab status"""
        # reset self-ping interval
        if self.self_ping_event:
            self.enable_self_ping_event()
        super().add_message(msg)
        if not isinstance(msg, Message):
            return
        if msg.user:
            msg.user.set_last_talked(msg.time)
        if config.get_by_tabname('notify_messages', self.jid) and self.state != 'current':
            if msg.nickname != self.own_nick and not msg.history:
                self.state = 'message'
        if msg.txt and msg.nickname:
            self.do_highlight(msg.txt, msg.nickname, msg.history)

    def modify_message(self,
                       txt: str,
                       old_id: str,
                       new_id: str,
                       time: Optional[datetime] = None,
                       delayed: bool = False,
                       nickname: Optional[str] = None,
                       user: Optional[User] = None,
                       jid: Optional[JID] = None) -> bool:
        highlight = self.message_is_highlight(
            txt, nickname, delayed, corrected=True
        )
        message = self._text_buffer.modify_message(
            txt,
            old_id,
            new_id,
            highlight=highlight,
            time=time,
            user=user,
            jid=jid)
        if message:
            self.log_message(message)
            self.text_win.modify_message(message.identifier, message)
            return highlight
        return False

    def matching_names(self) -> List[Tuple[int, str]]:
        return [(1, self.jid.node), (3, self.jid.full)]

    def enable_self_ping_event(self) -> None:
        delay = config.get_by_tabname(
            "self_ping_delay", self.general_jid, default=0)
        interval = int(
            config.get_by_tabname(
                "self_ping_interval", self.general_jid, default=delay))
        if interval <= 0:  # use 0 or some negative value to disable it
            return
        self.disable_self_ping_event()
        self.self_ping_event = timed_events.DelayedEvent(
            interval, self.send_self_ping)
        self.core.add_timed_event(self.self_ping_event)

    def disable_self_ping_event(self) -> None:
        if self.self_ping_event is not None:
            self.core.remove_timed_event(self.self_ping_event)
            self.self_ping_event = None

    def send_self_ping(self) -> None:
        if self.core.xmpp.is_connected():
            timeout = config.get_by_tabname(
                "self_ping_timeout", self.general_jid, default=60)
            to = self.jid.bare + "/" + self.own_nick
            self.core.xmpp.plugin['xep_0199'].send_ping(
                jid=JID(to),
                callback=self.on_self_ping_result,
                timeout_callback=self.on_self_ping_failed,
                timeout=timeout)
        else:
            self.enable_self_ping_event()

    def on_self_ping_result(self, iq: Iq) -> None:
        if iq["type"] == "error" and iq["error"]["condition"] not in \
                ("feature-not-implemented", "service-unavailable", "item-not-found"):
            self.command_cycle(iq["error"]["text"] or "not in this room")
            self.core.refresh_window()
        else:  # Re-send a self-ping in a few seconds
            self.reset_lag()
            self.enable_self_ping_event()

    def search_for_color(self, nick: str) -> str:
        """
        Search for the color of a nick in the config file.
        Also, look at the colors of its possible aliases if nick_color_aliases
        is set.
        """
        color = config.getstr(nick, section='muc_colors')
        if color != '':
            return color
        nick_color_aliases = config.get_by_tabname('nick_color_aliases',
                                                   self.jid)
        if nick_color_aliases:
            nick_alias = re.sub('^_*(.*?)_*$', '\\1', nick)
            color = config.getstr(nick_alias, section='muc_colors')
        return color

    def on_self_ping_failed(self, iq: Any = None) -> None:
        if not self.lagged:
            self.lagged = True
            self._text_buffer.add_message(
                InfoMessage(
                    "MUC service not responding."
                ),
            )
            self._state = 'disconnected'
            self.core.refresh_window()
        self.enable_self_ping_event()

    def reset_lag(self) -> None:
        if self.lagged:
            self.lagged = False
            self.add_message(
                InfoMessage("MUC service is responding again.")
            )
            if self != self.core.tabs.current_tab:
                self._state = 'joined'
            else:
                self._state = 'normal'
            self.core.refresh_window()

########################## UI ONLY #####################################

    @refresh_wrapper.always
    def go_to_next_hl(self) -> None:
        """
        Go to the next HL in the room, or the last
        """
        self.text_win.next_highlight()

    @refresh_wrapper.always
    def go_to_prev_hl(self) -> None:
        """
        Go to the previous HL in the room, or the first
        """
        self.text_win.previous_highlight()

    @refresh_wrapper.always
    def scroll_user_list_up(self) -> None:
        "Scroll up in the userlist"
        self.user_win.scroll_up()

    @refresh_wrapper.always
    def scroll_user_list_down(self) -> None:
        "Scroll down in the userlist"
        self.user_win.scroll_down()

    def resize(self) -> None:
        """
        Resize the whole window. i.e. all its sub-windows
        """
        self.need_resize = False
        if config.getbool('hide_user_list') or self.size.tab_degrade_x:
            text_width = self.width
        else:
            text_width = (self.width // 10) * 9

        if self.size.tab_degrade_y:
            tab_win_height = 0
            info_win_height = 0
        else:
            tab_win_height = Tab.tab_win_height()
            info_win_height = self.core.information_win_size

        self.user_win.resize(
            self.height - 3 - info_win_height - tab_win_height,
            self.width - (self.width // 10) * 9 - 1, 1,
            (self.width // 10) * 9 + 1)
        self.v_separator.resize(
            self.height - 3 - info_win_height - tab_win_height, 1, 1,
            9 * (self.width // 10))

        self.topic_win.resize(1, self.width, 0, 0)

        self.text_win.resize(
            self.height - 3 - info_win_height - tab_win_height, text_width, 1,
            0, self._text_buffer, force=self.ui_config_changed)
        self.ui_config_changed = False
        self.info_header.resize(
            1, self.width, self.height - 2 - info_win_height - tab_win_height,
            0)
        self.input.resize(1, self.width, self.height - 1, 0)

    def refresh(self) -> None:
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        if config.getbool('hide_user_list') or self.size.tab_degrade_x:
            display_user_list = False
        else:
            display_user_list = True
        display_info_win = not self.size.tab_degrade_y

        self.topic_win.refresh(self.get_single_line_topic())
        self.text_win.refresh()
        if display_user_list:
            self.v_separator.refresh()
            self.user_win.refresh(self.users)
        self.info_header.refresh(
            self, self.text_win, user=self.own_user,
            information=MucTab.additional_information)
        self.refresh_tab_win()
        if display_info_win:
            self.info_win.refresh()
        self.input.refresh()

    def on_info_win_size_changed(self) -> None:
        if self.core.information_win_size >= self.height - 3:
            return
        if config.getbool("hide_user_list"):
            text_width = self.width
        else:
            text_width = (self.width // 10) * 9
        self.user_win.resize(
            self.height - 3 - self.core.information_win_size -
            Tab.tab_win_height(), self.width - (self.width // 10) * 9 - 1, 1,
            (self.width // 10) * 9 + 1)
        self.v_separator.resize(
            self.height - 3 - self.core.information_win_size -
            Tab.tab_win_height(), 1, 1, 9 * (self.width // 10))
        self.text_win.resize(
            self.height - 3 - self.core.information_win_size -
            Tab.tab_win_height(), text_width, 1, 0, self._text_buffer)
        self.info_header.resize(
            1, self.width, self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), 0)

    # This maxsize is kinda arbitrary, but most users won’t have that many
    # nicknames anyway.
    @functools.lru_cache(maxsize=8)
    def build_highlight_regex(self, nickname: str) -> Pattern:
        return re.compile(r"(^|\W)" + re.escape(nickname) + r"(\W|$)", re.I)

    def message_is_highlight(self, txt: str, nickname: Optional[str], history: bool,
                             corrected: bool = False) -> bool:
        """Highlight algorithm for MUC tabs"""
        # Don't highlight on info message or our own messages
        if not nickname or nickname == self.own_nick:
            return False
        highlight_on = config.get_by_tabname(
            'highlight_on',
            self.general_jid,
        ).split(':')
        highlighted = False
        if not history:
            if self.build_highlight_regex(self.own_nick).search(txt):
                highlighted = True
            else:
                for word in highlight_on:
                    if word and word.lower() in txt.lower():
                        highlighted = True
                        break
        return highlighted

    def do_highlight(self, txt: str, nickname: str, history: bool,
                     corrected: bool = False) -> bool:
        """Set the tab color and returns the highlight state"""
        highlighted = self.message_is_highlight(
            txt, nickname, history, corrected
        )
        if highlighted and self.joined and not corrected:
            if self.state != 'current':
                self.state = 'highlight'
            beep_on = config.getstr('beep_on').split()
            if 'highlight' in beep_on and 'message' not in beep_on:
                if not config.get_by_tabname('disable_beep', self.jid):
                    curses.beep()
            return True
        return False

########################## COMMANDS ####################################

    @command_args_parser.quoted(1, 1, [''])
    async def command_invite(self, args: List[str]) -> None:
        """/invite <jid> [reason]"""
        if args is None:
            self.core.command.help('invite')
            return
        jid, reason = args
        await self.core.command.invite('%s %s "%s"' % (jid, self.jid, reason))

    @command_args_parser.quoted(1)
    def command_info(self, args: List[str]) -> None:
        """
        /info <nick>
        """
        if args is None:
            self.core.command.help('info')
            return
        nick = args[0]
        if not self.print_info(nick):
            self.core.information("Unknown user: %s" % nick, "Error")

    @command_args_parser.quoted(0)
    async def command_configure(self, ignored: Any) -> None:
        """
        /configure
        """

        try:
            form = await self.core.xmpp.plugin['xep_0045'].get_room_config(
                self.jid
            )
            self.core.open_new_form(form, self.cancel_config, self.send_config)
        except (IqError, IqTimeout, ValueError):
            self.core.information(
                'Could not retrieve the configuration form', 'Error')

    @command_args_parser.raw
    def command_cycle(self, msg: str) -> None:
        """/cycle [reason]"""
        self.leave_room(msg)
        self.join()

    @command_args_parser.ignored
    def command_recolor(self) -> None:
        """
        /recolor [random]
        Re-assigns color to the participants of the room
        """
        self.recolor()

    @command_args_parser.quoted(2, 2, [''])
    def command_color(self, args: List[str]) -> None:
        """
        /color <nick> <color>
        Fix a color for a nick.
        Use "unset" instead of a color to remove the attribution.
        User "random" to attribute a random color.
        """
        if args is None:
            self.core.command.help('color')
            return
        nick = args[0]
        color = args[1].lower()
        if nick == self.own_nick:
            self.core.information(
                "You cannot change the color of your"
                " own nick.", 'Error'
            )
        elif color not in xhtml.colors and color not in ('unset', 'random'):
            self.core.information("Unknown color: %s" % color, 'Error')
        else:
            self.set_nick_color(nick, color)

    @command_args_parser.quoted(1)
    async def command_version(self, args: List[str]) -> None:
        """
        /version <jid or nick>
        """
        if args is None:
            self.core.command.help('version')
            return
        nick = args[0]
        try:
            if nick in {user.nick for user in self.users}:
                jid = copy(self.jid)
                jid.resource = nick
            else:
                jid = JID(nick)
        except InvalidJID:
            self.core.information('Invalid jid or nick %r' % nick, 'Error')
            return
        iq = await self.core.xmpp.plugin['xep_0092'].get_version(jid)
        self.core.handler.on_version_result(iq)

    @command_args_parser.quoted(1)
    def command_nick(self, args: List[str]) -> None:
        """
        /nick <nickname>
        """
        if args is None:
            self.core.command.help('nick')
            return
        nick = args[0]
        if not self.joined:
            self.core.information('/nick only works in joined rooms',
                                         'Info')
            return
        current_status = self.core.get_status()
        try:
            target_jid = copy(self.jid)
            target_jid.resource = nick
        except InvalidJID:
            self.core.information('Invalid nick', 'Info')
            return
        muc.change_nick(
            self.core,
            self.jid,
            nick,
            current_status.message,
            current_status.show,
        )

    @command_args_parser.quoted(0, 1, [''])
    def command_part(self, args: List[str]) -> None:
        """
        /part [msg]
        """
        message = args[0]
        self.leave_room(message)
        if self == self.core.tabs.current_tab:
            self.refresh()
        self.core.doupdate()

    @command_args_parser.raw
    def command_leave(self, msg: str) -> None:
        """
        /leave [msg]
        """
        self.command_close(msg)

    @command_args_parser.raw
    def command_close(self, msg: str) -> None:
        """
        /close [msg]
        """
        self.leave_room(msg)
        if config.getbool('synchronise_open_rooms'):
            if self.jid in self.core.bookmarks:
                bookmark = self.core.bookmarks[self.jid]
                if bookmark:
                    bookmark.autojoin = False
                    asyncio.create_task(
                        self.core.bookmarks.save(self.core.xmpp)
                    )
        self.core.close_tab(self)

    def on_close(self) -> None:
        super().on_close()
        if self.joined:
            self.leave_room('')

    @command_args_parser.quoted(1, 1)
    def command_query(self, args: List[str]) -> None:
        """
        /query <nick> [message]
        """
        if args is None:
            self.core.command.help('query')
            return
        nick = args[0]
        r = None
        for user in self.users:
            if user.nick == nick:
                r = self.core.open_private_window(self.jid.bare, user.nick)
        if r and len(args) == 2:
            msg = args[1]
            asyncio.ensure_future(
                r.command_say(
                    xhtml.convert_simple_to_full_colors(msg)
                )
            )
        if not r:
            self.core.information("Cannot find user: %s" % nick, 'Error')

    @command_args_parser.raw
    def command_topic(self, subject: str) -> None:
        """
        /topic [new topic]
        """
        if not subject:
            self.show_topic()
        else:
            self.change_topic(subject)

    @command_args_parser.quoted(0)
    def command_names(self, args: Any) -> None:
        """
        /names
        """
        if not self.joined:
            return

        theme = get_theme()
        aff = {
            'owner': theme.CHAR_AFFILIATION_OWNER,
            'admin': theme.CHAR_AFFILIATION_ADMIN,
            'member': theme.CHAR_AFFILIATION_MEMBER,
            'none': theme.CHAR_AFFILIATION_NONE,
        }

        colors = {}
        colors["visitor"] = dump_tuple(theme.COLOR_USER_VISITOR)
        colors["moderator"] = dump_tuple(theme.COLOR_USER_MODERATOR)
        colors["participant"] = dump_tuple(theme.COLOR_USER_PARTICIPANT)
        color_other = dump_tuple(theme.COLOR_USER_NONE)

        buff = ['Users: %s \n' % len(self.users)]
        for user in self.users:
            affiliation = aff.get(user.affiliation,
                                  theme.CHAR_AFFILIATION_NONE)
            color = colors.get(user.role, color_other)
            buff.append(
                '\x19%s}%s\x19o\x19%s}%s\x19o' %
                (color, affiliation, dump_tuple(user.color), user.nick))

        buff.append('\n')
        message = ' '.join(buff)

        self.add_message(InfoMessage(message))
        self.text_win.refresh()
        self.input.refresh()

    @command_args_parser.quoted(1, 1)
    async def command_kick(self, args: List[str]) -> None:
        """
        /kick <nick> [reason]
        """
        if args is None:
            self.core.command.help('kick')
            return
        if len(args) == 2:
            reason = args[1]
        else:
            reason = ''
        nick = args[0]
        await self.change_role(nick, 'none', reason)

    @command_args_parser.quoted(1, 1)
    async def command_ban(self, args: List[str]) -> None:
        """
        /ban <nick> [reason]
        """
        if args is None:
            self.core.command.help('ban')
            return
        nick = args[0]
        msg = args[1] if len(args) == 2 else ''
        await self.change_affiliation(nick, 'outcast', msg)

    @command_args_parser.quoted(2, 1, [''])
    async def command_role(self, args: List[str]) -> None:
        """
        /role <nick> <role> [reason]
        Changes the role of a user
        roles can be: none, visitor, participant, moderator
        """
        if args is None:
            self.core.command.help('role')
            return

        nick, role, reason = args[0], args[1].lower(), args[2]
        try:
            await self.change_role(nick, role, reason)
        except IqError as iq:
            self.core.room_error(iq, self.jid.bare)

    @command_args_parser.quoted(0, 2)
    async def command_affiliation(self, args: List[str]) -> None:
        """
        /affiliation [<nick or jid> <affiliation>]
        Changes the affiliation of a user
        affiliations can be: outcast, none, member, admin, owner
        """

        room = JID(self.name)
        if not room:
            self.core.information('affiliation: requires a valid chat address', 'Error')
            return

        # List affiliations
        if not args:
            await self.get_users_affiliations(room)
            return None

        if len(args) != 2:
            self.core.command.help('affiliation')
            return

        nick, affiliation = args[0], args[1].lower()
        # Set affiliation
        await self.change_affiliation(nick, affiliation)

    async def get_users_affiliations(self, jid: JID) -> None:
        owners, admins, members, outcasts = await asyncio.gather(
            self.core.xmpp['xep_0045'].get_affiliation_list(jid, 'owner'),
            self.core.xmpp['xep_0045'].get_affiliation_list(jid, 'admin'),
            self.core.xmpp['xep_0045'].get_affiliation_list(jid, 'member'),
            self.core.xmpp['xep_0045'].get_affiliation_list(jid, 'outcast'),
            return_exceptions=True,
        )

        all_errors = functools.reduce(
            lambda acc, iq: acc and isinstance(iq, (IqError, IqTimeout)),
            (owners, admins, members, outcasts),
            True,
        )
        if all_errors:
            self.core.information(
                'Can’t access affiliations for %s' % jid.bare,
                'Error',
            )
            return None

        theme = get_theme()
        aff_colors = {
            'owner': theme.CHAR_AFFILIATION_OWNER,
            'admin': theme.CHAR_AFFILIATION_ADMIN,
            'member': theme.CHAR_AFFILIATION_MEMBER,
            'outcast': theme.CHAR_AFFILIATION_OUTCAST,
        }



        lines = ['Affiliations for %s' % jid.bare]
        affiliation_dict = {
            'owner': owners,
            'admin': admins,
            'member': members,
            'outcast': outcasts,
        }
        for affiliation, items in affiliation_dict.items():
            if isinstance(items, BaseException) or not items:
                continue
            aff_char = aff_colors[affiliation]
            lines.append('  %s%s' % (aff_char, affiliation.capitalize()))
            for ajid in sorted(items):
                lines.append('    %s' % ajid)

        self.core.information('\n'.join(lines), 'Info')
        return None

    @command_args_parser.raw
    async def command_say(self, line: str, attention: bool = False, correct: bool = False):
        """
        /say <message>
        Or normal input + enter
        """
        chatstate = 'inactive' if self.inactive else 'active'
        msg: SMessage = self.core.xmpp.make_message(self.jid)
        msg['type'] = 'groupchat'
        msg['body'] = line
        # trigger the event BEFORE looking for colors.
        # This lets a plugin insert \x19xxx} colors, that will
        # be converted in xhtml.
        self.core.events.trigger('muc_say', msg, self)
        if not msg['body']:
            self.cancel_paused_delay()
            self.text_win.refresh()
            self.input.refresh()
            return
        if msg['body'].find('\x19') != -1:
            msg.enable('html')
            msg['html']['body'] = xhtml.poezio_colors_to_html(msg['body'])
            msg['body'] = xhtml.clean_text(msg['body'])
        if config.get_by_tabname('send_chat_states', self.general_jid):
            if chatstate == 'inactive':
                self.send_chat_state(chatstate, always_send=True)
            else:
                msg['chat_state'] = chatstate
        if correct:
            msg['replace']['id'] = self.last_sent_message['id']  # type: ignore
        self.cancel_paused_delay()
        self.core.events.trigger('muc_say_after', msg, self)
        if not msg['body']:
            self.cancel_paused_delay()
            self.text_win.refresh()
            self.input.refresh()
            return
        # TODO: #3314. Display outgoing MUC message.
        self.set_last_sent_message(msg, correct=correct)
        msg.send()
        self.chat_state = chatstate

    @command_args_parser.raw
    def command_xhtml(self, msg: str) -> None:
        message = self.generate_xhtml_message(msg)
        if message:
            message['type'] = 'groupchat'
            message.send()

    @command_args_parser.quoted(1)
    def command_ignore(self, args: List[str]) -> None:
        """
        /ignore <nick>
        """
        if args is None:
            self.core.command.help('ignore')
            return

        nick = args[0]
        user = self.get_user_by_name(nick)
        if not user:
            self.core.information('%s is not in the room' % nick)
        elif user in self.ignores:
            self.core.information('%s is already ignored' % nick)
        else:
            self.ignores.append(user)
            self.core.information("%s is now ignored" % nick, 'info')

    @command_args_parser.quoted(1)
    def command_unignore(self, args: List[str]) -> None:
        """
        /unignore <nick>
        """
        if args is None:
            self.core.command.help('unignore')
            return

        nick = args[0]
        user = self.get_user_by_name(nick)
        if not user:
            self.core.information('%s is not in the room' % nick)
        elif user not in self.ignores:
            self.core.information('%s is not ignored' % nick)
        else:
            self.ignores.remove(user)
            self.core.information('%s is now unignored' % nick)

    @command_args_parser.quoted(0, 1)
    def command_request_voice(self, args: List[str]) -> None:
        """
        /request_voice [role]
        Request voice in a moderated room
        role can be: participant, moderator
        """

        room = JID(self.name)
        if not room:
            self.core.information('request_voice: requires a valid chat address', 'Error')
            return

        if len(args) > 1:
            self.core.command.help('request_voice')
            return

        if args:
            role = args[0]
        else:
            role = 'participant'

        self.core.xmpp['xep_0045'].request_voice(room, role)

########################## COMPLETIONS #################################

    def completion(self) -> None:
        """
        Called when Tab is pressed, complete the nickname in the input
        """
        if self.complete_commands(self.input):
            return

        # If we are not completing a command or a command argument,
        # complete a nick
        word_list = []
        for user in sorted(self.users, key=COMPARE_USERS_LAST_TALKED, reverse=True):
            if user.nick != self.own_nick:
                word_list.append(user.nick)
        after = config.getstr('after_completion') + ' '
        input_pos = self.input.pos
        text_before = self.input.get_text()[:input_pos]
        if (' ' not in text_before and '\n' not in text_before) or (
                self.input.last_completion and self.input.get_text()
            [:input_pos] == self.input.last_completion + after):
            add_after = after
        else:
            if not config.getbool('add_space_after_completion'):
                add_after = ''
            else:
                add_after = ' '
        self.input.auto_completion(word_list, add_after, quotify=False)
        empty_after = self.input.get_text() == ''
        empty_after = empty_after or (
            self.input.get_text().startswith('/')
            and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)

    def completion_version(self, the_input: windows.MessageInput) -> Completion:
        """Completion for /version"""
        userlist = []
        for user in sorted(self.users, key=COMPARE_USERS_LAST_TALKED, reverse=True):
            if user.nick != self.own_nick:
                userlist.append(user.nick)
        comp = []
        for jid in (jid for jid in roster.jids() if len(roster[jid])):
            for resource in roster[jid].resources:
                comp.append(resource.jid)
        comp.sort()
        userlist.extend(comp)

        return Completion(the_input.auto_completion, userlist, quotify=False)

    def completion_info(self, the_input: windows.MessageInput) -> Completion:
        """Completion for /info"""
        userlist = []
        for user in sorted(self.users, key=COMPARE_USERS_LAST_TALKED, reverse=True):
            userlist.append(user.nick)
        return Completion(the_input.auto_completion, userlist, quotify=False)

    def completion_nick(self, the_input: windows.MessageInput) -> Completion:
        """Completion for /nick"""
        nicks_list = [
            os.environ.get('USER'),
            config.getstr('default_nick'),
            self.core.get_bookmark_nickname(self.jid.bare)
        ]
        nicks = [i for i in nicks_list if i]
        return Completion(the_input.auto_completion, nicks, '', quotify=False)

    def completion_recolor(self, the_input: windows.MessageInput) -> Optional[Completion]:
        if the_input.get_argument_position() == 1:
            return Completion(
                the_input.new_completion, ['random'], 1, '', quotify=False)
        return None

    def completion_color(self, the_input: windows.MessageInput) -> Optional[Completion]:
        """Completion for /color"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            userlist = [user.nick for user in self.users]
            if self.own_nick in userlist:
                userlist.remove(self.own_nick)
            return Completion(
                the_input.new_completion, userlist, 1, '', quotify=True)
        elif n == 2:
            colors = [i for i in xhtml.colors if i]
            colors.sort()
            colors.append('unset')
            colors.append('random')
            return Completion(
                the_input.new_completion, colors, 2, '', quotify=False)
        return None

    def completion_ignore(self, the_input: windows.MessageInput) -> Completion:
        """Completion for /ignore"""
        userlist = [user.nick for user in self.users]
        if self.own_nick in userlist:
            userlist.remove(self.own_nick)
        userlist.sort()
        return Completion(the_input.auto_completion, userlist, quotify=False)

    def completion_role(self, the_input: windows.MessageInput) -> Optional[Completion]:
        """Completion for /role"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            userlist = [user.nick for user in self.users]
            if self.own_nick in userlist:
                userlist.remove(self.own_nick)
            return Completion(
                the_input.new_completion, userlist, 1, '', quotify=True)
        elif n == 2:
            possible_roles = ['none', 'visitor', 'participant', 'moderator']
            return Completion(
                the_input.new_completion, possible_roles, 2, '', quotify=True)
        return None

    def completion_affiliation(self, the_input: windows.MessageInput) -> Optional[Completion]:
        """Completion for /affiliation"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            userlist = [user.nick for user in self.users]
            if self.own_nick in userlist:
                userlist.remove(self.own_nick)
            jidlist = [user.jid.bare for user in self.users]
            if self.core.xmpp.boundjid.bare in jidlist:
                jidlist.remove(self.core.xmpp.boundjid.bare)
            userlist.extend(jidlist)
            return Completion(
                the_input.new_completion, userlist, 1, '', quotify=True)
        elif n == 2:
            possible_affiliations = [
                'none', 'member', 'admin', 'owner', 'outcast'
            ]
            return Completion(
                the_input.new_completion,
                possible_affiliations,
                2,
                '',
                quotify=True)
        return None

    def completion_invite(self, the_input: windows.MessageInput) -> Optional[Completion]:
        """Completion for /invite"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            return Completion(
                the_input.new_completion,
                [str(i) for i in roster.jids()],
                argument_position=1,
                quotify=True)
        return None

    def completion_topic(self, the_input: windows.MessageInput) -> Optional[Completion]:
        if the_input.get_argument_position() == 1:
            return Completion(
                the_input.auto_completion, [self.topic], '', quotify=False)
        return None

    def completion_quoted(self, the_input: windows.MessageInput) -> Optional[Completion]:
        """Nick completion, but with quotes"""
        if the_input.get_argument_position(quoted=True) == 1:
            word_list = []
            for user in sorted(self.users, key=COMPARE_USERS_LAST_TALKED, reverse=True):
                if user.nick != self.own_nick:
                    word_list.append(user.nick)

            return Completion(
                the_input.new_completion, word_list, 1, quotify=True)
        return None

    def completion_unignore(self, the_input: windows.MessageInput) -> Optional[Completion]:
        if the_input.get_argument_position() == 1:
            users = [user.nick for user in self.ignores]
            return Completion(the_input.auto_completion, users, quotify=False)
        return None

    def completion_request_voice(self, the_input: windows.MessageInput) -> Optional[Completion]:
        """Completion for /request_voice"""
        allowed = ['participant', 'moderator']
        return Completion(the_input.auto_completion, allowed, quotify=False)


########################## REGISTER STUFF ##############################

    def register_keys(self) -> None:
        "Register tab-specific keys"
        self.key_func['^I'] = self.completion
        self.key_func['M-u'] = self.scroll_user_list_down
        self.key_func['M-y'] = self.scroll_user_list_up
        self.key_func['M-n'] = self.go_to_next_hl
        self.key_func['M-p'] = self.go_to_prev_hl

    def register_commands(self) -> None:
        "Register tab-specific commands"
        self.register_commands_batch([{
            'name': 'ignore',
            'func': self.command_ignore,
            'usage': '<nickname>',
            'desc': 'Ignore a specified nickname.',
            'shortdesc': 'Ignore someone',
            'completion': self.completion_unignore
        }, {
            'name':
            'unignore',
            'func':
            self.command_unignore,
            'usage':
            '<nickname>',
            'desc':
            'Remove the specified nickname from the ignore list.',
            'shortdesc':
            'Unignore someone.',
            'completion':
            self.completion_unignore
        }, {
            'name':
            'kick',
            'func':
            self.command_kick,
            'usage':
            '<nick> [reason]',
            'desc': ('Kick the user with the specified nickname.'
                     ' You also can give an optional reason.'),
            'shortdesc':
            'Kick someone.',
            'completion':
            self.completion_quoted
        }, {
            'name':
            'ban',
            'func':
            self.command_ban,
            'usage':
            '<nick> [reason]',
            'desc': ('Ban the user with the specified nickname.'
                     ' You also can give an optional reason.'),
            'shortdesc':
            'Ban someone',
            'completion':
            self.completion_quoted
        }, {
            'name':
            'role',
            'func':
            self.command_role,
            'usage':
            '<nick> <role> [reason]',
            'desc': ('Set the role of a user. Roles can be:'
                     ' none, visitor, participant, moderator.'
                     ' You also can give an optional reason.'),
            'shortdesc':
            'Set the role of a user.',
            'completion':
            self.completion_role
        }, {
            'name':
            'affiliation',
            'func':
            self.command_affiliation,
            'usage':
            '[<nick or jid> [<affiliation>]]',
            'desc': ('Set the affiliation of a user. Affiliations can be:'
                     ' outcast, none, member, admin, owner.'),
            'shortdesc':
            'Set the affiliation of a user.',
            'completion':
            self.completion_affiliation
        }, {
            'name':
            'topic',
            'func':
            self.command_topic,
            'usage':
            '<subject>',
            'desc':
            'Change the subject of the room.',
            'shortdesc':
            'Change the subject.',
            'completion':
            self.completion_topic
        }, {
            'name':
            'subject',
            'func':
            self.command_topic,
            'usage':
            '<subject>',
            'desc':
            'Change the subject of the room.',
            'shortdesc':
            'Change the subject.',
            'completion':
            self.completion_topic
        }, {
            'name':
            'query',
            'func':
            self.command_query,
            'usage':
            '<nick> [message]',
            'desc': ('Open a private conversation with <nick>. This nick'
                     ' has to be present in the room you\'re currently in.'
                     ' If you specified a message after the nickname, it '
                     'will immediately be sent to this user.'),
            'shortdesc':
            'Query a user.',
            'completion':
            self.completion_quoted
        }, {
            'name':
            'part',
            'func':
            self.command_part,
            'usage':
            '[message]',
            'desc': ('Disconnect from a room. You can'
                     ' specify an optional message.'),
            'shortdesc':
            'Leave the room.'
        }, {
            'name': 'leave',
            'func': self.command_leave,
            'usage': '[message]',
            'desc': 'Deprecated alias for /close',
            'shortdesc': 'Leave the room.'
        }, {
            'name':
            'close',
            'func':
            self.command_close,
            'usage':
            '[message]',
            'desc': ('Disconnect from a room and close the tab. '
                     'You can specify an optional message if '
                     'you are still connected. If synchronise_open_tabs '
                     'is true, also disconnect you from your other '
                     'clients.'),
            'shortdesc':
            'Close the tab.'
        }, {
            'name':
            'nick',
            'func':
            self.command_nick,
            'usage':
            '<nickname>',
            'desc':
            'Change your nickname in the current room.',
            'shortdesc':
            'Change your nickname.',
            'completion':
            self.completion_nick
        }, {
            'name':
            'recolor',
            'func':
            self.command_recolor,
            'usage':
            '',
            'desc': (
                'Re-assign a color to all participants of the room '
                'if the theme has changed.'
            ),
            'shortdesc':
            'Change the nicks colors.',
            'completion':
            self.completion_recolor
        }, {
            'name':
            'color',
            'func':
            self.command_color,
            'usage':
            '<nick> <color>',
            'desc': ('Fix a color for a nick. Use "unset" instead of a '
                     'color to remove the attribution'),
            'shortdesc':
            'Fix a color for a nick.',
            'completion':
            self.completion_color
        }, {
            'name':
            'cycle',
            'func':
            self.command_cycle,
            'usage':
            '[message]',
            'desc':
            'Leave the current room and rejoin it immediately.',
            'shortdesc':
            'Leave and re-join the room.'
        }, {
            'name':
            'info',
            'func':
            self.command_info,
            'usage':
            '<nickname>',
            'desc': ('Display some information about the user '
                     'in the MUC: their role, affiliation,'
                     ' status and status message.'),
            'shortdesc':
            'Show a user\'s infos.',
            'completion':
            self.completion_info
        }, {
            'name':
            'configure',
            'func':
            self.command_configure,
            'desc':
            'Configure the current room, through a form.',
            'shortdesc':
            'Configure the room.'
        }, {
            'name':
            'version',
            'func':
            self.command_version,
            'usage':
            '<jid or nick>',
            'desc': ('Get the software version of the given JID'
                     ' or nick in room (usually its XMPP client'
                     ' and Operating System).'),
            'shortdesc':
            'Get the software version of a jid.',
            'completion':
            self.completion_version
        }, {
            'name':
            'names',
            'func':
            self.command_names,
            'desc':
            'Get the users in the room with their roles.',
            'shortdesc':
            'List the users.'
        }, {
            'name':
            'invite',
            'func':
            self.command_invite,
            'desc':
            'Invite a contact to this room',
            'usage':
            '<jid> [reason]',
            'shortdesc':
            'Invite a contact to this room',
            'completion':
            self.completion_invite
        }, {
            'name':
            'request_voice',
            'func':
            self.command_request_voice,
            'desc':
            'Request voice when we are a visitor in a moderated room',
            'usage':
            '[role]',
            'shortdesc':
            'Request voice in a moderated room',
            'completion':
            self.completion_request_voice
        }])


class PresenceError(Exception):
    pass


def dissect_presence(presence: Presence) -> Tuple[str, str, str, str, str, str, JID, str]:
    """
    Extract relevant information from a presence
    """
    from_nick = presence['from'].resource
    from_room = presence['from'].bare
    # Check if it's not an error presence.
    if presence['type'] == 'error':
        raise PresenceError(presence)
    affiliation = presence['muc']['affiliation']
    show = presence['show']
    status = presence['status']
    role = presence['muc']['role']
    jid = presence['muc']['jid']
    typ = presence['type']
    return from_nick, from_room, affiliation, show, status, role, jid, typ
