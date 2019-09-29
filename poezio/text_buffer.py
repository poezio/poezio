"""
Define the TextBuffer class

A text buffer contains a list of intermediate representations of messages
(not xml stanzas, but neither the Lines used in windows.py.

Each text buffer can be linked to multiple windows, that will be rendered
independently by their TextWins.
"""

import logging
log = logging.getLogger(__name__)

from typing import Union, Optional, List, Tuple
from datetime import datetime
from poezio.config import config
from poezio.ui.types import Message, BaseMessage



class CorrectionError(Exception):
    pass


class AckError(Exception):
    pass


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
        # we keep track of one or more windows
        # so we can pass the new messages to them, as they are added, so
        # they (the windows) can build the lines from the new message
        self._windows = []

    def add_window(self, win) -> None:
        self._windows.append(win)

    @property
    def last_message(self) -> Optional[Message]:
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
            top = isinstance(msg, Message) and msg.top
            if window.pos != 0 and top is False:
                window.scroll_up(nb)

        return min(ret_val, 1)

    def _find_message(self, old_id: str) -> int:
        """
        Find a message in the text buffer from its message id
        """
        for i in range(len(self.messages) - 1, -1, -1):
            msg = self.messages[i]
            if msg.identifier == old_id:
                return i
        return -1

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
        i = self._find_message(old_id)
        if i == -1:
            return None
        msg = self.messages[i]
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
                       old_id: str,
                       new_id: str,
                       highlight: bool = False,
                       time: Optional[datetime] = None,
                       user: Optional[str] = None,
                       jid: Optional[str] = None) -> Message:
        """
        Correct a message in a text buffer.
        """

        i = self._find_message(old_id)

        if i == -1:
            log.debug(
                'Message %s not found in text_buffer, abort replacement.',
                old_id)
            raise CorrectionError("nothing to replace")

        msg = self.messages[i]

        if msg.user and msg.user is not user:
            raise CorrectionError("Different users")
        elif msg.history:
            raise CorrectionError("Delayed message")
        elif not msg.user and (msg.jid is None or jid is None):
            raise CorrectionError('Could not check the '
                                  'identity of the sender')
        elif not msg.user and msg.jid != jid:
            raise CorrectionError(
                'Messages %s and %s have not been '
                'sent by the same fullJID' % (old_id, new_id))

        if not time:
            time = msg.time
        message = Message(
            txt=txt,
            time=time,
            nickname=msg.nickname,
            nick_color=msg.nick_color,
            history=False,
            user=msg.user,
            identifier=new_id,
            highlight=highlight,
            old_message=msg,
            revisions=msg.revisions + 1,
            jid=jid)
        self.messages[i] = message
        log.debug('Replacing message %s with %s.', old_id, new_id)
        return message

    def del_window(self, win) -> None:
        self._windows.remove(win)

    def __del__(self):
        size = len(self.messages)
        log.debug('** Deleting %s messages from textbuffer', size)
