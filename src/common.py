# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
various useful functions
"""

from datetime import datetime, timedelta
import base64
import os
import mimetypes
import hashlib
import subprocess
import time
import string
import shlex

from config import config

ROOM_STATE_NONE = 11
ROOM_STATE_CURRENT = 10
ROOM_STATE_PRIVATE = 15
ROOM_STATE_MESSAGE = 12
ROOM_STATE_HL = 13

def get_base64_from_file(path):
    """
    Convert the content of a file to base64
    """
    if not os.path.isfile(path):
        return (None, None, "File does not exist")
    size = os.path.getsize(path)
    if size > 16384:
        return (None, None,"File is too big")
    fdes = open(path, 'rb')
    data = fdes.read()
    encoded = base64.encodestring(data)
    sha1 = hashlib.sha1(data).hexdigest()
    mime_type = mimetypes.guess_type(path)[0]
    return (encoded, mime_type, sha1)

def get_output_of_command(command):
    """
    Runs a command and returns its output
    """
    try:
        return subprocess.check_output(command.split()).decode('utf-8').split('\n')
    except subprocess.CalledProcessError:
        return None

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

DISTRO_INFO = {
        'Arch Linux': '/etc/arch-release',
        'Aurox Linux': '/etc/aurox-release',
        'Conectiva Linux': '/etc/conectiva-release',
        'CRUX': '/usr/bin/crux',
        'Debian GNU/Linux': '/etc/debian_version',
        'Fedora Linux': '/etc/fedora-release',
        'Gentoo Linux': '/etc/gentoo-release',
        'Linux from Scratch': '/etc/lfs-release',
        'Mandrake Linux': '/etc/mandrake-release',
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
    """
    Returns a detailed and well formated string containing
    informations about the operating system
    """
    if os.name == 'posix':
        executable = 'lsb_release'
        params = ' --description --codename --release --short'
        full_path_to_executable = is_in_path(executable, return_abs_path = True)
        if full_path_to_executable:
            command = executable + params
            process = subprocess.Popen([command], shell=True,
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       close_fds=True)
            process.wait()
            output = process.stdout.readline().decode('utf-8').strip()
            # some distros put n/a in places, so remove those
            output = output.replace('n/a', '').replace('N/A', '')
            return output

        # lsb_release executable not available, so parse files
        for distro_name in DISTRO_INFO:
            path_to_file = DISTRO_INFO[distro_name]
            if os.path.exists(path_to_file):
                if os.access(path_to_file, os.X_OK):
                    # the file is executable (f.e. CRUX)
                    # yes, then run it and get the first line of output.
                    text = get_output_of_command(path_to_file)[0]
                else:
                    fdes = open(path_to_file)
                    text = fdes.readline().strip() # get only first line
                    fdes.close()
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
                    elif path_to_file.endswith('lfs-release'):
                        # file just has version
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
    try:
        ret = datetime.strptime(timestamp, '%Y%m%dT%H:%M:%SZ')
    except ValueError:      # Support the deprecated format, XEP 0091 :(
        ret = datetime.strptime(timestamp, '%Y%m%dT%H:%M:%S')
    # convert UTC to local time, with DST etc.
    dst = timedelta(seconds=time.altzone)
    ret -= dst
    return ret

def shell_split(st):
    sh = shlex.shlex(st, posix=True)
    sh.commenters = ''
    sh.whitespace_split = True
    sh.quotes = '"'
    ret = list()
    try:
        w = sh.get_token()
        while w is not None:
            ret.append(w)
            w = sh.get_token()
        return ret
    except ValueError:
        return st.split(" ")

def replace_key_with_bound(key):
    bind = config.get(key, key, 'bindings')
    if not bind:
        bind = key
    return bind

def parse_str_to_secs(duration=''):
    """
    Parse a string of with a number of d, h, m, s
    >>> parse_str_to_secs("1d3m1h")
    90180
    """
    values = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    result = 0
    tmp = '0'
    for char in duration:
        if char in string.digits:
            tmp += char
        elif char in values:
            tmp_i = int(tmp)
            result += tmp_i * values[char]
            tmp = '0'
        else:
            result += int(tmp)
    if tmp != '0':
        result += int(tmp)
    return result

def parse_secs_to_str(duration=0):
    """
    Parse a number of seconds to a human-readable string.
    The string has the form XdXhXmXs. 0 units are removed.
    >>> parse_secs_to_str(3601)
    1h1s
    """
    secs, mins, hours, days = 0, 0, 0, 0
    result = ''
    secs = duration % 60
    mins = (duration % 3600) // 60
    hours = (duration % 86400) // 3600
    days = duration // 86400

    result += '%sd' % days if days else ''
    result += '%sh' % hours if hours else ''
    result += '%sm' % mins if mins else ''
    result += '%ss' % secs if secs else ''
    return result

def parse_command_args_to_alias(arg, strto):
    """
    Parse command parameters.
    Numbers can be from 0 to 9.
    >>> parse_command_args_to_alias('sdf koin', '%1 %0')
    "koin sdf"
    """
    if '%' not in strto:
        return strto + arg
    args = shell_split(arg)
    l = len(args)
    dest = ''
    var_num = False
    for i in strto:
        if i != '%':
            if not var_num:
                dest += i
            elif i in string.digits:
                if 0 <= int(i) < l:
                    dest += args[int(i)]
                var_num = False
        elif i == '%':
            if var_num:
                dest += '%'
                var_num = False
            else:
                var_num = True
    return dest
