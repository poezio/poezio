# -*- coding: utf-8 -*-

# Copyright 2009, 2010 Erwan Briand
# Copyright 2010, Florent Le Coz <louizatakk@fedoraproject.org>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation version 3 of the License.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from singleton import Singleton

class Handler(Singleton):
    """
    This class is the global handler for the software's signals.
    """
    __is_first_instance = True

    def __init__(self):
        if Handler.__is_first_instance:
            Handler.__is_first_instance = False

            self.__signals__ = {

                'on-connected': list(),
                # At the end of a successful connection process.
                # emitted when presence confirmation is received
                # Args: jid

                'join-room': list(),
                # Join a room.
                # Args: room, nick

                'room-presence': list(),
                # A presence is received
                # Args: the stanza object

                'room-message': list(),
                # A message is received
                # Args: the stanza object

                'room-delayed-message': list(),
                # A message is received
                # Args: the stanza object

                'send-version': list(),
                # We send our version
                # Args: the stanza we reply to

                'send-time': list(),
                # We send our time
                # Args: the stanza we reply to

                'error-message': list(),
                # We send our time
                # Args: the stanza we reply to

                'error': list()
                # We send our time
                # Args: the stanza we reply to
            }

    def connect(self, signal, func):
        """Connect a function to a signal."""
        if func not in self.__signals__[signal]:
            self.__signals__[signal].append(func)

    def emit(self, signal, **kwargs):
        """Emit a signal."""
        if self.__signals__.has_key(signal):
            for func in self.__signals__[signal]:
                func(**kwargs)
