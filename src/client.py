#!/usr/bin/python
# -*- coding:utf-8 -*-
#
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

from connection import Connection
from multiuserchat import MultiUserChat
from config import config
from handler import Handler
from gui import Gui

class Client(object):
    """
    Main class
    Do what should be done automatically by the Client:
    join the rooms at startup, for example
    """
    def __init__(self):
        self.handler = Handler()

        self.resource = config.get('resource')
        self.server = config.get('server')
        self.connection = Connection(self.server, self.resource)
        self.connection.start()

        self.muc = MultiUserChat(self.connection.client)
        self.gui = Gui()
        self.rooms = config.get('rooms').split(':')

        import time
        time.sleep(1)           # remove
        for room in self.rooms:
            self.handler.emit('join-room', room = room.split('/')[0], nick=room.split('/')[1])
        while 1:
            self.connection.process()


def main():
    client = Client()

if __name__ == '__main__':
    main()
