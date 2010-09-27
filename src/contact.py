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

from sleekxmpp.xmlstream.jid import JID

class Contact(object):
    """
    Defines a roster item
    """
    def __init__(self, jid):
        self._jid = JID(jid)         # a SleekXMPP jid object
        self._display_name = None
        self._subscription = 'none'
        self._ask = None
        self._status = ''
        self._presence = 'unavailable'
        self._priority = 0
        self._groups = []       # a list of groups the contact is in

    def set_ask(self, ask):
        self._ask = ask

    def set_subscription(self, sub):
        self._subscription = sub

    def get_jid(self):
        return self._jid

    def __repr__(self):
        return '%s' % self._jid

    def set_priority(self, priority):
        assert isinstance(priority, int)
        self._priority = priority

    def set_presence(self, pres):
        self._presence = pres

    def get_presence(self):
        return self._presence

    def set_name(self, name):
        self._display_name = name

    def get_name(self):
        return self._display_name
