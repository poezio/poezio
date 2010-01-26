#!/usr/bin/python
# -*- coding:utf-8 -*-
#
# Copyright 2009 chickenzilla
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

from ConfigParser import RawConfigParser

class Config(RawConfigParser):
    """
    load/save the config to a file
    """
    def __init__(self, file_name):
        self.defsection = "Poezio"
        self.file_name = file_name
        RawConfigParser.__init__(self, None)
        RawConfigParser.read(self, file_name)

    def get(self, option):
        return RawConfigParser.get(self, self.defsection, option)

    def rget(self, option):
	res = self.get(option)
	print res

    def getint(self, option):
        return int(self.get(option))

    def getfloat(self, option):
        return float(self.get(option))

    def getboolean(self, option):
        return RawConfigParser.getboolean(self, self.defsection, option)

    def set(self, option, value):
        RawConfigParser.set(self, self.defsection, option, value)

    def save(self):
        f = copen(self.filename, "w", "utf-8", "ignore")
        RawConfigParser.write(self, f)
	f.close()	

    def setAndSave(self, option, value):
        self.set(option, value)
        self.save()

config = Config('poezio.cfg')
