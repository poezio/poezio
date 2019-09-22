
from datetime import datetime
from math import ceil, log10
from typing import Union, Optional, List, Tuple

from poezio.theming import get_theme, dump_tuple
from poezio.ui.funcs import truncate_nick, parse_attrs
from poezio import poopt
from poezio.ui.consts import FORMAT_CHAR


class Message:
    __slots__ = ('txt', 'nick_color', 'time', 'str_time', 'nickname', 'user',
                 'identifier', 'top', 'highlight', 'me', 'old_message', 'revisions',
                 'jid', 'ack')

    def __init__(self,
                 txt: str,
                 time: Optional[datetime],
                 nickname: Optional[str],
                 nick_color: Optional[Tuple],
                 history: bool,
                 user: Optional[str],
                 identifier: Optional[str],
                 top: Optional[bool] = False,
                 str_time: Optional[str] = None,
                 highlight: bool = False,
                 old_message: Optional['Message'] = None,
                 revisions: int = 0,
                 jid: Optional[str] = None,
                 ack: int = 0) -> None:
        """
        Create a new Message object with parameters, check for /me messages,
        and delayed messages
        """
        time = time if time is not None else datetime.now()
        if txt.startswith('/me '):
            me = True
            txt = '\x19%s}%s\x19o' % (dump_tuple(get_theme().COLOR_ME_MESSAGE),
                                      txt[4:])
        else:
            me = False
        str_time = time.strftime("%H:%M:%S")
        if history:
            txt = txt.replace(
                '\x19o',
                '\x19o\x19%s}' % dump_tuple(get_theme().COLOR_LOG_MSG))
            str_time = time.strftime("%Y-%m-%d %H:%M:%S")

        self.txt = txt.replace('\t', '    ') + '\x19o'
        self.nick_color = nick_color
        self.time = time
        self.str_time = str_time
        self.nickname = nickname
        self.user = user
        self.identifier = identifier
        self.top = top
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

    def render(self, width: int, timestamp: bool = False, nick_size: int = 10) -> List["Line"]:
        """
        Build a list of lines from this message.
        """
        txt = self.txt
        if not txt:
            return []
        theme = get_theme()
        if len(self.str_time) > 8:
            default_color = (
                FORMAT_CHAR + dump_tuple(theme.COLOR_LOG_MSG) + '}')  # type: Optional[str]
        else:
            default_color = None
        ret = []  # type: List[Union[None, Line]]
        nick = truncate_nick(self.nickname, nick_size)
        offset = 0
        if self.ack:
            if self.ack > 0:
                offset += poopt.wcswidth(theme.CHAR_ACK_RECEIVED) + 1
            else:
                offset += poopt.wcswidth(theme.CHAR_NACK) + 1
        if nick:
            offset += poopt.wcswidth(nick) + 2  # + nick + '> ' length
        if self.revisions > 0:
            offset += ceil(log10(self.revisions + 1))
        if self.me:
            offset += 1  # '* ' before and ' ' after
        if timestamp:
            if self.str_time:
                offset += 1 + len(self.str_time)
            if theme.CHAR_TIME_LEFT and self.str_time:
                offset += 1
            if theme.CHAR_TIME_RIGHT and self.str_time:
                offset += 1
        lines = poopt.cut_text(txt, width - offset - 1)
        prepend = default_color if default_color else ''
        attrs = []  # type: List[str]
        for line in lines:
            saved = Line(
                msg=self,
                start_pos=line[0],
                end_pos=line[1],
                prepend=prepend)
            attrs = parse_attrs(self.txt[line[0]:line[1]], attrs)
            if attrs:
                prepend = FORMAT_CHAR + FORMAT_CHAR.join(attrs)
            else:
                if default_color:
                    prepend = default_color
                else:
                    prepend = ''
            ret.append(saved)
        return ret


# msg is a reference to the corresponding Message object. text_start and
# text_end are the position delimiting the text in this line.
class Line:
    __slots__ = ('msg', 'start_pos', 'end_pos', 'prepend')

    def __init__(self, msg: Message, start_pos: int, end_pos: int, prepend: str) -> None:
        self.msg = msg
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.prepend = prepend
