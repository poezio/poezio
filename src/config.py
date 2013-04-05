# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Defines the global config instance, used to get or set (and save) values
from/to the config file
"""

DEFSECTION = "Poezio"

from gettext import gettext as _

from configparser import RawConfigParser, NoOptionError, NoSectionError
from os import environ, makedirs, path
from shutil import copy2
from args import parse_args
from common import safeJID


class Config(RawConfigParser):
    """
    load/save the config to a file
    """
    def __init__(self, file_name):
        self.file_name = file_name
        RawConfigParser.__init__(self, None)
        # make the options case sensitive
        self.optionxform = str
        try:
            RawConfigParser.read(self, file_name, encoding='utf-8')
        except TypeError: # python < 3.2 sucks
            RawConfigParser.read(self, file_name)
        # Check config integrity and fix it if it’s wrong
        for section in ('bindings', 'var'):
            if not self.has_section(section):
                self.add_section(section)

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
        except (NoOptionError, NoSectionError):
            return default
        return res

    def getl(self, option, default, section=DEFSECTION):
        """
        get a value and return it lowercase
        """
        return self.get(option, default, section).lower()

    def get_by_tabname(self, option, default, tabname, fallback=True, fallback_server=True):
        """
        Try to get the value for the option. First we look in
        a section named `tabname`, if the option is not present
        in the section, we search for the global option if fallback is
        True. And we return `default` as a fallback as a last resort.
        """
        if tabname in self.sections():
            if option in self.options(tabname):
                # We go the tab-specific option
                return self.get(option, default, tabname)
        if fallback_server:
            return self.get_by_servname(tabname, option, default, fallback)
        if fallback:
            # We fallback to the global option
            return self.get(option, default)
        return default

    def get_by_servname(self, jid, option, default, fallback=True):
        """
        Try to get the value of an option for a server
        """
        server = safeJID(jid).server
        if server:
            server = '@' + server
            if server in self.sections() and option in self.options(server):
                return self.get(option, default, server)
        if fallback:
            return self.get(option, default)
        return default


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
        if path.exists(self.file_name):
            df = open(self.file_name, 'r', encoding='utf-8')
            lines_before = (line.strip() for line in df.readlines())
            df.close()
        else:
            lines_before = []
        result_lines = []
        we_are_in_the_right_section = False
        written = False
        section_found = False
        for line in lines_before:
            if line.startswith('['): # check the section
                if we_are_in_the_right_section and not written:
                    result_lines.append('%s = %s' % (option, value))
                    written = True
                if line == '[%s]' % section:
                    we_are_in_the_right_section = True
                    section_found = True
                else:
                    we_are_in_the_right_section = False
            if (line.startswith('%s ' % (option,)) or
                line.startswith('%s=' % (option,)) or
                line.startswith('%s = ' % (option,))) and we_are_in_the_right_section:
                line = '%s = %s' % (option, value)
                written = True
            result_lines.append(line)

        if not section_found:
            result_lines.append('[%s]' % section)
            result_lines.append('%s = %s' % (option, value))
        elif not written:
            result_lines.append('%s = %s' % (option, value))


        try:
            df = open(self.file_name, 'w', encoding='utf-8')
            for line in result_lines:
                df.write('%s\n' % line)
            df.close()
        except:
            success = False
        else:
            success = True
        return success

    def set_and_save(self, option, value, section=DEFSECTION):
        """
        set the value in the configuration then save it
        to the file
        """
        # Special case for a 'toggle' value. We take the current value
        # and set the opposite. Warning if the no current value exists
        # or it is not a bool.
        if value == "toggle":
            current = self.get(option, "", section)
            if current.lower() == "false":
                value = "true"
            elif current.lower() == "true":
                value = "false"
            else:
                return (_("Could not toggle option: %s. Current value is %s.") % (option, current or _("empty")), 'Warning')
        if self.has_section(section):
            RawConfigParser.set(self, section, option, value)
        else:
            self.add_section(section)
            RawConfigParser.set(self, section, option, value)
        if not self.write_in_file(section, option, value):
            return (_('Unable to write in the config file'), 'Error')
        return ("%s=%s" % (option, value), 'Info')

    def silent_set(self, option, value, section=DEFSECTION):
        """
        Set a value, save, and return True on success and False on failure
        """
        if self.has_section(section):
            RawConfigParser.set(self, section, option, value)
        else:
            self.add_section(section)
            RawConfigParser.set(self, section, option, value)
        return self.write_in_file(section, option, value)

    def set(self, option, value, section=DEFSECTION):
        """
        Set the value of an option temporarily
        """
        try:
            RawConfigParser.set(self, section, option, value)
        except NoSectionError:
            pass


firstrun = False

# creates the configuration directory if it doesn't exist
# and copy the default config in it
CONFIG_HOME = environ.get("XDG_CONFIG_HOME")
if not CONFIG_HOME:
    CONFIG_HOME = path.join(environ.get('HOME'), '.config')
CONFIG_PATH = path.join(CONFIG_HOME, 'poezio')
try:
    makedirs(CONFIG_PATH)
except OSError:
    pass

if not path.isfile(path.join(CONFIG_PATH, 'poezio.cfg')):
    copy2(path.join(path.dirname(__file__), '../data/default_config.cfg'), path.join(CONFIG_PATH, 'poezio.cfg'))
    firstrun = True

options = parse_args(CONFIG_PATH)
config = Config(options.filename)
if firstrun:
    config.set('firstrun', True)
