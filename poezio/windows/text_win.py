"""
TextWin, the window showing the text messages and info messages in poezio.
Can be locked, scrolled, has a separator, etc…
"""

import logging
import curses
from math import ceil, log10
from typing import Optional, List, Union

from poezio.windows.base_wins import Win, FORMAT_CHAR
from poezio.ui.funcs import truncate_nick, parse_attrs

from poezio import poopt
from poezio.config import config
from poezio.theming import to_curses_attr, get_theme, dump_tuple
from poezio.ui.types import Line, Message

log = logging.getLogger(__name__)


class BaseTextWin(Win):
    __slots__ = ('lines_nb_limit', 'pos', 'built_lines', 'lock', 'lock_buffer',
                 'separator_after')

    def __init__(self, lines_nb_limit: Optional[int] = None) -> None:
        if lines_nb_limit is None:
            lines_nb_limit = config.get('max_lines_in_memory')
        Win.__init__(self)
        self.lines_nb_limit = lines_nb_limit  # type: int
        self.pos = 0
        # Each new message is built and kept here.
        # on resize, we rebuild all the messages
        self.built_lines = []  # type: List[Union[None, Line]]

        self.lock = False
        self.lock_buffer = []  # type: List[Union[None, Line]]
        self.separator_after = None  # type: Optional[Line]

    def toggle_lock(self) -> bool:
        if self.lock:
            self.release_lock()
        else:
            self.acquire_lock()
        return self.lock

    def acquire_lock(self) -> None:
        self.lock = True

    def release_lock(self) -> None:
        for line in self.lock_buffer:
            self.built_lines.append(line)
        self.lock = False

    def scroll_up(self, dist: int = 14) -> bool:
        pos = self.pos
        self.pos += dist
        if self.pos + self.height > len(self.built_lines):
            self.pos = len(self.built_lines) - self.height
            if self.pos < 0:
                self.pos = 0
        return self.pos != pos

    def scroll_down(self, dist: int = 14) -> bool:
        pos = self.pos
        self.pos -= dist
        if self.pos <= 0:
            self.pos = 0
        return self.pos != pos

    # TODO: figure out the type of history.
    def build_new_message(self,
                          message: Message,
                          history=None,
                          clean: bool = True,
                          highlight: bool = False,
                          timestamp: bool = False,
                          top: Optional[bool] = False,
                          nick_size: int = 10) -> int:
        """
        Take one message, build it and add it to the list
        Return the number of lines that are built for the given
        message.
        """
        #pylint: disable=assignment-from-no-return
        lines = self.build_message(
            message, timestamp=timestamp, nick_size=nick_size)
        if top:
            lines.reverse()
            for line in lines:
                self.built_lines.insert(0, line)
        else:
            if self.lock:
                self.lock_buffer.extend(lines)
            else:
                self.built_lines.extend(lines)
        if not lines or not lines[0]:
            return 0
        if clean:
            while len(self.built_lines) > self.lines_nb_limit:
                self.built_lines.pop(0)
        return len(lines)

    def build_message(self, message: Message, timestamp: bool = False, nick_size: int = 10) -> List[Union[None, Line]]:
        """
        Build a list of lines from a message, without adding it
        to a list
        """
        return []

    def refresh(self) -> None:
        pass

    def write_text(self, y: int, x: int, txt: str) -> None:
        """
        write the text of a line.
        """
        self.addstr_colored(txt, y, x)

    def write_time(self, time: str) -> int:
        """
        Write the date on the yth line of the window
        """
        if time:
            color = get_theme().COLOR_TIME_STRING
            curses_color = to_curses_attr(color)
            self._win.attron(curses_color)
            self.addstr(time)
            self._win.attroff(curses_color)
            self.addstr(' ')
            return poopt.wcswidth(time) + 1
        return 0

    # TODO: figure out the type of room.
    def resize(self, height: int, width: int, y: int, x: int, room=None) -> None:
        if hasattr(self, 'width'):
            old_width = self.width
        else:
            old_width = None
        self._resize(height, width, y, x)
        if room and self.width != old_width:
            self.rebuild_everything(room)

        # reposition the scrolling after resize
        # (see #2450)
        buf_size = len(self.built_lines)
        if buf_size - self.pos < self.height:
            self.pos = buf_size - self.height
            if self.pos < 0:
                self.pos = 0

    # TODO: figure out the type of room.
    def rebuild_everything(self, room) -> None:
        self.built_lines = []
        with_timestamps = config.get('show_timestamps')
        nick_size = config.get('max_nick_length')
        for message in room.messages:
            self.build_new_message(
                message,
                clean=False,
                top=message.top,
                timestamp=with_timestamps,
                nick_size=nick_size)
            if self.separator_after is message:
                self.build_new_message(None)
        while len(self.built_lines) > self.lines_nb_limit:
            self.built_lines.pop(0)

    def __del__(self) -> None:
        log.debug('** TextWin: deleting %s built lines',
                  (len(self.built_lines)))
        del self.built_lines


class TextWin(BaseTextWin):
    __slots__ = ('highlights', 'hl_pos', 'nb_of_highlights_after_separator')

    def __init__(self, lines_nb_limit: Optional[int] = None) -> None:
        BaseTextWin.__init__(self, lines_nb_limit)

        # the Lines of the highlights in that buffer
        self.highlights = []  # type: List[Line]
        # the current HL position in that list NaN means that we’re not on
        # an hl. -1 is a valid position (it's before the first hl of the
        # list. i.e the separator, in the case where there’s no hl before
        # it.)
        self.hl_pos = float('nan')

        # Keep track of the number of hl after the separator.
        # This is useful to make “go to next highlight“ work after a “move to separator”.
        self.nb_of_highlights_after_separator = 0

    def next_highlight(self) -> None:
        """
        Go to the next highlight in the buffer.
        (depending on which highlight was selected before)
        if the buffer is already positioned on the last, of if there are no
        highlights, scroll to the end of the buffer.
        """
        log.debug('Going to the next highlight…')
        if (not self.highlights or self.hl_pos != self.hl_pos
                or self.hl_pos >= len(self.highlights) - 1):
            self.hl_pos = float('nan')
            self.pos = 0
            return
        hl_size = len(self.highlights) - 1
        if self.hl_pos < hl_size:
            self.hl_pos += 1
        else:
            self.hl_pos = hl_size
        log.debug("self.hl_pos = %s", self.hl_pos)
        hl = self.highlights[self.hl_pos]
        pos = None
        while not pos:
            try:
                pos = self.built_lines.index(hl)
            except ValueError:
                self.highlights = self.highlights[self.hl_pos + 1:]
                if not self.highlights:
                    self.hl_pos = float('nan')
                    self.pos = 0
                    return
                self.hl_pos = 0
                hl = self.highlights[0]
        self.pos = len(self.built_lines) - pos - self.height
        if self.pos < 0 or self.pos >= len(self.built_lines):
            self.pos = 0

    def previous_highlight(self) -> None:
        """
        Go to the previous highlight in the buffer.
        (depending on which highlight was selected before)
        if the buffer is already positioned on the first, or if there are no
        highlights, scroll to the end of the buffer.
        """
        log.debug('Going to the previous highlight…')
        if not self.highlights or self.hl_pos <= 0:
            self.hl_pos = float('nan')
            self.pos = 0
            return
        if self.hl_pos != self.hl_pos:
            self.hl_pos = len(self.highlights) - 1
        else:
            self.hl_pos -= 1
        log.debug("self.hl_pos = %s", self.hl_pos)
        hl = self.highlights[self.hl_pos]
        pos = None
        while not pos:
            try:
                pos = self.built_lines.index(hl)
            except ValueError:
                self.highlights = self.highlights[self.hl_pos + 1:]
                if not self.highlights:
                    self.hl_pos = float('nan')
                    self.pos = 0
                    return
                self.hl_pos = 0
                hl = self.highlights[0]
        self.pos = len(self.built_lines) - pos - self.height
        if self.pos < 0 or self.pos >= len(self.built_lines):
            self.pos = 0

    def scroll_to_separator(self) -> None:
        """
        Scroll to the first message after the separator.  If no
        separator is present, scroll to the first message of the window
        """
        if None in self.built_lines:
            self.pos = len(self.built_lines) - self.built_lines.index(
                None) - self.height + 1
            if self.pos < 0:
                self.pos = 0
        else:
            self.pos = len(self.built_lines) - self.height + 1
        # Chose a proper position (not too high)
        self.scroll_up(0)
        # Make “next highlight” work afterwards. This makes it easy to
        # review all the highlights since the separator was placed, in
        # the correct order.
        self.hl_pos = len(
            self.highlights) - self.nb_of_highlights_after_separator - 1
        log.debug("self.hl_pos = %s", self.hl_pos)

    def remove_line_separator(self) -> None:
        """
        Remove the line separator
        """
        log.debug('remove_line_separator')
        if None in self.built_lines:
            self.built_lines.remove(None)
            self.separator_after = None

    # TODO: figure out the type of room.
    def add_line_separator(self, room=None) -> None:
        """
        add a line separator at the end of messages list
        room is a textbuffer that is needed to get the previous message
        (in case of resize)
        """
        if None not in self.built_lines:
            self.built_lines.append(None)
            self.nb_of_highlights_after_separator = 0
            log.debug("Resetting number of highlights after separator")
            if room and room.messages:
                self.separator_after = room.messages[-1]

    # TODO: figure out the type of history.
    def build_new_message(self,
                          message: Message,
                          history: bool = False,
                          clean: bool = True,
                          highlight: bool = False,
                          timestamp: bool = False,
                          top: Optional[bool] = False,
                          nick_size: int = 10) -> int:
        """
        Take one message, build it and add it to the list
        Return the number of lines that are built for the given
        message.
        """
        lines = self.build_message(
            message, timestamp=timestamp, nick_size=nick_size)
        if top:
            lines.reverse()
            for line in lines:
                self.built_lines.insert(0, line)
        else:
            if self.lock:
                self.lock_buffer.extend(lines)
            else:
                self.built_lines.extend(lines)
        if not lines or not lines[0]:
            return 0
        if highlight:
            self.highlights.append(lines[0])
            self.nb_of_highlights_after_separator += 1
            log.debug("Number of highlights after separator is now %s",
                      self.nb_of_highlights_after_separator)
        if clean:
            while len(self.built_lines) > self.lines_nb_limit:
                self.built_lines.pop(0)
        return len(lines)

    def build_message(self, message: Optional[Message], timestamp: bool = False, nick_size: int = 10) -> List[Union[None, Line]]:
        """
        Build a list of lines from a message, without adding it
        to a list
        """
        if message is None:  # line separator
            return [None]
        return message.render(self.width, timestamp, nick_size)

    def refresh(self) -> None:
        log.debug('Refresh: %s', self.__class__.__name__)
        if self.height <= 0:
            return
        if self.pos == 0:
            lines = self.built_lines[-self.height:]
        else:
            lines = self.built_lines[-self.height - self.pos:-self.pos]
        with_timestamps = config.get("show_timestamps")
        nick_size = config.get("max_nick_length")
        self._win.move(0, 0)
        self._win.erase()
        offset = 0
        for y, line in enumerate(lines):
            if line:
                msg = line.msg
                if line.start_pos == 0:
                    offset = self.write_pre_msg(msg, with_timestamps,
                                                nick_size)
                elif y == 0:
                    offset = self.compute_offset(msg, with_timestamps,
                                                 nick_size)
                self.write_text(
                    y, offset,
                    line.prepend + line.msg.txt[line.start_pos:line.end_pos])
            else:
                self.write_line_separator(y)
            if y != self.height - 1:
                self.addstr('\n')
        self._win.attrset(0)
        self._refresh()

    def compute_offset(self, msg, with_timestamps, nick_size) -> int:
        offset = 0
        if with_timestamps and msg.str_time:
            offset += poopt.wcswidth(msg.str_time) + 1

        if not msg.nickname:  # not a message, nothing to do afterwards
            return offset

        nick = truncate_nick(msg.nickname, nick_size)
        offset += poopt.wcswidth(nick)
        if msg.ack:
            theme = get_theme()
            if msg.ack > 0:
                offset += poopt.wcswidth(theme.CHAR_ACK_RECEIVED) + 1
            else:
                offset += poopt.wcswidth(theme.CHAR_NACK) + 1
        if msg.me:
            offset += 3
        else:
            offset += 2
        if msg.revisions:
            offset += ceil(log10(msg.revisions + 1))
        offset += self.write_revisions(msg)
        return offset

    def write_pre_msg(self, msg, with_timestamps, nick_size) -> int:
        offset = 0
        if with_timestamps:
            offset += self.write_time(msg.str_time)

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
                offset += self.write_ack()
            else:
                offset += self.write_nack()
        if msg.me:
            self._win.attron(to_curses_attr(get_theme().COLOR_ME_MESSAGE))
            self.addstr('* ')
            self.write_nickname(nick, color, msg.highlight)
            offset += self.write_revisions(msg)
            self.addstr(' ')
            offset += 3
        else:
            self.write_nickname(nick, color, msg.highlight)
            offset += self.write_revisions(msg)
            self.addstr('> ')
            offset += 2
        return offset

    def write_revisions(self, msg) -> int:
        if msg.revisions:
            self._win.attron(
                to_curses_attr(get_theme().COLOR_REVISIONS_MESSAGE))
            self.addstr('%d' % msg.revisions)
            self._win.attrset(0)
            return ceil(log10(msg.revisions + 1))
        return 0

    def write_line_separator(self, y) -> None:
        theme = get_theme()
        char = theme.CHAR_NEW_TEXT_SEPARATOR
        self.addnstr(y, 0, char * (self.width // len(char) - 1), self.width,
                     to_curses_attr(theme.COLOR_NEW_TEXT_SEPARATOR))

    def write_ack(self) -> int:
        theme = get_theme()
        color = theme.COLOR_CHAR_ACK
        self._win.attron(to_curses_attr(color))
        self.addstr(theme.CHAR_ACK_RECEIVED)
        self._win.attroff(to_curses_attr(color))
        self.addstr(' ')
        return poopt.wcswidth(theme.CHAR_ACK_RECEIVED) + 1

    def write_nack(self) -> int:
        theme = get_theme()
        color = theme.COLOR_CHAR_NACK
        self._win.attron(to_curses_attr(color))
        self.addstr(theme.CHAR_NACK)
        self._win.attroff(to_curses_attr(color))
        self.addstr(' ')
        return poopt.wcswidth(theme.CHAR_NACK) + 1

    def write_nickname(self, nickname, color, highlight=False) -> None:
        """
        Write the nickname, using the user's color
        and return the number of written characters
        """
        if not nickname:
            return
        if highlight:
            hl_color = get_theme().COLOR_HIGHLIGHT_NICK
            if hl_color == "reverse":
                self._win.attron(curses.A_REVERSE)
            else:
                color = hl_color
        if color:
            self._win.attron(to_curses_attr(color))
        self.addstr(nickname)
        if color:
            self._win.attroff(to_curses_attr(color))
        if highlight and hl_color == "reverse":
            self._win.attroff(curses.A_REVERSE)

    def modify_message(self, old_id, message) -> None:
        """
        Find a message, and replace it with a new one
        (instead of rebuilding everything in order to correct a message)
        """
        with_timestamps = config.get('show_timestamps')
        nick_size = config.get('max_nick_length')
        for i in range(len(self.built_lines) - 1, -1, -1):
            if self.built_lines[i] and self.built_lines[i].msg.identifier == old_id:
                index = i
                while index >= 0 and self.built_lines[index] and self.built_lines[index].msg.identifier == old_id:
                    self.built_lines.pop(index)
                    index -= 1
                index += 1
                lines = self.build_message(
                    message, timestamp=with_timestamps, nick_size=nick_size)
                for line in lines:
                    self.built_lines.insert(index, line)
                    index += 1
                break

    def __del__(self) -> None:
        log.debug('** TextWin: deleting %s built lines',
                  (len(self.built_lines)))
        del self.built_lines


class XMLTextWin(BaseTextWin):
    __slots__ = ()

    def __init__(self) -> None:
        BaseTextWin.__init__(self)

    def refresh(self) -> None:
        log.debug('Refresh: %s', self.__class__.__name__)
        theme = get_theme()
        if self.height <= 0:
            return
        if self.pos == 0:
            lines = self.built_lines[-self.height:]
        else:
            lines = self.built_lines[-self.height - self.pos:-self.pos]
        self._win.move(0, 0)
        self._win.erase()
        for y, line in enumerate(lines):
            if line:
                msg = line.msg
                if line.start_pos == 0:
                    if msg.nickname == theme.CHAR_XML_OUT:
                        color = theme.COLOR_XML_OUT
                    elif msg.nickname == theme.CHAR_XML_IN:
                        color = theme.COLOR_XML_IN
                    self.write_time(msg.str_time)
                    self.write_prefix(msg.nickname, color)
                    self.addstr(' ')
            if y != self.height - 1:
                self.addstr('\n')
        self._win.attrset(0)
        for y, line in enumerate(lines):
            offset = 0
            # Offset for the timestamp (if any) plus a space after it
            offset += len(line.msg.str_time)
            # space
            offset += 1

            # Offset for the prefix
            offset += poopt.wcswidth(truncate_nick(line.msg.nickname))
            # space
            offset += 1

            self.write_text(
                y, offset,
                line.prepend + line.msg.txt[line.start_pos:line.end_pos])
            if y != self.height - 1:
                self.addstr('\n')
        self._win.attrset(0)
        self._refresh()

    def build_message(self, message: Message, timestamp: bool = False, nick_size: int = 10) -> List[Line]:
        txt = message.txt
        ret = []
        default_color = None
        nick = truncate_nick(message.nickname, nick_size)
        offset = 0
        if nick:
            offset += poopt.wcswidth(nick) + 1  # + nick + ' ' length
        if message.str_time:
            offset += 1 + len(message.str_time)
        theme = get_theme()
        if theme.CHAR_TIME_LEFT and message.str_time:
            offset += 1
        if theme.CHAR_TIME_RIGHT and message.str_time:
            offset += 1
        lines = poopt.cut_text(txt, self.width - offset - 1)
        prepend = default_color if default_color else ''
        attrs = []  # type: List[str]
        for line in lines:
            saved = Line(
                msg=message,
                start_pos=line[0],
                end_pos=line[1],
                prepend=prepend)
            attrs = parse_attrs(message.txt[line[0]:line[1]], attrs)
            if attrs:
                prepend = FORMAT_CHAR + FORMAT_CHAR.join(attrs)
            else:
                if default_color:
                    prepend = default_color
                else:
                    prepend = ''
            ret.append(saved)
        return ret

    def write_prefix(self, nickname, color) -> None:
        self._win.attron(to_curses_attr(color))
        self.addstr(truncate_nick(nickname))
        self._win.attroff(to_curses_attr(color))
