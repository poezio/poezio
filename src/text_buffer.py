# Copyright 2010 Le Coz Florent <louizatakk@fedoraproject.org>
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

from message import Message
from datetime import datetime
import theme

class TextBuffer(object):
    """
    This class just keep trace of messages, in a list with various
    informations and attributes.
    """
    def __init__(self):
        self.messages = []         # Message objects
        self.pos = 0

    def add_message(self, txt, time=None, nickname=None, colorized=False):
        color = theme.COLOR_NORMAL_TEXT
        user = None
        time = time or datetime.now()
        if self.pos:            # avoid scrolling of one line when one line is received
            self.pos += 1
        self.messages.append(Message(txt, time, nickname, user, color, colorized))

    def remove_line_separator(self):
        """
        Remove the line separator
        """
        if None in self.messages:
            self.messages.remove(None)

    def add_line_separator(self):
        """
        add a line separator at the end of messages list
        """
        if None not in self.messages:
            self.messages.append(None)

    def scroll_up(self, dist=14):
        # The pos can grow a lot over the top of the number of
        # available lines, it will be fixed on the next refresh of the
        # screen anyway
        self.pos += dist

    def scroll_down(self, dist=14):
        self.pos -= dist
        if self.pos <= 0:
            self.pos = 0

