"""
Define the TextBuffer class

A text buffer contains a list of intermediate representations of messages
(not xml stanzas, but neither the Lines used in windows.py.

Each text buffer can be linked to multiple windows, that will be rendered
independently by their TextWins.
"""

import logging
log = logging.getLogger(__name__)

from typing import (
    Dict,
    List,
    Optional,
    TYPE_CHECKING,
    Tuple,
    Union,
)
from dataclasses import dataclass
from datetime import datetime
from poezio.config import config
from poezio.ui.types import (
    BaseMessage,
    Message,
    MucOwnJoinMessage,
    MucOwnLeaveMessage,
)

if TYPE_CHECKING:
    from poezio.windows.text_win import TextWin


class CorrectionError(Exception):
    pass


class AckError(Exception):
    pass


@dataclass
class HistoryGap:
    """Class representing a period of non-presence inside a MUC"""
    leave_message: Optional[MucOwnLeaveMessage]
    join_message: Optional[MucOwnJoinMessage]
    last_timestamp_before_leave: Optional[datetime]
    first_timestamp_after_join: Optional[datetime]


class TextBuffer:
    """
    This class just keep trace of messages, in a list with various
    information and attributes.
    """

    def __init__(self, messages_nb_limit: Optional[int] = None) -> None:

        if messages_nb_limit is None:
            messages_nb_limit = config.get('max_messages_in_memory')
        self._messages_nb_limit = messages_nb_limit  # type: int
        # Message objects
        self.messages = []  # type: List[BaseMessage]
        # COMPAT: Correction id -> Original message id.
        self.correction_ids = {}  # type: Dict[str, str]
        # we keep track of one or more windows
        # so we can pass the new messages to them, as they are added, so
        # they (the windows) can build the lines from the new message
        self._windows = []  # type: List[TextWin]

    def add_window(self, win) -> None:
        self._windows.append(win)

    def find_last_gap_muc(self) -> Optional[HistoryGap]:
        """Find the last known history gap contained in buffer"""
        leave, join = None, None
        for i, item in enumerate(reversed(self.messages)):
            if isinstance(item, MucOwnLeaveMessage):
                leave = (i, item)
                break
            if isinstance(item, MucOwnJoinMessage):
                join = (i, item)
        if join and leave:  # Skip if we find a message in the interval
            real_leave = len(self.messages) - leave[0] - 1
            real_join = len(self.messages) - join[0] - 1
            for i in range(real_leave, real_join, 1):
                if isinstance(self.messages[i], Message):
                    return None
        elif not (join or leave):
            return None
        if leave is None:
            last_timestamp, leave_msg = None, None
        else:
            last_timestamp = None
            leave_msg = leave[1]
            for i in range(len(self.messages) - leave[0] - 1, 0, -1):
                if isinstance(self.messages[i], Message):
                    last_timestamp = self.messages[i].time
                    break
        first_timestamp = datetime.now()
        if join is None:
            join_msg = None
        else:
            join_msg = join[1]
            for i in range(len(self.messages) - join[0], len(self.messages)):
                msg = self.messages[i]
                if isinstance(msg, Message) and msg.time < first_timestamp:
                    first_timestamp = msg.time
                    break
        return HistoryGap(
            leave_message=leave_msg,
            join_message=join_msg,
            last_timestamp_before_leave=last_timestamp,
            first_timestamp_after_join=first_timestamp,
        )

    def get_gap_index(self, gap: HistoryGap) -> Optional[int]:
        """Find the first index to insert into inside a gap"""
        if gap.leave_message is None:
            return 0
        for i, msg in enumerate(self.messages):
            if msg is gap.leave_message:
                return i + 1
        return None

    def add_history_messages(self, messages: List[Message], gap: Optional[HistoryGap] = None) -> None:
        """Insert history messages at their correct place """
        index = 0
        if gap is not None:
            index = self.get_gap_index(gap)
        if index is None:  # Not sure what happened, abort
            return
        for message in messages:
            self.messages.insert(index, message)
            index += 1
            log.debug('inserted message: %s', message)
        for window in self._windows:  # make the associated windows
            window.rebuild_everything(self)

    @property
    def last_message(self) -> Optional[BaseMessage]:
        return self.messages[-1] if self.messages else None

    def add_message(self, msg: BaseMessage):
        """
        Create a message and add it to the text buffer
        """
        self.messages.append(msg)

        while len(self.messages) > self._messages_nb_limit:
            self.messages.pop(0)

        ret_val = 0
        show_timestamps = config.get('show_timestamps')
        nick_size = config.get('max_nick_length')
        for window in self._windows:  # make the associated windows
            # build the lines from the new message
            nb = window.build_new_message(
                msg,
                timestamp=show_timestamps,
                nick_size=nick_size)
            if ret_val == 0:
                ret_val = nb
            if window.pos != 0:
                window.scroll_up(nb)

        return min(ret_val, 1)

    def _find_message(self, orig_id: str) -> Tuple[str, int]:
        """
        Find a message in the text buffer from its message id
        """
        # When looking for a message, ensure the id doesn't appear in a
        # message we've removed from our message list. If so return the index
        # of the corresponding id for the original message instead.
        orig_id = self.correction_ids.get(orig_id, orig_id)

        for i in range(len(self.messages) - 1, -1, -1):
            msg = self.messages[i]
            if msg.identifier == orig_id:
                return (orig_id, i)
        return (orig_id, -1)

    def ack_message(self, old_id: str, jid: str) -> Union[None, bool, Message]:
        """Mark a message as acked"""
        return self._edit_ack(1, old_id, jid)

    def nack_message(self, error: str, old_id: str,
                     jid: str) -> Union[None, bool, Message]:
        """Mark a message as errored"""
        return self._edit_ack(-1, old_id, jid, append=error)

    def _edit_ack(self, value: int, old_id: str, jid: str,
                  append: str = '') -> Union[None, bool, Message]:
        """
        Edit the ack status of a message, and optionally
        append some text.
        """
        _, i = self._find_message(old_id)
        if i == -1:
            return None
        msg = self.messages[i]
        if not isinstance(msg, Message):
            return None
        if msg.ack == 1:  # Message was already acked
            return False
        if msg.jid != jid:
            raise AckError('Wrong JID for message id %s (was %s, expected %s)'
                           % (old_id, msg.jid, jid))

        msg.ack = value
        if append:
            msg.txt += append
        return msg

    def modify_message(self,
                       txt: str,
                       orig_id: str,
                       new_id: str,
                       highlight: bool = False,
                       time: Optional[datetime] = None,
                       user: Optional[str] = None,
                       jid: Optional[str] = None) -> Message:
        """
        Correct a message in a text buffer.

        Version 1.1.0 of Last Message Correction (0308) added clarifications
        that break the way poezio handles corrections. Instead of linking
        corrections to the previous correction/message as we were doing, we
        are now required to link all corrections to the original messages.
        """

        orig_id, i = self._find_message(orig_id)

        if i == -1:
            log.debug(
                'Message %s not found in text_buffer, abort replacement.',
                orig_id)
            raise CorrectionError("nothing to replace")

        msg = self.messages[i]
        if not isinstance(msg, Message):
            raise CorrectionError('Wrong message type')
        if msg.user and msg.user is not user:
            raise CorrectionError("Different users")
        elif msg.delayed:
            raise CorrectionError("Delayed message")
        elif not msg.user and (msg.jid is None or jid is None):
            raise CorrectionError('Could not check the '
                                  'identity of the sender')
        elif not msg.user and msg.jid != jid:
            raise CorrectionError(
                'Messages %s and %s have not been '
                'sent by the same fullJID' % (orig_id, new_id))

        if not time:
            time = msg.time

        self.correction_ids[new_id] = orig_id
        message = Message(
            txt=txt,
            time=time,
            nickname=msg.nickname,
            nick_color=msg.nick_color,
            user=msg.user,
            identifier=orig_id,
            highlight=highlight,
            old_message=msg,
            revisions=msg.revisions + 1,
            jid=jid)
        self.messages[i] = message
        log.debug('Replacing message %s with %s.', orig_id, new_id)
        return message

    def del_window(self, win) -> None:
        self._windows.remove(win)

    def __del__(self):
        size = len(self.messages)
        log.debug('** Deleting %s messages from textbuffer', size)
