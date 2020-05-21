import curses

from datetime import datetime
from functools import singledispatch
from math import ceil, log10
from typing import (
    List,
    Tuple,
    TYPE_CHECKING,
)

from poezio import poopt
from poezio.theming import (
    get_theme,
)
from poezio.ui.consts import (
    FORMAT_CHAR,
    LONG_FORMAT,
    SHORT_FORMAT,
)
from poezio.ui.funcs import (
    truncate_nick,
    parse_attrs,
)
from poezio.ui.types import (
    BaseMessage,
    Message,
    StatusMessage,
    XMLLog,
)

if TYPE_CHECKING:
    from poezio.windows import Win

# msg is a reference to the corresponding Message object. text_start and
# text_end are the position delimiting the text in this line.
class Line:
    __slots__ = ('msg', 'start_pos', 'end_pos', 'prepend')

    def __init__(self, msg: BaseMessage, start_pos: int, end_pos: int, prepend: str) -> None:
        self.msg = msg
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.prepend = prepend

    def __repr__(self):
        return '(%s, %s)' % (self.start_pos, self.end_pos)


LinePos = Tuple[int, int]

def generate_lines(lines: List[LinePos], msg: BaseMessage, default_color: str = '') -> List[Line]: 
    line_objects = []
    attrs = []  # type: List[str]
    prepend = default_color if default_color else ''
    for line in lines:
        saved = Line(
            msg=msg,
            start_pos=line[0],
            end_pos=line[1],
            prepend=prepend)
        attrs = parse_attrs(msg.txt[line[0]:line[1]], attrs)
        if attrs:
            prepend = FORMAT_CHAR + FORMAT_CHAR.join(attrs)
        else:
            if default_color:
                prepend = default_color
            else:
                prepend = ''
        line_objects.append(saved)
    return line_objects


@singledispatch
def build_lines(msg: BaseMessage, width: int, timestamp: bool, nick_size: int = 10) -> List[Line]:
    offset = msg.compute_offset(timestamp, nick_size)
    lines = poopt.cut_text(msg.txt, width - offset - 1)
    return generate_lines(lines, msg, default_color='')


@build_lines.register(type(None))
def build_separator(*args, **kwargs):
    return [None]


@build_lines.register(Message)
def build_message(msg: Message, width: int, timestamp: bool, nick_size: int = 10) -> List[Line]:
    """
    Build a list of lines from this message.
    """
    txt = msg.txt
    if not txt:
        return []
    offset = msg.compute_offset(timestamp, nick_size)
    lines = poopt.cut_text(txt, width - offset - 1)
    generated_lines = generate_lines(lines, msg, default_color='')
    return generated_lines


@build_lines.register(StatusMessage)
def build_status(msg: StatusMessage, width: int, timestamp: bool, nick_size: int = 10) -> List[Line]:
    msg.rebuild()
    offset = msg.compute_offset(timestamp, nick_size)
    lines = poopt.cut_text(msg.txt, width - offset - 1)
    return generate_lines(lines, msg, default_color='')


@build_lines.register(XMLLog)
def build_xmllog(msg: XMLLog, width: int, timestamp: bool, nick_size: int = 10) -> List[Line]:
    offset = msg.compute_offset(timestamp, nick_size)
    lines = poopt.cut_text(msg.txt, width - offset - 1)
    return generate_lines(lines, msg, default_color='')


@singledispatch
def write_pre(msg: BaseMessage, win: 'Win', with_timestamps: bool, nick_size: int) -> int:
    """Write the part before text (only the timestamp)"""
    if with_timestamps:
        return PreMessageHelpers.write_time(win, False, msg.time)
    return 0


@write_pre.register(Message)
def write_pre_message(msg: Message, win: 'Win', with_timestamps: bool, nick_size: int) -> int:
    """Write the part before the body:
        - timestamp (short or long)
        - ack/nack
        - nick (with a "* " for /me)
        - LMC number if present
    """
    offset = 0
    if with_timestamps:
        offset += PreMessageHelpers.write_time(win, msg.history, msg.time)

    if not msg.nickname:  # not a message, nothing to do afterwards
        return offset

    nick = truncate_nick(msg.nickname, nick_size)
    offset += poopt.wcswidth(nick)
    if msg.nick_color:
        color = msg.nick_color
    elif msg.user:
        color = msg.user.color
    else:
        color = None
    if msg.ack:
        if msg.ack > 0:
            offset += PreMessageHelpers.write_ack(win)
        else:
            offset += PreMessageHelpers.write_nack(win)
    if msg.me:
        with win.colored_text(color=get_theme().COLOR_ME_MESSAGE):
            win.addstr('* ')
        PreMessageHelpers.write_nickname(win, nick, color, msg.highlight)
        offset += PreMessageHelpers.write_revisions(win, msg)
        win.addstr(' ')
        offset += 3
    else:
        PreMessageHelpers.write_nickname(win, nick, color, msg.highlight)
        offset += PreMessageHelpers.write_revisions(win, msg)
        win.addstr('> ')
        offset += 2
    return offset


@write_pre.register(XMLLog)
def write_pre_xmllog(msg: XMLLog, win: 'Win', with_timestamps: bool, nick_size: int) -> int:
    """Write the part before the stanza (timestamp + IN/OUT)"""
    offset = 0
    if with_timestamps:
        offset += 1 + PreMessageHelpers.write_time(win, False, msg.time)
    theme = get_theme()
    if msg.incoming:
        char = theme.CHAR_XML_IN
        color = theme.COLOR_XML_IN
    else:
        char = theme.CHAR_XML_OUT
        color = theme.COLOR_XML_OUT
    nick = truncate_nick(char, nick_size)
    offset += poopt.wcswidth(nick)
    PreMessageHelpers.write_nickname(win, char, color)
    win.addstr(' ')
    return offset

class PreMessageHelpers:

    @staticmethod
    def write_revisions(buffer: 'Win', msg: Message) -> int:
        if msg.revisions:
            color = get_theme().COLOR_REVISIONS_MESSAGE
            with buffer.colored_text(color=color):
                buffer.addstr('%d' % msg.revisions)
            return ceil(log10(msg.revisions + 1))
        return 0

    @staticmethod
    def write_ack(buffer: 'Win') -> int:
        theme = get_theme()
        color = theme.COLOR_CHAR_ACK
        with buffer.colored_text(color=color):
            buffer.addstr(theme.CHAR_ACK_RECEIVED)
        buffer.addstr(' ')
        return poopt.wcswidth(theme.CHAR_ACK_RECEIVED) + 1

    @staticmethod
    def write_nack(buffer: 'Win') -> int:
        theme = get_theme()
        color = theme.COLOR_CHAR_NACK
        with buffer.colored_text(color=color):
            buffer.addstr(theme.CHAR_NACK)
        buffer.addstr(' ')
        return poopt.wcswidth(theme.CHAR_NACK) + 1

    @staticmethod
    def write_nickname(buffer: 'Win', nickname: str, color, highlight=False) -> None:
        """
        Write the nickname, using the user's color
        and return the number of written characters
        """
        if not nickname:
            return
        attr = None
        if highlight:
            hl_color = get_theme().COLOR_HIGHLIGHT_NICK
            if hl_color == "reverse":
                attr = curses.A_REVERSE
            else:
                color = hl_color
        with buffer.colored_text(color=color, attr=attr):
            buffer.addstr(nickname)

    @staticmethod
    def write_time(buffer: 'Win', history: bool, time: datetime) -> int:
        """
        Write the date on the yth line of the window
        """
        if time:
            if history:
                format = LONG_FORMAT
            else:
                format = SHORT_FORMAT
            time_str = time.strftime(format)
            color = get_theme().COLOR_TIME_STRING
            with buffer.colored_text(color=color):
                buffer.addstr(time_str)
            buffer.addstr(' ')
            return poopt.wcswidth(time_str) + 1
        return 0
