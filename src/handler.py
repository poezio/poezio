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

                'join-room': list(),
                # Join a room.
                # Args: room, nick

                'room-presence': list(),
                # A presence is received
                # Args: the stanza object

                'room-message': list(),
                # A message is received
                # Args: the stanza object

                # 'xmpp-presence-handler': list(),
                # # A presence is received
                # # Args: the stanza object

                # 'xmpp-iq-handler': list(),
                # # An iq is received
                # # Args: the stanza object

                # 'xmpp-message-handler': list(),
                # # A message is received
                # # Args: the stanza object

                # # - GUI event

                # 'on-quit': list(),
                # # When the user wants to quit.

                # # - Roster and presence

                # 'on-disconnected': list(),
                # # When the user is disconnected from the server.

                # 'on-message-received': list(),
                # # When a message is received.
                # # Args: jid, msg, subject, typ

                # 'send-message': list(),
                # # Send a message to someone.
                # # Args: jid, msg, subj, typ

                # # - vCard (XEP-0054)

                # 'vcard-request': list(),
                # # Request a vcard.
                # # Args: jid

                # 'on-vcard-received': list(),
                # # When a vcard is received.
                # # Args: jid, vcard

                # # - Multi-User Chat (XEP-0045)

                # 'gui-join-room': list(),
                # # Join a room inside the GUI (call `join-room`).
                # # Args: room, nickname

                # 'quit-room': list(),
                # # Quit a room.
                # # Args: room, nick

                # 'on-muc-message-received': list(),
                # # When a message is received.
                # # Args: jid, msg, subject, typ, stanza

                # 'on-muc-presence-changed': list(),
                # # When someone in the roster changes his presence.
                # # Args: jid, priority, show, status, stanza

                # 'on-muc-error': list(),
                # # When the MUC composant sends an error
                # # Args: room, code, msg

                # 'eject-user': list(),
                # # When the user try to eject another one.
                # # Args: room, action, nick, reason

                # 'change-user-role': list(),
                # # When the user try to change the role of someone.
                # # Args: room, nick, role

                # 'change-user-affiliation': list(),
                # # When the user try to change the affiliation of someone.
                # # Args: room, jid, aff

                # 'change-subject': list(),
                # # When the user try to change the topic.
                # # Args: room, subject

                # 'change-nick': list()
                # # When the user try to change his nick.
                # # Args: room, nick
            }

    def connect(self, signal, func):
        """Connect a function to a signal."""
        if func not in self.__signals__[signal]:
            self.__signals__[signal].append(func)
        else:
            print "signal %s doesn't exist." % signal

    def emit(self, signal, **kwargs):
        """Emit a signal."""
        if self.__signals__.has_key(signal):
            for func in self.__signals__[signal]:
                func(**kwargs)
        else:
            print "signal %s doesn't exist." % signal
