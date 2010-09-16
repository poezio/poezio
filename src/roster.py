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

from contact import Contact

class Roster(object):
    """
    Defines the roster
    """
    def __init__(self):
        self._contacts = {}

    def addContactToList(self, contact):
        assert isinstance(contact, Contact)
        assert contact not in self._contacts
        self._contacts[contact.getJid().bare] = contact

    def getContacts(self):
        """
        returns all the contacts in a list
        TODO: sorted
        TODO: only some contacts (online only for example)
        """
        return [contact for contact in self._contacts.keys()]

    def __len__(self):
        return len(self._contacts)

    def getContact(self, bare_jid):
        if bare_jid not in self._contacts:
            return None
        return self._contacts[bare_jid]
