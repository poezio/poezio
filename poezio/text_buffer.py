"""
Define the TextBuffer class

A text buffer contains a list of intermediate representations of messages
(not xml stanzas, but neither the Lines used in windows.py.

Each text buffer can be linked to multiple windows, that will be rendered
independantly by their TextWins.
"""

import logging
log = logging.getLogger(__name__)

from datetime import datetime
from poezio.config import config
from poezio.theming import get_theme, dump_tuple

class Message:
    __slots__ = ('txt', 'nick_color', 'time', 'str_time', 'nickname', 'user',
                 'identifier', 'highlight', 'me', 'old_message', 'revisions',
                 'jid', 'ack')

    def __init__(self, txt, time, nickname, nick_color, history, user,
                 identifier, str_time=None, highlight=False,
                 old_message=None, revisions=0, jid=None, ack=0):
        """
        Create a new Message object with parameters, check for /me messages,
        and delayed messages
        """
        time = time or datetime.now()
        if txt.startswith('/me '):
            me = True
            txt = '\x19%s}%s\x19o' % (dump_tuple(get_theme().COLOR_ME_MESSAGE),
                                      txt[4:])
        else:
            me = False
        if history:
            txt = txt.replace('\x19o', '\x19o\x19%s}' %
                                dump_tuple(get_theme().COLOR_LOG_MSG))
            str_time = time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            if str_time is None:
                str_time = time.strftime("%H:%M:%S")
            else:
                str_time = ''

        self.txt = txt.replace('\t', '    ') + '\x19o'
        self.nick_color = nick_color
        self.time = time
        self.str_time = str_time
        self.nickname = nickname
        self.user = user
        self.identifier = identifier
        self.highlight = highlight
        self.me = me
        self.old_message = old_message
        self.revisions = revisions
        self.jid = jid
        self.ack = ack

    def _other_elems(self):
        "Helper for the repr_message function"
        acc = ['Message(']
        fields = list(self.__slots__)
        fields.remove('old_message')
        for field in fields:
            acc.append('%s=%s' % (field, repr(getattr(self, field))))
        return ', '.join(acc) + ', old_message='

    def __repr__(self):
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

class CorrectionError(Exception):
    pass

class AckError(Exception):
    pass

class TextBuffer(object):
    """
    This class just keep trace of messages, in a list with various
    information and attributes.
    """
    def __init__(self, messages_nb_limit=None):

        if messages_nb_limit is None:
            messages_nb_limit = config.get('max_messages_in_memory')
        self._messages_nb_limit = messages_nb_limit
        # Message objects
        self.messages = []
        # we keep track of one or more windows
        # so we can pass the new messages to them, as they are added, so
        # they (the windows) can build the lines from the new message
        self._windows = []

    def add_window(self, win):
        self._windows.append(win)

    @property
    def last_message(self):
        return self.messages[-1] if self.messages else None

    def add_message(self, txt, time=None, nickname=None,
                    nick_color=None, history=None, user=None, highlight=False,
                    identifier=None, str_time=None, jid=None, ack=0):
        """
        Create a message and add it to the text buffer
        """
        msg = Message(txt, time, nickname, nick_color, history, user,
                      identifier, str_time=str_time, highlight=highlight,
                      jid=jid, ack=ack)
        self.messages.append(msg)

        while len(self.messages) > self._messages_nb_limit:
            self.messages.pop(0)

        ret_val = 0
        show_timestamps = config.get('show_timestamps')
        nick_size = config.get('max_nick_length')
        for window in self._windows: # make the associated windows
                                     # build the lines from the new message
            nb = window.build_new_message(msg, history=history,
                                          highlight=highlight,
                                          timestamp=show_timestamps,
                                          nick_size=nick_size)
            if ret_val == 0:
                ret_val = nb
            if window.pos != 0:
                window.scroll_up(nb)

        return min(ret_val, 1)

    def _find_message(self, old_id):
        """
        Find a message in the text buffer from its message id
        """
        for i in range(len(self.messages) -1, -1, -1):
            msg = self.messages[i]
            if msg.identifier == old_id:
                return i
        return -1

    def ack_message(self, old_id, jid):
        """Mark a message as acked"""
        return self._edit_ack(1, old_id, jid)

    def nack_message(self, error, old_id, jid):
        """Mark a message as errored"""
        return self._edit_ack(-1, old_id, jid, append=error)

    def _edit_ack(self, value, old_id, jid, append=''):
        """
        Edit the ack status of a message, and optionally
        append some text.
        """
        i = self._find_message(old_id)
        if i == -1:
            return
        msg = self.messages[i]
        if msg.jid != jid:
            raise AckError('Wrong JID for message id %s (was %s, expected %s)' %
                            (old_id, msg.jid, jid))

        msg.ack = value
        if append:
            msg.txt += append
        return msg

    def modify_message(self, txt, old_id, new_id, highlight=False,
                       time=None, user=None, jid=None):
        """
        Correct a message in a text buffer.
        """

        i = self._find_message(old_id)

        if i == -1:
            log.debug('Message %s not found in text_buffer, abort replacement.',
                      old_id)
            raise CorrectionError("nothing to replace")

        msg = self.messages[i]

        if msg.user and msg.user is not user:
            raise CorrectionError("Different users")
        elif len(msg.str_time) > 8: # ugly
            raise CorrectionError("Delayed message")
        elif not msg.user and (msg.jid is None or jid is None):
            raise CorrectionError('Could not check the '
                                  'identity of the sender')
        elif not msg.user and msg.jid != jid:
            raise CorrectionError('Messages %s and %s have not been '
                                  'sent by the same fullJID' %
                                      (old_id, new_id))

        if not time:
            time = msg.time
        message = Message(txt, time, msg.nickname, msg.nick_color, None,
                          msg.user, new_id, highlight=highlight,
                          old_message=msg, revisions=msg.revisions + 1,
                          jid=jid)
        self.messages[i] = message
        log.debug('Replacing message %s with %s.', old_id, new_id)
        return message

    def del_window(self, win):
        self._windows.remove(win)

    def __del__(self):
        size = len(self.messages)
        log.debug('** Deleting %s messages from textbuffer', size)
