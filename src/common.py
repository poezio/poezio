# -*- coding: utf-8 -*-

# some functions coming from gajim sources (thanks)

## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    James Newton <redshodan AT gmail.com>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
##

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

# various useful functions

import base64
import os
import mimetypes
import hashlib
import subprocess
import curses
import traceback
import sys

def exception_handler(type_, value, trace):
    """
    on any traceback: exit ncurses and print the traceback
    then exit the program
    """
    curses.echo()
    curses.endwin()
    traceback.print_exception(type_, value, trace, None, sys.stderr)
    sys.exit(2)

def get_base64_from_file(path):
    if not os.path.isfile(path):
        return (None, None, "File does not exist")
    size = os.path.getsize(path)
    if size > 16384:
        return (None, None,"File is too big")
    fd = open(path, 'rb')
    data = fd.read()
    encoded = base64.encodestring(data)
    sha1 = hashlib.sha1(data).hexdigest()
    mime_type = mimetypes.guess_type(path)[0]
    return (encoded, mime_type, sha1)

def get_output_of_command(command):
    try:
        child_stdin, child_stdout = os.popen2(command)
    except ValueError:
        return None

    output = child_stdout.readlines()
    child_stdout.close()
    child_stdin.close()

    return output

def is_in_path(command, return_abs_path=False):
    """
    Return True if 'command' is found in one of the directories in the user's
    path. If 'return_abs_path' is True, return the absolute path of the first
    found command instead. Return False otherwise and on errors
    """
    for directory in os.getenv('PATH').split(os.pathsep):
        try:
            if command in os.listdir(directory):
                if return_abs_path:
                    return os.path.join(directory, command)
                else:
                    return True
        except OSError:
            # If the user has non directories in his path
            pass
    return False

distro_info = {
        'Arch Linux': '/etc/arch-release',
        'Aurox Linux': '/etc/aurox-release',
        'Conectiva Linux': '/etc/conectiva-release',
        'CRUX': '/usr/bin/crux',
        'Debian GNU/Linux': '/etc/debian_release',
        'Debian GNU/Linux': '/etc/debian_version',
        'Fedora Linux': '/etc/fedora-release',
        'Gentoo Linux': '/etc/gentoo-release',
        'Linux from Scratch': '/etc/lfs-release',
        'Mandrake Linux': '/etc/mandrake-release',
        'Slackware Linux': '/etc/slackware-release',
        'Slackware Linux': '/etc/slackware-version',
        'Solaris/Sparc': '/etc/release',
        'Source Mage': '/etc/sourcemage_version',
        'SUSE Linux': '/etc/SuSE-release',
        'Sun JDS': '/etc/sun-release',
        'PLD Linux': '/etc/pld-release',
        'Yellow Dog Linux': '/etc/yellowdog-release',
        # many distros use the /etc/redhat-release for compatibility
        # so Redhat is the last
        'Redhat Linux': '/etc/redhat-release'
}
def get_os_info():
    if os.name == 'nt':         # could not happen, but...
        ver = sys.getwindowsversion()
        ver_format = ver[3], ver[0], ver[1]
        win_version = {
                (1, 4, 0): '95',
                (1, 4, 10): '98',
                (1, 4, 90): 'ME',
                (2, 4, 0): 'NT',
                (2, 5, 0): '2000',
                (2, 5, 1): 'XP',
                (2, 5, 2): '2003',
                (2, 6, 0): 'Vista',
                (2, 6, 1): '7',
        }
        if ver_format in win_version:
            os_info = 'Windows' + ' ' + win_version[ver_format]
        else:
            os_info = 'Windows'
        return os_info
    elif os.name == 'posix':
        executable = 'lsb_release'
        params = ' --description --codename --release --short'
        full_path_to_executable = is_in_path(executable, return_abs_path = True)
        if full_path_to_executable:
            command = executable + params
            p = subprocess.Popen([command], shell=True, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, close_fds=True)
            p.wait()
            output = temp_failure_retry(p.stdout.readline).strip()
            # some distros put n/a in places, so remove those
            output = output.replace('n/a', '').replace('N/A', '')
            return output

        # lsb_release executable not available, so parse files
        for distro_name in distro_info:
            path_to_file = distro_info[distro_name]
            if os.path.exists(path_to_file):
                if os.access(path_to_file, os.X_OK):
                    # the file is executable (f.e. CRUX)
                    # yes, then run it and get the first line of output.
                    text = get_output_of_command(path_to_file)[0]
                else:
                    fd = open(path_to_file)
                    text = fd.readline().strip() # get only first line
                    fd.close()
                    if path_to_file.endswith('version'):
                        # sourcemage_version and slackware-version files
                        # have all the info we need (name and version of distro)
                        if not os.path.basename(path_to_file).startswith(
                        'sourcemage') or not\
                        os.path.basename(path_to_file).startswith('slackware'):
                            text = distro_name + ' ' + text
                    elif path_to_file.endswith('aurox-release') or \
                    path_to_file.endswith('arch-release'):
                        # file doesn't have version
                        text = distro_name
                    elif path_to_file.endswith('lfs-release'): # file just has version
                        text = distro_name + ' ' + text
                os_info = text.replace('\n', '')
                return os_info

        # our last chance, ask uname and strip it
        uname_output = get_output_of_command('uname -sr')
        if uname_output is not None:
            os_info = uname_output[0] # only first line
            return os_info
    os_info = 'N/A'
    return os_info

def datetime_tuple(timestamp):
    """
    Convert timestamp using strptime and the format: %Y%m%dT%H:%M:%S

    Because of various datetime formats are used the following exceptions
    are handled:
            - Optional milliseconds appened to the string are removed
            - Optional Z (that means UTC) appened to the string are removed
            - XEP-082 datetime strings have all '-' cahrs removed to meet
              the above format.
    """
    timestamp = timestamp.split('.')[0]
    timestamp = timestamp.replace('-', '')
    timestamp = timestamp.replace('z', '')
    timestamp = timestamp.replace('Z', '')
    from datetime import datetime
    return datetime.strptime(timestamp, '%Y%m%dT%H:%M:%S')
