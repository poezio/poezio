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

from ConfigParser import RawConfigParser, NoOptionError
from os import environ, makedirs
from shutil import copy2

class Config(RawConfigParser):
    """
    load/save the config to a file
    """
    def __init__(self, file_name):
        self.defsection = "Poezio"
        self.file_name = file_name
        RawConfigParser.__init__(self, None)
        RawConfigParser.read(self, file_name)

    def get(self, option, default):
        """
        get a value from the config but return
        a default value if it is not found
        The type of default defines the type
        returned
        """
	try:
            if type(default) == int:
                res = self.getint(option)
            elif type(default) == float:
                res = self.getfloat(option)
            elif type(default) == bool:
                res = self.getboolean(option)
            else:
                res = self.getstr(option)
        except NoOptionError:
            return default
        return res

    def _get(self, option):
        return RawConfigParser.get(self, self.defsection, option)

    def getstr(self, option):
        return self._get(option)

    def getint(self, option):
        try:
            return int(self._get(option))
        except ValueError:
            return -1

    def getfloat(self, option):
        return float(self._get(option))

    def getboolean(self, option):
        return RawConfigParser.getboolean(self, self.defsection, option)

    def set(self, option, value):
        RawConfigParser.set(self, self.defsection, option, value)

    def save(self):
        f = open(self.file_name, "w")
        RawConfigParser.write(self, f)
	f.close()

    def set_and_save(self, option, value):
        self.set(option, value)
        self.save()

CONFIG_HOME = environ.get("XDG_CONFIG_HOME")
if not CONFIG_HOME:
    CONFIG_HOME = environ.get('HOME')+'/.config'
CONFIG_PATH = CONFIG_HOME + '/poezio/'

try:
    makedirs(CONFIG_PATH)
    copy2('../data/default_config.cfg', CONFIG_PATH+'poezio.cfg')
except:pass


config = Config(CONFIG_PATH+'poezio.cfg')
