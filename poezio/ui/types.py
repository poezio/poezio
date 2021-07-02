from __future__ import annotations

from datetime import datetime
from math import ceil, log10
from typing import Optional, Tuple, Dict, Any, Callable

from slixmpp import JID

from poezio import poopt
from poezio.theming import dump_tuple, get_theme
from poezio.ui.funcs import truncate_nick
from poezio.user import User


class BaseMessage:
    """Base class for all ui-related messages"""
    __slots__ = ('txt', 'time', 'identifier')

    txt: str
    identifier: str
    time: datetime

    def __init__(self, txt: str, identifier: str = '', time: Optional[datetime] = None):
        self.txt = txt
        self.identifier = identifier
        if time is not None:
            self.time = time
        else:
            self.time = datetime.now()

    def compute_offset(self, with_timestamps: bool, nick_size: int) -> int:
        """Compute the offset of the message"""
        theme = get_theme()
        return theme.SHORT_TIME_FORMAT_LENGTH + 1


class EndOfArchive(BaseMessage):
    """Marker added to a buffer when we reach the end of a MAM archive"""


class InfoMessage(BaseMessage):
    """Information message"""
    def __init__(self, txt: str, identifier: str = '', time: Optional[datetime] = None):
        txt = ('\x19%s}' % dump_tuple(get_theme().COLOR_INFORMATION_TEXT)) + txt
        super().__init__(txt=txt, identifier=identifier, time=time)


class UIMessage(BaseMessage):
    """Message displayed through poezio UI"""
    __slots__ = ('level', 'color')
    level: str
    color: Optional[Tuple]

    def __init__(self, txt: str, level: str):
        BaseMessage.__init__(self, txt=txt)
        self.level = level.capitalize()
        colors = get_theme().INFO_COLORS
        self.color = colors.get(level.lower(), colors.get('default', None))

    def compute_offset(self, with_timestamps: bool, nick_size: int) -> int:
        """Compute the x-position at which the message should be printed"""
        offset = 0
        theme = get_theme()
        if with_timestamps:
            offset += 1 + theme.SHORT_TIME_FORMAT_LENGTH
        level = self.level
        if not level:  # not a message, nothing to do afterwards
            return offset
        level = truncate_nick(level, nick_size) or ''
        offset += poopt.wcswidth(level)
        offset += 2
        return offset


class LoggableTrait:
    """Trait for classes of messages that should go through the logger"""
    pass


class PersistentInfoMessage(InfoMessage, LoggableTrait):
    """Information message thatt will be logged"""
    pass


class MucOwnLeaveMessage(InfoMessage, LoggableTrait):
    """Status message displayed on our room leave/kick/ban"""


class MucOwnJoinMessage(InfoMessage, LoggableTrait):
    """Status message displayed on our room join"""


class XMLLog(BaseMessage):
    """XML Log message"""
    __slots__ = ('incoming')
    incoming: bool

    def __init__(
            self,
            txt: str,
            incoming: bool,
    ):
        BaseMessage.__init__(
            self,
            txt=txt,
        )
        self.incoming = incoming

    def compute_offset(self, with_timestamps: bool, nick_size: int) -> int:
        offset = 0
        theme = get_theme()
        if with_timestamps:
            offset += 1 + theme.SHORT_TIME_FORMAT_LENGTH
        if self.incoming:
            nick = theme.CHAR_XML_IN
        else:
            nick = theme.CHAR_XML_OUT
        nick = truncate_nick(nick, nick_size) or ''
        offset += 1 + len(nick)
        return offset


class StatusMessage(BaseMessage):
    """A dynamically formatted status message"""
    __slots__ = ('format_string', 'format_args')
    format_string: str
    format_args: Dict[str, Callable[[], Any]]

    def __init__(self, format_string: str, format_args: dict):
        BaseMessage.__init__(
            self,
            txt='',
        )
        self.format_string = format_string
        self.format_args = format_args
        self.rebuild()

    def rebuild(self):
        real_args = {}
        for key, func in self.format_args.items():
            real_args[key] = func()
        self.txt = self.format_string.format(**real_args)


class Message(BaseMessage, LoggableTrait):
    __slots__ = ('nick_color', 'nickname', 'user', 'delayed', 'history',
                 'highlight', 'me', 'old_message', 'revisions',
                 'jid', 'ack')
    nick_color: Optional[Tuple]
    nickname: Optional[str]
    user: Optional[User]
    delayed: bool
    history: bool
    highlight: bool
    me: bool
    old_message: Optional[Message]
    revisions: int
    jid: Optional[JID]
    ack: int

    def __init__(self,
                 txt: str,
                 nickname: Optional[str],
                 time: Optional[datetime] = None,
                 nick_color: Optional[Tuple] = None,
                 delayed: bool = False,
                 history: bool = False,
                 user: Optional[User] = None,
                 identifier: Optional[str] = '',
                 highlight: bool = False,
                 old_message: Optional[Message] = None,
                 revisions: int = 0,
                 jid: Optional[JID] = None,
                 ack: int = 0) -> None:
        """
        Create a new Message object with parameters, check for /me messages,
        and delayed messages
        """
        BaseMessage.__init__(
            self,
            txt=txt.replace('\t', '    ') + '\x19o',
            identifier=identifier or '',
            time=time,
        )
        if txt.startswith('/me '):
            me = True
            txt = '\x19%s}%s\x19o' % (dump_tuple(get_theme().COLOR_ME_MESSAGE),
                                      txt[4:])
        else:
            me = False
        self.txt = txt
        self.delayed = delayed or history
        self.history = history
        self.nickname = nickname
        self.nick_color = nick_color
        self.user = user
        self.highlight = highlight
        self.me = me
        self.old_message = old_message
        self.revisions = revisions
        self.jid = jid
        self.ack = ack

    def _other_elems(self) -> str:
        "Helper for the repr_message function"
        acc = []
        fields = list(self.__slots__)
        fields.remove('old_message')
        for field in fields:
            acc.append('%s=%s' % (field, repr(getattr(self, field))))
        return 'Message(%s, %s' % (', '.join(acc), 'old_message=')

    def __repr__(self) -> str:
        """
        repr() for the Message class, for debug purposes, since the default
        repr() is recursive, so it can stack overflow given too many revisions
        of a message
        """
        init = self._other_elems()
        acc = [init]
        next_message = self.old_message
        rev = 1
        while next_message is not None:
            acc.append(next_message._other_elems())
            next_message = next_message.old_message
            rev += 1
        acc.append('None')
        while rev:
            acc.append(')')
            rev -= 1
        return ''.join(acc)

    def compute_offset(self, with_timestamps: bool, nick_size: int) -> int:
        """Compute the x-position at which the message should be printed"""
        offset = 0
        theme = get_theme()
        if with_timestamps:
            if self.history:
                offset += 1 + theme.LONG_TIME_FORMAT_LENGTH
            else:
                offset += 1 + theme.SHORT_TIME_FORMAT_LENGTH

        if not self.nickname:  # not a message, nothing to do afterwards
            return offset

        nick = truncate_nick(self.nickname, nick_size) or ''
        offset += poopt.wcswidth(nick)
        if self.ack:
            theme = get_theme()
            if self.ack > 0:
                offset += poopt.wcswidth(theme.CHAR_ACK_RECEIVED) + 1
            else:
                offset += poopt.wcswidth(theme.CHAR_NACK) + 1
        if self.me:
            offset += 3
        else:
            offset += 2
        if self.revisions:
            offset += ceil(log10(self.revisions + 1))
        return offset
