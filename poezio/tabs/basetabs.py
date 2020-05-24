"""
Module for the base Tabs

The root class Tab defines the generic interface and attributes of a
tab. A tab organizes various Windows around the screen depending
of the tab specificity. If the tab shows messages, it will also
reference a buffer containing the messages.

Each subclass should redefine its own refresh() and resize() method
according to its windows.

This module also defines ChatTabs, the parent class for all tabs
revolving around chats.
"""

import copy
import logging
import string
import asyncio
import time
from math import ceil, log10
from datetime import datetime
from xml.etree import ElementTree as ET
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Union,
    TYPE_CHECKING,
)

from poezio import (
    poopt,
    timed_events,
    xhtml,
    windows
)
from poezio.core.structs import Command, Completion, Status
from poezio.common import safeJID
from poezio.config import config
from poezio.decorators import command_args_parser, refresh_wrapper
from poezio.logger import logger
from poezio.text_buffer import TextBuffer
from poezio.theming import get_theme, dump_tuple
from poezio.ui.funcs import truncate_nick
from poezio.ui.consts import LONG_FORMAT_LENGTH
from poezio.ui.types import BaseMessage, InfoMessage, Message

from slixmpp import JID, InvalidJID, Message as SMessage

if TYPE_CHECKING:
    from _curses import _CursesWindow  # pylint: disable=E0611

log = logging.getLogger(__name__)

NS_MUC_USER = 'http://jabber.org/protocol/muc#user'

# getters for tab colors (lambdas, so that they are dynamic)
STATE_COLORS = {
    'disconnected': lambda: get_theme().COLOR_TAB_DISCONNECTED,
    'scrolled': lambda: get_theme().COLOR_TAB_SCROLLED,
    'nonempty': lambda: get_theme().COLOR_TAB_NONEMPTY,
    'joined': lambda: get_theme().COLOR_TAB_JOINED,
    'message': lambda: get_theme().COLOR_TAB_NEW_MESSAGE,
    'composing': lambda: get_theme().COLOR_TAB_COMPOSING,
    'highlight': lambda: get_theme().COLOR_TAB_HIGHLIGHT,
    'private': lambda: get_theme().COLOR_TAB_PRIVATE,
    'normal': lambda: get_theme().COLOR_TAB_NORMAL,
    'current': lambda: get_theme().COLOR_TAB_CURRENT,
    'attention': lambda: get_theme().COLOR_TAB_ATTENTION,
}
VERTICAL_STATE_COLORS = {
    'disconnected': lambda: get_theme().COLOR_VERTICAL_TAB_DISCONNECTED,
    'scrolled': lambda: get_theme().COLOR_VERTICAL_TAB_SCROLLED,
    'nonempty': lambda: get_theme().COLOR_VERTICAL_TAB_NONEMPTY,
    'joined': lambda: get_theme().COLOR_VERTICAL_TAB_JOINED,
    'message': lambda: get_theme().COLOR_VERTICAL_TAB_NEW_MESSAGE,
    'composing': lambda: get_theme().COLOR_VERTICAL_TAB_COMPOSING,
    'highlight': lambda: get_theme().COLOR_VERTICAL_TAB_HIGHLIGHT,
    'private': lambda: get_theme().COLOR_VERTICAL_TAB_PRIVATE,
    'normal': lambda: get_theme().COLOR_VERTICAL_TAB_NORMAL,
    'current': lambda: get_theme().COLOR_VERTICAL_TAB_CURRENT,
    'attention': lambda: get_theme().COLOR_VERTICAL_TAB_ATTENTION,
}

# priority of the different tab states when using Alt+e
# higher means more priority, < 0 means not selectable
STATE_PRIORITY = {
    'normal': -1,
    'current': -1,
    'disconnected': 0,
    'nonempty': 0.1,
    'scrolled': 0.5,
    'joined': 0.8,
    'composing': 0.9,
    'message': 1,
    'highlight': 2,
    'private': 2,
    'attention': 3
}

SHOW_NAME = {
    'dnd': 'busy',
    'away': 'away',
    'xa': 'not available',
    'chat': 'chatty',
    '': 'available'
}


class Tab:
    plugin_commands = {}  # type: Dict[str, Command]
    plugin_keys = {}  # type: Dict[str, Callable]
    # Placeholder values, set on resize
    height = 1
    width = 1

    def __init__(self, core):
        self.core = core
        self.nb = 0
        if not hasattr(self, 'name'):
            self.name = self.__class__.__name__
        self.input = None
        self.closed = False
        self._state = 'normal'
        self._prev_state = None

        self.need_resize = False
        self.key_func = {}  # each tab should add their keys in there
        # and use them in on_input
        self.commands = {}  # and their own commands

    @property
    def size(self) -> int:
        return self.core.size

    @staticmethod
    def tab_win_height() -> int:
        """
        Returns 1 or 0, depending on if we are using the vertical tab list
        or not.
        """
        if config.get('enable_vertical_tab_list'):
            return 0
        return 1

    @property
    def info_win(self):
        return self.core.information_win

    @property
    def color(self):
        return STATE_COLORS[self._state]()

    @property
    def vertical_color(self):
        return VERTICAL_STATE_COLORS[self._state]()

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: str):
        if value not in STATE_COLORS:
            log.debug("Invalid value for tab state: %s", value)
        elif STATE_PRIORITY[value] < STATE_PRIORITY[self._state] and \
                value not in ('current', 'disconnected') and \
                not (self._state == 'scrolled' and value == 'disconnected'):
            log.debug(
                "Did not set state because of lower priority, asked: %s, kept: %s",
                value, self._state)
        elif self._state == 'disconnected' and value not in ('joined',
                                                             'current'):
            log.debug(
                'Did not set state because disconnected tabs remain visible')
        else:
            self._state = value
            if self._state == 'current':
                self._prev_state = None

    def set_state(self, value: str):
        self._state = value

    def save_state(self):
        if self._state != 'composing':
            self._prev_state = self._state

    def restore_state(self):
        if self.state == 'composing' and self._prev_state:
            self._state = self._prev_state
            self._prev_state = None
        elif not self._prev_state:
            self._state = 'normal'

    @staticmethod
    def resize(scr: '_CursesWindow'):
        Tab.height, Tab.width = scr.getmaxyx()
        windows.base_wins.TAB_WIN = scr

    def missing_command_callback(self, command_name):
        """
        Callback executed when a command is not found.
        Returns True if the callback took care of displaying
        the error message, False otherwise.
        """
        return False

    def register_commands_batch(self, commands: List[Dict[str, Any]]):
        """
        Add several commands in a row, using a list of dictionaries
        """
        for command in commands:
            name = command['name']
            func = command['func']
            desc = command.get('desc', '')
            shortdesc = command.get('shortdesc', '')
            completion = command.get('completion')
            usage = command.get('usage', '')
            self.register_command(
                name,
                func,
                desc=desc,
                shortdesc=shortdesc,
                completion=completion,
                usage=usage)

    def register_command(self,
                         name: str,
                         func: Callable,
                         *,
                         desc='',
                         shortdesc='',
                         completion: Optional[Callable] = None,
                         usage=''):
        """
        Add a command
        """
        if name in self.commands:
            return
        if not desc and shortdesc:
            desc = shortdesc
        self.commands[name] = Command(func, desc, completion, shortdesc, usage)

    def complete_commands(self, the_input: windows.Input) -> bool:
        """
        Does command completion on the specified input for both global and tab-specific
        commands.
        This should be called from the completion method (on tab, for example), passing
        the input where completion is to be made.
        It can completion the command name itself or an argument of the command.
        Returns True if a completion was made, False else.
        """
        txt = the_input.get_text()
        # check if this is a command
        if txt.startswith('/') and not txt.startswith('//'):
            position = the_input.get_argument_position(quoted=False)
            if position == 0:
                words = ['/%s'% (name) for name in sorted(self.core.commands)] +\
                    ['/%s' % (name) for name in sorted(self.commands)]
                the_input.new_completion(words, 0)
                # Do not try to cycle command completion if there was only
                # one possibility. The next tab will complete the argument.
                # Otherwise we would need to add a useless space before being
                # able to complete the arguments.
                hit_copy = set(the_input.hit_list)
                if len(hit_copy) == 1:
                    the_input.do_command(' ')
                    the_input.reset_completion()
                return True
            # check if we are in the middle of the command name
            elif len(txt.split()) > 1 or\
                    (txt.endswith(' ') and not the_input.last_completion):
                command_name = txt.split()[0][1:]
                if command_name in self.commands:
                    command = self.commands[command_name]
                elif command_name in self.core.commands:
                    command = self.core.commands[command_name]
                else:  # Unknown command, cannot complete
                    return False
                if command.comp is None:
                    return False  # There's no completion function
                comp = command.comp(the_input)
                if comp:
                    return comp.run()
                return comp
        return False

    def execute_command(self, provided_text: str) -> bool:
        """
        Execute the command in the input and return False if
        the input didn't contain a command
        """
        txt = provided_text or self.input.key_enter()
        if txt.startswith('/') and not txt.startswith('//') and\
                not txt.startswith('/me '):
            command = txt.strip().split()[0][1:]
            arg = txt[2 + len(command):]  # jump the '/' and the ' '
            func = None
            if command in self.commands:  # check tab-specific commands
                func = self.commands[command].func
            elif command in self.core.commands:  # check global commands
                func = self.core.commands[command].func
            else:
                low = command.lower()
                if low in self.commands:
                    func = self.commands[low].func
                elif low in self.core.commands:
                    func = self.core.commands[low].func
                else:
                    if self.missing_command_callback is not None:
                        error_handled = self.missing_command_callback(low)
                    if not error_handled:
                        self.core.information(
                            "Unknown command (%s)" % (command), 'Error')
            if command in ('correct', 'say'):  # hack
                arg = xhtml.convert_simple_to_full_colors(arg)
            else:
                arg = xhtml.clean_text_simple(arg)
            if func:
                if hasattr(self.input, "reset_completion"):
                    self.input.reset_completion()
                func(arg)
            return True
        else:
            return False

    def refresh_tab_win(self):
        if config.get('enable_vertical_tab_list'):
            left_tab_win = self.core.left_tab_win
            if left_tab_win and not self.size.core_degrade_x:
                left_tab_win.refresh()
        elif not self.size.core_degrade_y:
            self.core.tab_win.refresh()

    def refresh_input(self):
        """Refresh the current input if any"""
        if self.input is not None:
            self.input.refresh()
            self.core.doupdate()

    def refresh(self):
        """
        Called on each screen refresh (when something has changed)
        """
        pass

    def get_name(self):
        """
        get the name of the tab
        """
        return self.name

    def get_nick(self) -> str:
        """
        Get the nick of the tab (defaults to its name)
        """
        return self.name

    def get_text_window(self) -> Optional[windows.TextWin]:
        """
        Returns the principal TextWin window, if there's one
        """
        return None

    def on_input(self, key: str, raw: bool):
        """
        raw indicates if the key should activate the associated command or not.
        """
        pass

    def update_commands(self):
        for c in self.plugin_commands:
            if c not in self.commands:
                self.commands[c] = self.plugin_commands[c]

    def update_keys(self):
        for k in self.plugin_keys:
            if k not in self.key_func:
                self.key_func[k] = self.plugin_keys[k]

    def on_lose_focus(self):
        """
        called when this tab loses the focus.
        """
        self.state = 'normal'

    def on_gain_focus(self):
        """
        called when this tab gains the focus.
        """
        self.state = 'current'

    def on_scroll_down(self):
        """
        Defines what happens when we scroll down
        """
        pass

    def on_scroll_up(self):
        """
        Defines what happens when we scroll up
        """
        pass

    def on_line_up(self):
        """
        Defines what happens when we scroll one line up
        """
        pass

    def on_line_down(self):
        """
        Defines what happens when we scroll one line up
        """
        pass

    def on_half_scroll_down(self):
        """
        Defines what happens when we scroll half a screen down
        """
        pass

    def on_half_scroll_up(self):
        """
        Defines what happens when we scroll half a screen up
        """
        pass

    def on_info_win_size_changed(self):
        """
        Called when the window with the information is resized
        """
        pass

    def on_close(self):
        """
        Called when the tab is to be closed
        """
        if self.input:
            self.input.on_delete()
        self.closed = True

    def matching_names(self) -> List[str]:
        """
        Returns a list of strings that are used to name a tab with the /win
        command.  For example you could switch to a tab that returns
        ['hello', 'coucou'] using /win hel, or /win coucou
        If not implemented in the tab, it just doesn’t match with anything.
        """
        return []

    def __del__(self):
        log.debug('------ Closing tab %s', self.__class__.__name__)


class GapTab(Tab):
    def __bool__(self):
        return False

    def __len__(self):
        return 0

    @property
    def name(self):
        return ''

    def refresh(self):
        log.debug(
            'WARNING: refresh() called on a gap tab, this should not happen')


class ChatTab(Tab):
    """
    A tab containing a chat of any type.
    Just use this class instead of Tab if the tab needs a recent-words completion
    Also, ^M is already bound to on_enter
    And also, add the /say command
    """
    plugin_commands = {}  # type: Dict[str, Command]
    plugin_keys = {}  # type: Dict[str, Callable]
    message_type = 'chat'

    def __init__(self, core, jid: Union[JID, str]):
        Tab.__init__(self, core)

        if not isinstance(jid, JID):
            jid = JID(jid)
        assert jid.domain
        self._jid = jid
        #: Is the tab currently requesting MAM data?
        self.query_status = False
        self._name = jid.full  # type: Optional[str]
        self.text_win = windows.TextWin()
        self.directed_presence = None
        self._text_buffer = TextBuffer()
        self._text_buffer.add_window(self.text_win)
        self.chatstate = None  # can be "active", "composing", "paused", "gone", "inactive"
        # We keep a reference of the event that will set our chatstate to "paused", so that
        # we can delete it or change it if we need to
        self.timed_event_paused = None
        self.timed_event_not_paused = None
        # Keeps the last sent message to complete it easily in completion_correct, and to replace it.
        self.last_sent_message = {}
        self.key_func['M-v'] = self.move_separator
        self.key_func['M-h'] = self.scroll_separator
        self.key_func['M-/'] = self.last_words_completion
        self.key_func['^M'] = self.on_enter
        self.register_command(
            'say',
            self.command_say,
            usage='<message>',
            shortdesc='Send the message.')
        self.register_command(
            'scrollback',
            self.command_scrollback,
            usage="end home clear status goto <+|-linecount>|<linenum>|<timestamp>",
            shortdesc='Scrollback to the given line number, message, or clear the buffer.')
        self.commands['sb'] = self.commands['scrollback']
        self.register_command(
            'xhtml',
            self.command_xhtml,
            usage='<custom xhtml>',
            shortdesc='Send custom XHTML.')
        self.register_command(
            'clear', self.command_clear, shortdesc='Clear the current buffer.')
        self.register_command(
            'correct',
            self.command_correct,
            desc='Fix the last message with whatever you want.',
            shortdesc='Correct the last message.',
            completion=self.completion_correct)
        self.chat_state = None
        self.update_commands()
        self.update_keys()

    @property
    def name(self) -> str:
        if self._name is not None:
            return self._name
        return self._jid.full

    @name.setter
    def name(self, value: Union[JID, str]) -> None:
        if isinstance(value, JID):
            self.jid = value
        elif isinstance(value, str):
            try:
                value = JID(value)
                if value.domain:
                    self._jid = value
            except InvalidJID:
                self._name = value
        else:
            raise TypeError("Name %r must be of type JID or str." % value)

    @property
    def jid(self) -> JID:
        return copy.copy(self._jid)

    @jid.setter
    def jid(self, value: JID) -> None:
        if not isinstance(value, JID):
            raise TypeError("Jid %r must be of type JID." % value)
        assert value.domain
        self._jid = value

    @property
    def general_jid(self) -> JID:
        raise NotImplementedError

    def log_message(self, message: BaseMessage, typ=1):
        """
        Log the messages in the archives.
        """
        name = self.jid.bare
        if not isinstance(message, Message):
            return
        if not logger.log_message(name, message.nickname, message.txt, date=message.time, typ=typ):
            self.core.information('Unable to write in the log file', 'Error')

    def add_message(self, message: BaseMessage, typ=1):
        self.log_message(message, typ=typ)
        self._text_buffer.add_message(message)

    def modify_message(self,
                       txt,
                       old_id,
                       new_id,
                       user=None,
                       jid=None,
                       nickname=None):
        message = self._text_buffer.modify_message(
            txt, old_id, new_id, user=user, jid=jid)
        if message:
            self.log_message(message, typ=1)
            self.text_win.modify_message(message.identifier, message)
            self.core.refresh_window()
            return True
        return False

    def last_words_completion(self):
        """
        Complete the input with words recently said
        """
        # build the list of the recent words
        char_we_dont_want = string.punctuation + ' ’„“”…«»'
        words = []
        for msg in self._text_buffer.messages[:-40:-1]:
            if not msg:
                continue
            txt = xhtml.clean_text(msg.txt)
            for char in char_we_dont_want:
                txt = txt.replace(char, ' ')
            for word in txt.split():
                if len(word) >= 4 and word not in words:
                    words.append(word)
        words.extend([word for word in config.get('words').split(':') if word])
        self.input.auto_completion(words, ' ', quotify=False)

    def on_enter(self):
        txt = self.input.key_enter()
        if txt:
            if not self.execute_command(txt):
                if txt.startswith('//'):
                    txt = txt[1:]
                self.command_say(xhtml.convert_simple_to_full_colors(txt))
        self.cancel_paused_delay()

    @command_args_parser.raw
    def command_xhtml(self, xhtml):
        """"
        /xhtml <custom xhtml>
        """
        message = self.generate_xhtml_message(xhtml)
        if message:
            message.send()

    def generate_xhtml_message(self, arg: str) -> SMessage:
        if not arg:
            return
        try:
            body = xhtml.clean_text(
                xhtml.xhtml_to_poezio_colors(arg, force=True))
            ET.fromstring(arg)
        except:
            self.core.information('Could not send custom xhtml', 'Error')
            log.error('/xhtml: Unable to send custom xhtml', exc_info=True)
            return

        msg = self.core.xmpp.make_message(self.get_dest_jid())
        msg['body'] = body
        msg.enable('html')
        msg['html']['body'] = arg
        return msg

    def get_dest_jid(self) -> JID:
        return self.jid

    @refresh_wrapper.always
    def command_clear(self, ignored):
        """
        /clear
        """
        self._text_buffer.messages = []
        self.text_win.rebuild_everything(self._text_buffer)

    def check_send_chat_state(self):
        "If we should send a chat state"
        return True

    def send_chat_state(self, state, always_send=False):
        """
        Send an empty chatstate message
        """
        from poezio.tabs import PrivateTab

        if self.check_send_chat_state():
            if state in ('active', 'inactive',
                         'gone') and self.inactive and not always_send:
                return
            if config.get_by_tabname('send_chat_states', self.general_jid):
                msg = self.core.xmpp.make_message(self.get_dest_jid())
                msg['type'] = self.message_type
                msg['chat_state'] = state
                self.chat_state = state
                msg['no-store'] = True
                if isinstance(self, PrivateTab):
                    x = ET.Element('{%s}x' % NS_MUC_USER)
                    msg.append(x)
                msg.send()
                return True

    def send_composing_chat_state(self, empty_after):
        """
        Send the "active" or "composing" chatstate, depending
        on the the current status of the input
        """
        name = self.general_jid
        if config.get_by_tabname('send_chat_states', name):
            needed = 'inactive' if self.inactive else 'active'
            self.cancel_paused_delay()
            if not empty_after:
                if self.chat_state != "composing":
                    self.send_chat_state("composing")
                self.set_paused_delay(True)
            elif empty_after and self.chat_state != needed:
                self.send_chat_state(needed, True)

    def set_paused_delay(self, composing):
        """
        we create a timed event that will put us to paused
        in a few seconds
        """
        if not config.get_by_tabname('send_chat_states', self.general_jid):
            return
        # First, cancel the delay if it already exists, before rescheduling
        # it at a new date
        self.cancel_paused_delay()
        new_event = timed_events.DelayedEvent(4, self.send_chat_state,
                                              'paused')
        self.core.add_timed_event(new_event)
        self.timed_event_paused = new_event
        new_event = timed_events.DelayedEvent(
            30, self.send_chat_state, 'inactive'
            if self.inactive else 'active')
        self.core.add_timed_event(new_event)
        self.timed_event_not_paused = new_event

    def cancel_paused_delay(self):
        """
        Remove that event from the list and set it to None.
        Called for example when the input is emptied, or when the message
        is sent
        """
        if self.timed_event_paused is not None:
            self.core.remove_timed_event(self.timed_event_paused)
            self.timed_event_paused = None
            self.core.remove_timed_event(self.timed_event_not_paused)
            self.timed_event_not_paused = None

    def set_last_sent_message(self, msg, correct=False):
        """Ensure last_sent_message is set with the correct attributes"""
        if correct:
            # XXX: Is the copy needed. Is the object passed here reused
            # afterwards? Who knows.
            msg = copy.copy(msg)
            msg['id'] = self.last_sent_message['id']
        self.last_sent_message = msg

    @command_args_parser.raw
    def command_correct(self, line):
        """
        /correct <fixed message>
        """
        if not line:
            self.core.command.help('correct')
            return
        if not self.last_sent_message:
            self.core.information('There is no message to correct.', 'Error')
            return
        self.command_say(line, correct=True)

    def completion_correct(self, the_input):
        if self.last_sent_message and the_input.get_argument_position() == 1:
            return Completion(
                the_input.auto_completion, [self.last_sent_message['body']],
                '',
                quotify=False)
        return True

    @property
    def inactive(self) -> bool:
        """Whether we should send inactive or active as a chatstate"""
        return self.core.status.show in ('xa', 'away') or\
                (hasattr(self, 'directed_presence') and not self.directed_presence)

    def move_separator(self):
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        self.text_win.refresh()
        self.input.refresh()

    def get_conversation_messages(self):
        return self._text_buffer.messages

    def check_scrolled(self):
        if self.text_win.pos != 0:
            self.state = 'scrolled'

    @command_args_parser.raw
    def command_say(self, line, correct=False):
        pass

    def goto_build_lines(self, new_date):
        text_buffer = self._text_buffer
        built_lines = []
        message_count = 0
        timestamp = config.get('show_timestamps')
        nick_size = config.get('max_nick_length')
        for message in text_buffer.messages:
            # Build lines of a message
            txt = message.txt
            nick = truncate_nick(message.nickname, nick_size)
            offset = 0
            theme = get_theme()
            if message.ack:
                if message.ack > 0:
                    offset += poopt.wcswidth(theme.CHAR_ACK_RECEIVED) + 1
                else:
                    offset += poopt.wcswidth(theme.CHAR_NACK) + 1
            if nick:
                offset += poopt.wcswidth(nick) + 2
            if message.revisions > 0:
                offset += ceil(log10(message.revisions + 1))
            if message.me:
                offset += 1
            if timestamp:
                if message.history:
                    offset += 1 + LONG_FORMAT_LENGTH
            lines = poopt.cut_text(txt, self.text_win.width - offset - 1)
            for line in lines:
                built_lines.append(line)
            # Find the message with timestamp less than or equal to the queried
            # timestamp and goto that location in the tab.
            if message.time <= new_date:
                message_count += 1
                if len(self.text_win.built_lines) - self.text_win.height >= len(built_lines):
                    self.text_win.pos = len(self.text_win.built_lines) - self.text_win.height - len(built_lines) + 1
                else:
                    self.text_win.pos = 0
        if message_count == 0:
            self.text_win.scroll_up(len(self.text_win.built_lines))
        self.core.refresh_window()

    @command_args_parser.quoted(0, 2)
    def command_scrollback(self, args):
        """
        /sb clear
        /sb home
        /sb end
        /sb goto <+|-linecount>|<linenum>|<timestamp>
        The format of timestamp must be ‘[dd[.mm]-<days ago>] hh:mi[:ss]’
        """
        if args is None or len(args) == 0:
            args = ['end']
        if len(args) == 1:
            if args[0] == 'end':
                self.text_win.scroll_down(len(self.text_win.built_lines))
                self.core.refresh_window()
                return
            elif args[0] == 'home':
                self.text_win.scroll_up(len(self.text_win.built_lines))
                self.core.refresh_window()
                return
            elif args[0] == 'clear':
                self._text_buffer.messages = []
                self.text_win.rebuild_everything(self._text_buffer)
                self.core.refresh_window()
                return
            elif args[0] == 'status':
                self.core.information('Total %s lines in this tab.' % len(self.text_win.built_lines), 'Info')
                return
        elif len(args) == 2 and args[0] == 'goto':
            for fmt in ('%d %H:%M', '%d %H:%M:%S', '%d:%m %H:%M', '%d:%m %H:%M:%S', '%H:%M', '%H:%M:%S'):
                try:
                    new_date = datetime.strptime(args[1], fmt)
                    if 'd' in fmt and 'm' in fmt:
                        new_date = new_date.replace(year=datetime.now().year)
                    elif 'd' in fmt:
                        new_date = new_date.replace(year=datetime.now().year, month=datetime.now().month)
                    else:
                        new_date = new_date.replace(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
                except ValueError:
                    pass
            if args[1].startswith('-'):
                # Check if the user is giving argument of type goto <-linecount> or goto [-<days ago>] hh:mi[:ss]
                if ' ' in args[1]:
                    new_args = args[1].split(' ')
                    new_args[0] = new_args[0].strip('-')
                    new_date = datetime.now()
                    if new_args[0].isdigit():
                        new_date = new_date.replace(day=new_date.day - int(new_args[0]))
                    for fmt in ('%H:%M', '%H:%M:%S'):
                        try:
                            arg_date = datetime.strptime(new_args[1], fmt)
                            new_date = new_date.replace(hour=arg_date.hour, minute=arg_date.minute, second=arg_date.second)
                        except ValueError:
                            pass
                else:
                    scroll_len = args[1].strip('-')
                    if scroll_len.isdigit():
                        self.text_win.scroll_down(int(scroll_len))
                        self.core.refresh_window()
                        return
            elif args[1].startswith('+'):
                scroll_len = args[1].strip('+')
                if scroll_len.isdigit():
                    self.text_win.scroll_up(int(scroll_len))
                    self.core.refresh_window()
                    return
            # Check for the argument of type goto <linenum>
            elif args[1].isdigit():
                if len(self.text_win.built_lines) - self.text_win.height >= int(args[1]):
                    self.text_win.pos = len(self.text_win.built_lines) - self.text_win.height - int(args[1])
                    self.core.refresh_window()
                    return
                else:
                    self.text_win.pos = 0
                    self.core.refresh_window()
                    return
            elif args[1] == '0':
                args = ['home']
            # new_date is the timestamp for which the user has queried.
            self.goto_build_lines(new_date)

    def on_line_up(self):
        return self.text_win.scroll_up(1)

    def on_line_down(self):
        return self.text_win.scroll_down(1)

    def on_scroll_up(self):
        if not self.query_status:
            from poezio import mam
            mam.schedule_scroll_up(tab=self)
        return self.text_win.scroll_up(self.text_win.height - 1)

    def on_scroll_down(self):
        return self.text_win.scroll_down(self.text_win.height - 1)

    def on_half_scroll_up(self):
        return self.text_win.scroll_up((self.text_win.height - 1) // 2)

    def on_half_scroll_down(self):
        return self.text_win.scroll_down((self.text_win.height - 1) // 2)

    @refresh_wrapper.always
    def scroll_separator(self):
        self.text_win.scroll_to_separator()


class OneToOneTab(ChatTab):
    def __init__(self, core, jid):
        ChatTab.__init__(self, core, jid)

        self.__status = Status("", "")
        self.last_remote_message = datetime.now()

        # Set to true once the first disco is done
        self.__initial_disco = False
        self.check_features()
        self.register_command(
            'unquery', self.command_unquery, shortdesc='Close the tab.')
        self.register_command(
            'close', self.command_unquery, shortdesc='Close the tab.')
        self.register_command(
            'attention',
            self.command_attention,
            usage='[message]',
            shortdesc='Request the attention.',
            desc='Attention: Request the attention of the contact.  Can also '
            'send a message along with the attention.')

    def remote_user_color(self):
        return dump_tuple(get_theme().COLOR_REMOTE_USER)

    def update_status(self, status):
        old_status = self.__status
        if not (old_status.show != status.show
                or old_status.message != status.message):
            return
        self.__status = status
        hide_status_change = config.get_by_tabname('hide_status_change',
                                                   self.jid.bare)
        now = datetime.now()
        dff = now - self.last_remote_message
        if hide_status_change > -1 and dff.total_seconds() > hide_status_change:
            return

        info_c = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        nick = self.get_nick()
        remote = self.remote_user_color()
        msg = '\x19%(color)s}%(nick)s\x19%(info)s} changed: '
        msg %= {'color': remote, 'nick': nick, 'info': info_c}
        if status.message != old_status.message and status.message:
            msg += 'status: %s, ' % status.message
        if status.show in SHOW_NAME:
            msg += 'show: %s, ' % SHOW_NAME[status.show]
        self.add_message(
            InfoMessage(txt=msg[:-2]),
            typ=2,
        )

    def ack_message(self, msg_id: str, msg_jid: JID):
        """
        Ack a message
        """
        new_msg = self._text_buffer.ack_message(msg_id, msg_jid)
        if new_msg:
            self.text_win.modify_message(msg_id, new_msg)
            self.core.refresh_window()

    def nack_message(self, error: str, msg_id: str, msg_jid: JID):
        """
        Non-ack a message (e.g. timeout)
        """
        new_msg = self._text_buffer.nack_message(error, msg_id, msg_jid)
        if new_msg:
            self.text_win.modify_message(msg_id, new_msg)
            self.core.refresh_window()
            return True
        return False

    @command_args_parser.raw
    def command_xhtml(self, xhtml_data):
        message = self.generate_xhtml_message(xhtml_data)
        if message:
            message['type'] = 'chat'
            message._add_receipt = True
            message['chat_sate'] = 'active'
            message.send()
            body = xhtml.xhtml_to_poezio_colors(xhtml_data, force=True)
            self._text_buffer.add_message(
                Message(
                    body,
                    nickname=self.core.own_nick,
                    nick_color=get_theme().COLOR_OWN_NICK,
                    identifier=message['id'],
                    jid=self.core.xmpp.boundjid,
                )
            )
            self.refresh()

    def check_features(self):
        "check the features supported by the other party"
        if safeJID(self.get_dest_jid()).resource:
            self.core.xmpp.plugin['xep_0030'].get_info(
                jid=self.get_dest_jid(),
                timeout=5,
                callback=self.features_checked)

    @command_args_parser.raw
    def command_attention(self, message):
        """/attention [message]"""
        if message != '':
            self.command_say(message, attention=True)
        else:
            msg = self.core.xmpp.make_message(self.get_dest_jid())
            msg['type'] = 'chat'
            msg['attention'] = True
            msg.send()

    @command_args_parser.raw
    def command_say(self, line, correct=False, attention=False):
        pass

    @command_args_parser.ignored
    def command_unquery(self):
        """
        /unquery
        """
        self.send_chat_state('gone', always_send=True)
        self.core.close_tab(self)

    def missing_command_callback(self, command_name):
        if command_name not in ('correct', 'attention'):
            return False

        if command_name == 'correct':
            feature = 'message correction'
        elif command_name == 'attention':
            feature = 'attention requests'
        msg = ('%s does not support %s, therefore the /%s '
               'command is currently disabled in this tab.')
        msg = msg % (self.name, feature, command_name)
        self.core.information(msg, 'Info')
        return True

    def features_checked(self, iq):
        "Features check callback"
        features = iq['disco_info'].get_features() or []
