# Copyright 2009 chickenzilla
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
Defines the global config instance, used to get or set (and save) values
from/to the config file
"""

DEFSECTION = "Poezio"

from configparser import RawConfigParser, NoOptionError, NoSectionError
from os import environ, makedirs, path
from shutil import copy2
from optparse import OptionParser

class Config(RawConfigParser):
    """
    load/save the config to a file
    """
    def __init__(self, file_name):
        self.file_name = file_name
        RawConfigParser.__init__(self, None)
        RawConfigParser.read(self, file_name)

    def get(self, option, default, section=DEFSECTION):
        """
        get a value from the config but return
        a default value if it is not found
        The type of default defines the type
        returned
        """
        try:
            if type(default) == int:
                res = self.getint(option, section)
            elif type(default) == float:
                res = self.getfloat(option, section)
            elif type(default) == bool:
                res = self.getboolean(option, section)
            else:
                res = self.getstr(option, section)
        except( NoOptionError, NoSectionError):
            return default
        return res

    def __get(self, option, section=DEFSECTION):
        """
        facility for RawConfigParser.get
        """
        return RawConfigParser.get(self, section, option)

    def getstr(self, option, section=DEFSECTION):
        """
        get a value and returns it as a string
        """
        return self.__get(option, section)

    def getint(self, option, section=DEFSECTION):
        """
        get a value and returns it as an int
        """
        try:
            return int(self.__get(option, section))
        except ValueError:
            return -1

    def getfloat(self, option, section=DEFSECTION):
        """
        get a value and returns it as a float
        """
        return float(self.__get(option, section))

    def getboolean(self, option, section=DEFSECTION):
        """
        get a value and returns it as a boolean
        """
        return RawConfigParser.getboolean(self, section, option)

    def write_in_file(self, section, option, value):
        """
        Our own way to save write the value in the file
        Just find the right section, and then find the
        right option, and edit it.

        TODO: make it write also new values in the file, not just what did already
        exist
        """
        df = open(self.file_name, 'r')
        lines_before = [line.strip() for line in df.readlines()]
        df.close()
        result_lines = []
        we_are_in_the_right_section = False
        for line in lines_before:
            if line.startswith('['): # check the section
                if line == '[%s]' % section:
                    we_are_in_the_right_section = True
                else:
                    we_are_in_the_right_section = False
            if (line.startswith('%s ' % (option,)) or
                line.startswith('%s=' % (option,))) and we_are_in_the_right_section:
                line = '%s = %s' % (option, value)
            result_lines.append(line)
        df = open(self.file_name, 'w')
        for line in result_lines:
            df.write('%s\n' % line)
        df.close()

    def set_and_save(self, option, value, section=DEFSECTION):
        """
        set the value in the configuration then save it
        to the file
        """
        try:
            RawConfigParser.set(self, section, option, value)
        except NoSectionError:
            # TODO, add this section if it didn't exist
            return
        self.write_in_file(section, option, value)

# creates the configuration directory if it doesn't exist
# and copy the default config in it
CONFIG_HOME = environ.get("XDG_CONFIG_HOME")
if not CONFIG_HOME:
    CONFIG_HOME = path.join(environ.get('HOME'), '/.config')
CONFIG_PATH = path.join(CONFIG_HOME, 'poezio')
try:
    makedirs(CONFIG_PATH)
except OSError:
    pass

if not path.isfile(CONFIG_PATH+'poezio.cfg'):
    copy2(path.join(path.dirname(__file__), '../data/default_config.cfg'), path.join(CONFIG_PATH, 'poezio.cfg'))

parser = OptionParser()
parser.add_option("-f", "--file", dest="filename", default=CONFIG_PATH+'poezio.cfg',
                  help="The config file you want to use", metavar="CONFIG_FILE")
parser.add_option("-d", "--debug", dest="debug",
                  help="The file where debug will be written", metavar="DEBUG_FILE")
(options, args) = parser.parse_args()
config = Config(options.filename)
