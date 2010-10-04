# Copyright 2010 Le Coz Florent <louiz@louiz.org>
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
Defines the Connection class
"""

from gettext import (bindtextdomain, textdomain, bind_textdomain_codeset,
                     gettext as _)

import sys
import sleekxmpp

from config import config
from logger import logger
from handler import Handler
from common import jid_get_node, jid_get_domain, is_jid_the_same

class Connection(sleekxmpp.ClientXMPP):
    """
    Receives everything from Jabber and emits the
    appropriate signals
    """
    def __init__(self):
        if config.get('jid', ''):
            self.anon = False  # Field used to know if we are anonymous or not.
            # many features will be handled diferently
            # depending on this setting
            jid = config.get('jid', '')
            password = config.get('password', '')
        else:                   # anonymous auth
            self.anon = True
            jid = None
            password = None
        sleekxmpp.ClientXMPP.__init__(self, jid, password, ssl=True,
                                      resource=config.get('resource', 'poezio'))

        self.registerPlugin('xep_0045')

    def start(self):
        # TODO, try multiple servers
        if self.connect((config.get('server', 'anon.louiz.org'),
                      config.get('port', 5222))):
            self.process(threaded=True)
