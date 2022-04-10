"""
Module for the ConversationTabs

A ConversationTab is a direct chat between two JIDs, outside of a room.

There are two different instances of a ConversationTab:
- A DynamicConversationTab that used to implement XEP-0296 (best
    practices for resource locking), which now stays on the bare JID at
    any time. This is the default.
- A StaticConversationTab that will stay focused on one resource all
    the time.

"""
import asyncio
import curses
import logging
from datetime import datetime
from typing import Dict, Callable

from slixmpp import JID, InvalidJID, Message as SMessage

from poezio.tabs.basetabs import OneToOneTab, Tab

from poezio import common
from poezio import windows
from poezio import xhtml
from poezio.config import config, get_image_cache
from poezio.core.structs import Command
from poezio.decorators import refresh_wrapper
from poezio.roster import roster
from poezio.theming import get_theme, dump_tuple
from poezio.decorators import command_args_parser
from poezio.ui.types import InfoMessage, Message
from poezio.text_buffer import CorrectionError

log = logging.getLogger(__name__)


class ConversationTab(OneToOneTab):
    """
    The tab containing a normal conversation (not from a MUC)
    Must not be instantiated, use Static or Dynamic version only.
    """
    plugin_commands: Dict[str, Command] = {}
    plugin_keys: Dict[str, Callable] = {}
    additional_information: Dict[str, Callable[[str], str]] = {}
    message_type = 'chat'

    def __init__(self, core, jid, initial=None):
        OneToOneTab.__init__(self, core, jid, initial=initial)
        self.nick = None
        self.nick_sent = False
        self.state = 'normal'
        self.upper_bar = windows.ConversationStatusMessageWin()
        self.input = windows.MessageInput()
        # keys
        self.key_func['^I'] = self.completion
        # commands
        self.register_command(
            'version',
            self.command_version,
            desc=
            'Get the software version of the current interlocutor (usually its XMPP client and Operating System).',
            shortdesc='Get the software version of the user.')
        self.register_command(
            'info',
            self.command_info,
            shortdesc='Get the status of the contact.')
        self.register_command(
            'last_activity',
            self.command_last_activity,
            usage='[jid]',
            desc='Get the last activity of the given or the current contact.',
            shortdesc='Get the activity.',
            completion=self.core.completion.last_activity)
        self.register_command(
            'invite',
            self.core.command.impromptu,
            desc='Invite people into an impromptu room.',
            shortdesc='Invite other users to the discussion',
            completion=self.core.completion.impromptu)
        self.update_commands()
        self.update_keys()

    @property
    def general_jid(self):
        return self.jid.bare

    def get_info_header(self):
        raise NotImplementedError

    @staticmethod
    @refresh_wrapper.always
    def add_information_element(plugin_name, callback):
        """
        Lets a plugin add its own information to the ConversationInfoWin
        """
        ConversationTab.additional_information[plugin_name] = callback

    @staticmethod
    @refresh_wrapper.always
    def remove_information_element(plugin_name):
        del ConversationTab.additional_information[plugin_name]

    def completion(self):
        self.complete_commands(self.input)

    async def handle_message(self, message: SMessage, display: bool = True):
        """Handle a received message.

        The message can come from us (carbon copy).
        """

        # Prevent messages coming from our own devices (1:1) to be reflected
        if message['to'].bare == self.core.xmpp.boundjid.bare and \
           message['from'].bare == self.core.xmpp.boundjid.bare:
            _, index = self._text_buffer._find_message(message['id'])
            if index != -1:
                return

        use_xhtml = config.get_by_tabname(
            'enable_xhtml_im',
            message['from'].bare
        )
        tmp_dir = get_image_cache()

        # normal message, we are the recipient
        if message['to'].bare == self.core.xmpp.boundjid.bare:
            conv_jid = message['from']
            jid = conv_jid
            color = get_theme().COLOR_REMOTE_USER
            self.last_remote_message = datetime.now()
            remote_nick = self.get_nick()
        # we wrote the message (happens with carbons)
        elif message['from'].bare == self.core.xmpp.boundjid.bare:
            conv_jid = message['to']
            jid = self.core.xmpp.boundjid
            color = get_theme().COLOR_OWN_NICK
            remote_nick = self.core.own_nick
        # we are not part of that message, drop it
        else:
            return

        await self.core.events.trigger_async('conversation_msg', message, self)

        if not message['body']:
            return
        body = xhtml.get_body_from_message_stanza(
            message, use_xhtml=use_xhtml, extract_images_to=tmp_dir)
        delayed, date = common.find_delayed_tag(message)

        replaced = False
        if message.get_plugin('replace', check=True):
            replaced_id = message['replace']['id']
            if replaced_id and config.get_by_tabname('group_corrections',
                                                     conv_jid.bare):
                try:
                    replaced = self.modify_message(
                        body,
                        replaced_id,
                        message['id'],
                        time=date,
                        jid=jid,
                        nickname=remote_nick)
                except CorrectionError:
                    log.debug('Unable to correct the message: %s', message)
        if not replaced:
            msg = Message(
                txt=body,
                time=date,
                nickname=remote_nick,
                nick_color=color,
                history=delayed,
                identifier=message['id'],
                jid=jid,
            )
            if display:
                self.add_message(msg)
            else:
                self.log_message(msg)

    @refresh_wrapper.always
    @command_args_parser.raw
    async def command_say(self, line: str, attention: bool = False, correct: bool = False):
        await self._initial_log.wait()
        msg: SMessage = self.core.xmpp.make_message(
            mto=self.get_dest_jid(),
            mfrom=self.core.xmpp.boundjid
        )
        msg['type'] = 'chat'
        msg['body'] = line
        if not self.nick_sent:
            msg['nick'] = self.core.own_nick
            self.nick_sent = True
        # trigger the event BEFORE looking for colors.
        # and before displaying the message in the window
        # This lets a plugin insert \x19xxx} colors, that will
        # be converted in xhtml.
        self.core.events.trigger('conversation_say', msg, self)
        if not msg['body']:
            return
        if correct or msg['replace']['id']:
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
        self.core.events.trigger('conversation_say_after', msg, self)
        if not msg['body']:
            return
        self.set_last_sent_message(msg, correct=correct)
        msg._add_receipt = True  # type: ignore
        msg.send()
        await self.core.handler.on_normal_message(msg)
        # Our receipts slixmpp hack
        self.cancel_paused_delay()

    @command_args_parser.quoted(0, 1)
    def command_last_activity(self, args):
        """
        /last_activity [jid]
        """
        if args and args[0]:
            return self.core.command.last_activity(args[0])

        def callback(iq):
            if iq['type'] != 'result':
                if iq['error']['type'] == 'auth':
                    self.core.information(
                        'You are not allowed to see the activity of this contact.',
                        'Error')
                else:
                    self.core.information('Error retrieving the activity',
                                          'Error')
                return
            seconds = iq['last_activity']['seconds']
            status = iq['last_activity']['status']
            from_ = iq['from']
            msg = '\x19%s}The last activity of %s was %s ago%s'
            user = ''
            try:
                user = JID(from_).user
            except InvalidJID:
                pass

            if not user:
                msg = '\x19%s}The uptime of %s is %s.' % (
                    dump_tuple(get_theme().COLOR_INFORMATION_TEXT), from_,
                    common.parse_secs_to_str(seconds))
            else:
                msg = '\x19%s}The last activity of %s was %s ago%s' % (
                    dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
                    from_,
                    common.parse_secs_to_str(seconds),
                    (' and their last status was %s' % status)
                    if status else '',
                )
            self.add_message(InfoMessage(msg))
            self.core.refresh_window()

        self.core.xmpp.plugin['xep_0012'].get_last_activity(
            self.get_dest_jid(), callback=callback)

    @refresh_wrapper.conditional
    @command_args_parser.ignored
    def command_info(self):
        contact = roster[self.get_dest_jid()]
        try:
            jid = JID(self.get_dest_jid())
        except InvalidJID:
            jid = JID('')
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        if resource:
            status = (f', Status: {resource.status}') if resource.status else ''
            show = f"Show: {resource.presence or 'available'}"
            self.add_message(InfoMessage(f'{show}{status}'))
            return True
        self.add_message(
            InfoMessage("No information available"),
        )
        return True

    @command_args_parser.quoted(0, 1)
    async def command_version(self, args):
        """
        /version [jid]
        """
        if args:
            return await self.core.command.version(args[0])
        jid = self.jid
        if not jid.resource:
            if jid in roster:
                resource = roster[jid].get_highest_priority_resource()
                jid = resource.jid if resource else jid
        iq = await self.core.xmpp.plugin['xep_0092'].get_version(jid)
        self.core.handler.on_version_result(iq)

    def resize(self):
        self.need_resize = False
        if self.size.tab_degrade_y:
            display_bar = False
            info_win_height = 0
            tab_win_height = 0
            bar_height = 0
        else:
            display_bar = True
            info_win_height = self.core.information_win_size
            tab_win_height = Tab.tab_win_height()
            bar_height = 1

        self.text_win.resize(
            self.height - 2 - bar_height - info_win_height - tab_win_height,
            self.width, bar_height, 0, self._text_buffer,
            force=self.ui_config_changed
        )
        self.ui_config_changed = False
        if display_bar:
            self.upper_bar.resize(1, self.width, 0, 0)
        self.get_info_header().resize(
            1, self.width, self.height - 2 - info_win_height - tab_win_height,
            0)
        self.input.resize(1, self.width, self.height - 1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        display_bar = display_info_win = not self.size.tab_degrade_y

        self.text_win.refresh()

        if display_bar:
            self.upper_bar.refresh(self.get_dest_jid(),
                                   roster[self.get_dest_jid()])
        self.get_info_header().refresh(
            self.get_dest_jid(), roster[self.get_dest_jid()], self.text_win,
            self.chatstate, ConversationTab.additional_information)

        if display_info_win:
            self.info_win.refresh()
        self.refresh_tab_win()
        self.input.refresh()

    def refresh_info_header(self):
        self.get_info_header().refresh(
            self.get_dest_jid(), roster[self.get_dest_jid()], self.text_win,
            self.chatstate, ConversationTab.additional_information)
        self.input.refresh()

    def get_nick(self):
        contact = roster[self.jid.bare]
        if contact:
            return contact.name or self.jid.user
        else:
            if self.nick:
                return self.nick
            return self.jid.user or self.jid.domain

    def on_input(self, key, raw):
        if not raw and key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key, raw=raw)
        empty_after = self.input.get_text() == '' or (
            self.input.get_text().startswith('/')
            and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)
        return False

    def on_lose_focus(self):
        contact = roster[self.get_dest_jid()]
        try:
            jid = JID(self.get_dest_jid())
        except InvalidJID:
            jid = JID('')
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        if self.input.text:
            self.state = 'nonempty'
        else:
            self.state = 'normal'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        if config.get_by_tabname('send_chat_states', self.general_jid):
            if resource:
                self.send_chat_state('inactive')
        self.check_scrolled()

    def on_gain_focus(self):
        contact = roster[self.get_dest_jid()]
        try:
            jid = JID(self.get_dest_jid())
        except InvalidJID:
            jid = JID('')
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None

        self.state = 'current'
        curses.curs_set(1)
        if (config.get_by_tabname('send_chat_states', self.general_jid)
                and (not self.input.get_text()
                     or not self.input.get_text().startswith('//'))):
            if resource:
                self.send_chat_state('active')

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height - 3:
            return
        self.text_win.resize(
            self.height - 3 - self.core.information_win_size -
            Tab.tab_win_height(), self.width, 1, 0)
        self.get_info_header().resize(
            1, self.width, self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), 0)

    def on_close(self):
        Tab.on_close(self)
        if config.get_by_tabname('send_chat_states', self.general_jid):
            self.send_chat_state('gone')

    def matching_names(self):
        res = []
        jid = self.jid
        res.append((2, jid.bare))
        res.append((1, jid.user))
        contact = roster[self.name]
        if contact and contact.name:
            res.append((0, contact.name))
        return res


class DynamicConversationTab(ConversationTab):
    """
    A conversation tab associated with one bare JID.  It used to
    support resource locking (as described in XEP-0296), but that was a
    bad idea so it has been removed.
    Only one DynamicConversationTab can be opened for a given jid.
    """
    plugin_commands: Dict[str, Command] = {}
    plugin_keys: Dict[str, Callable] = {}

    def __init__(self, core, jid, initial=None):
        self.locked_resource = None
        ConversationTab.__init__(self, core, jid, initial=initial)
        self.jid.resource = None
        self.info_header = windows.DynamicConversationInfoWin()
        self.register_command(
            'unlock', self.unlock_command, shortdesc='Deprecated, do nothing.')
        self.resize()
        self.update_commands()
        self.update_keys()

    def get_info_header(self):
        return self.info_header

    def lock(self, resource):
        pass

    def unlock_command(self, arg=None):
        pass

    def unlock(self, from_=None):
        pass

    def get_dest_jid(self):
        """
        Returns the bare jid.
        """
        return self.jid.bare

    def refresh(self):
        """
        Different from the parent class only for the info_header object.
        """
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        display_bar = display_info_win = not self.size.tab_degrade_y

        self.text_win.refresh()
        if display_bar:
            self.upper_bar.refresh(self.jid.bare, roster[self.jid.bare])
        displayed_jid = self.jid.bare
        self.get_info_header().refresh(displayed_jid, roster[self.jid.bare],
                                       self.text_win, self.chatstate,
                                       ConversationTab.additional_information)
        if display_info_win:
            self.info_win.refresh()

        self.refresh_tab_win()
        self.input.refresh()

    def refresh_info_header(self):
        """
        Different from the parent class only for the info_header object.
        """
        displayed_jid = self.jid.bare
        self.get_info_header().refresh(displayed_jid, roster[self.jid.bare],
                                       self.text_win, self.chatstate,
                                       ConversationTab.additional_information)
        self.input.refresh()


class StaticConversationTab(ConversationTab):
    """
    A conversation tab associated with one Full JID. It cannot be locked to
    an different resource or unlocked.
    """
    plugin_commands: Dict[str, Command] = {}
    plugin_keys: Dict[str, Callable] = {}

    def __init__(self, core, jid, initial=None):
        ConversationTab.__init__(self, core, jid, initial=initial)
        assert jid.resource
        self.info_header = windows.ConversationInfoWin()
        self.resize()
        self.update_commands()
        self.update_keys()

    async def init_logs(self, initial=None) -> None:
        # Disable local logs because…
        pass

    def get_info_header(self):
        return self.info_header
