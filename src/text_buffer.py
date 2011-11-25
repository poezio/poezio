# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Define the TextBuffer class
"""

import logging
log = logging.getLogger(__name__)

import collections

from datetime import datetime
from config import config

Message = collections.namedtuple('Message', 'txt nick_color time str_time nickname user')

class TextBuffer(object):
    """
    This class just keep trace of messages, in a list with various
    informations and attributes.
    """
    def __init__(self, messages_nb_limit=config.get('max_messages_in_memory', 2048)):
        self.messages_nb_limit = messages_nb_limit
        self.messages = []         # Message objects
        self.windows = []       # we keep track of one or more windows
        # so we can pass the new messages to them, as they are added, so
        # they (the windows) can build the lines from the new message

    def add_window(self, win):
        self.windows.append(win)

    def add_message(self, txt, time=None, nickname=None, nick_color=None, history=None, user=None):
        time = time or datetime.now()
        if txt.startswith('/me '):
            if nick_color:
                color = nick_color[0]
            elif user:
                color = user.color[0]
            else:
                color = None
            # TODO: display the bg color too.
            txt = ("\x19%s}* \x195}" % (color or 5,))+ nickname + ' ' + txt[4:]
            nickname = None
        msg = Message(txt='%s\x19o'%(txt.replace('\t', '    '),), nick_color=nick_color,
                      time=time, str_time=time.strftime("%Y-%m-%d %H:%M:%S")\
                                          if history else time.strftime("%H:%M:%S"),\
                      nickname=nickname, user=user)
        self.messages.append(msg)
        while len(self.messages) > self.messages_nb_limit:
            self.messages.pop(0)
        ret_val = None
        for window in self.windows: # make the associated windows
            # build the lines from the new message
            nb = window.build_new_message(msg, history=history)
            if ret_val is None:
                ret_val = nb
            if window.pos != 0:
                window.scroll_up(nb)
        return ret_val or 1

    def del_window(self, win):
        self.windows.remove(win)

    def __del__(self):
        log.debug('** Deleting %s messages from textbuffer' % (len(self.messages)))
