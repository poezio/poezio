# Copyright 2010-2011 Le Coz Florent <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

"""
Define the TextBuffer class
"""

import logging
log = logging.getLogger(__name__)

from message import Message
from datetime import datetime
import theme

MESSAGE_NB_LIMIT = 8192

class TextBuffer(object):
    """
    This class just keep trace of messages, in a list with various
    informations and attributes.
    """
    def __init__(self):
        self.messages = []         # Message objects
        self.windows = []       # we keep track of one or more windows
        # so we can pass the new messages to them, as they are added, so
        # they (the windows) can build the lines from the new message

    def add_window(self, win):
        self.windows.append(win)

    def add_message(self, txt, time=None, nickname=None, colorized=False, nick_color=None):
        color = theme.COLOR_NORMAL_TEXT if nickname is not None else theme.COLOR_INFORMATION_TEXT
        nick_color = nick_color
        time = time or datetime.now()
        msg = Message(txt, time, nickname, nick_color, color, colorized)
        self.messages.append(msg)
        while len(self.messages) > MESSAGE_NB_LIMIT:
            self.messages.pop(0)
        for window in self.windows: # make the associated windows
            # build the lines from the new message
            nb = window.build_new_message(msg)
            if window.pos != 0:
                window.scroll_up(nb)

    def del_window(self, win):
        self.windows.remove(win)

    def __del__(self):
        log.debug('** Deleting %s messages from textbuffer' % (len(self.messages)))
