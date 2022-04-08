"""
Defines the global config instance, used to get or set (and save) values
from/to the config file.

This module has the particularity that some imports and global variables
are delayed because it would mean doing an incomplete setup of the python
loggers.

TODO: get http://bugs.python.org/issue1410680 fixed, one day, in order
to remove our ugly custom I/O methods.
"""

import logging
import logging.config
import os
import sys

from configparser import RawConfigParser, NoOptionError, NoSectionError
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, cast, Any

from poezio import xdg
from slixmpp import JID, InvalidJID

log = logging.getLogger(__name__)  # type: logging.Logger

ConfigValue = Union[str, int, float, bool]

ConfigDict = Dict[str, Dict[str, ConfigValue]]

USE_DEFAULT_SECTION = '__DEFAULT SECTION PLACEHOLDER__'

CA_CERT_DEFAULT_PATHS = {
    '/etc/ssl/cert.pem',
    '/etc/ssl/certs/ca-certificates.crt',
    '/etc/ssl/certs/ca-bundle.crt',
    '/etc/pki/tls/certs/ca-bundle.crt',
    '/etc/ssl/certs/ca-certificates.crt',
    '/etc/ca-certificates/extracted/tls-ca-bundle.pem',
    '/etc/pki/ca-trust/extracted/openssl/ca-bundle.trust.crt',
}

DEFAULT_CONFIG: ConfigDict = {
    'Poezio': {
        'ack_message_receipts': True,
        'add_space_after_completion': True,
        'after_completion': ',',
        'alternative_nickname': '',
        'auto_reconnect': True,
        'autocolor_tab_names': False,
        'autorejoin_delay': '5',
        'autorejoin': False,
        'beep_on': 'highlight private invite disconnect',
        'ca_cert_path': ':'.join(CA_CERT_DEFAULT_PATHS),
        'certificate': '',
        'certfile': '',
        'ciphers': 'HIGH+kEDH:HIGH+kEECDH:HIGH:!PSK:!SRP:!3DES:!aNULL',
        'connection_check_interval': 300,
        'connection_timeout_delay': 30,
        'create_gaps': False,
        'custom_host': '',
        'custom_port': '',
        'default_nick': '',
        'default_muc_service': '',
        'device_id': '',
        'nick_color_aliases': True,
        'display_activity_notifications': False,
        'display_gaming_notifications': False,
        'display_mood_notifications': False,
        'display_tune_notifications': False,
        'display_user_color_in_join_part': True,
        'enable_avatars': True,
        'enable_carbons': True,
        'enable_css_parsing': True,
        'enable_user_activity': True,
        'enable_user_gaming': True,
        'enable_user_mood': True,
        'enable_user_nick': True,
        'enable_user_tune': True,
        'enable_vertical_tab_list': True,
        'enable_xhtml_im': True,
        'enable_smacks': False,
        'eval_password': '',
        'exec_remote': False,
        'extract_inline_images': True,
        'filter_info_messages': '',
        'force_encryption': True,
        'go_to_previous_tab_on_alt_number': False,
        'group_corrections': True,
        'hide_exit_join': -1,
        'hide_status_change': 120,
        'hide_user_list': False,
        'highlight_on': '',
        'ignore_certificate': False,
        'ignore_private': False,
        'image_use_half_blocks': False,
        'information_buffer_popup_on': 'error roster warning help info',
        'information_buffer_type_filter': '',
        'jid': '',
        'keyfile': '',
        'lang': 'en',
        'lazy_resize': True,
        'log_dir': '',
        'log_errors': True,
        'mam_sync': True,
        'mam_sync_limit': 2000,
        'max_lines_in_memory': 2048,
        'max_messages_in_memory': 2048,
        'max_nick_length': 25,
        'muc_history_length': 50,
        'notify_messages': True,
        'open_all_bookmarks': False,
        'password': '',
        'plugins_autoload': '',
        'plugins_conf_dir': '',
        'plugins_dir': '',
        'popup_time': 4,
        'private_auto_response': '',
        'remote_fifo_path': './',
        'request_message_receipts': True,
        'rooms': '',
        'roster_group_sort': 'name',
        'roster_show_offline': False,
        'roster_sort': 'jid:show',
        'save_status': True,
        'self_ping_interval': 0,
        'self_ping_timeout': 60,
        'send_chat_states': True,
        'send_initial_presence': True,
        'send_os_info': True,
        'send_poezio_info': True,
        'send_time': True,
        'separate_history': False,
        'server': 'anon.jeproteste.info',
        'show_composing_tabs': 'direct',
        'show_inactive_tabs': True,
        'show_jid_in_conversations': True,
        'show_muc_jid': False,
        'show_roster_jids': True,
        'show_roster_subscriptions': '',
        'show_s2s_errors': True,
        'show_tab_names': False,
        'show_tab_numbers': True,
        'show_timestamps': True,
        'show_useless_separator': True,
        'status': '',
        'status_message': '',
        'synchronise_open_rooms': True,
        'theme': 'default',
        'themes_dir': '',
        'tmp_image_dir': '',
        'unique_prefix_tab_names': False,
        'use_bookmarks_method': '',
        'use_log': True,
        'use_remote_bookmarks': True,
        'user_list_sort': 'desc',
        'use_tab_nicks': True,
        'vertical_tab_list_size': 20,
        'vertical_tab_list_sort': 'desc',
        'whitespace_interval': 300,
        'words': ''
    },
    'bindings': {
        'M-i': '^I'
    },
    'var': {
        'folded_roster_groups': '',
        'info_win_height': 2
    },
    'muc_colors': {}
}


class PoezioConfigParser(RawConfigParser):
    def optionxform(self, value) -> str:
        return str(value)


class Config:
    """
    load/save the config to a file
    """

    configparser: PoezioConfigParser
    file_name: Path
    default: ConfigDict
    default_section: str = 'Poezio'

    def __init__(self, file_name: Path, default: Optional[ConfigDict] = None) -> None:
        self.configparser = PoezioConfigParser()
        # make the options case sensitive
        self.file_name = file_name
        self.read_file()
        self.default = default or {}

    def optionxform(self, value):
        return str(value)

    def read_file(self):
        self.configparser.read(str(self.file_name), encoding='utf-8')
        # Check config integrity and fix it if it’s wrong
        # only when the object is the main config
        if self.__class__ is Config:
            for section in ('bindings', 'var'):
                if not self.has_section(section):
                    self.add_section(section)

    def get(self,
            option: str,
            default: Optional[ConfigValue] = None,
            section: str = USE_DEFAULT_SECTION) -> Any:
        """
        get a value from the config but return
        a default value if it is not found
        The type of default defines the type
        returned
        """
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        if default is None:
            default = self.default.get(section, {}).get(option, '')

        res: Optional[ConfigValue]
        try:
            if isinstance(default, bool):
                res = self.configparser.getboolean(section, option)
            elif isinstance(default, int):
                res = self.configparser.getint(section, option)
            elif isinstance(default, float):
                res = self.configparser.getfloat(section, option)
            else:
                res = self.configparser.get(section, option)
        except (NoOptionError, NoSectionError, ValueError, AttributeError):
            return default

        if res is None:
            return default
        return res

    def _get_default(self, option, section):
        if self.default:
            return self.default.get(section, {}).get(option)
        else:
            return ''

    def sections(self, *args, **kwargs) -> List[str]:
        return self.configparser.sections(*args, **kwargs)

    def options(self, *args, **kwargs):
        return self.configparser.options(*args, **kwargs)

    def has_option(self, *args, **kwargs) -> bool:
        return self.configparser.has_option(*args, **kwargs)

    def has_section(self, *args, **kwargs) -> bool:
        return self.configparser.has_section(*args, **kwargs)

    def add_section(self, *args, **kwargs):
        return self.configparser.add_section(*args, **kwargs)

    def remove_section(self, *args, **kwargs):
        return self.configparser.remove_section(*args, **kwargs)

    def get_by_tabname(self,
                       option,
                       tabname: JID,
                       fallback=True,
                       fallback_server=True,
                       default=''):
        """
        Try to get the value for the option. First we look in
        a section named `tabname`, if the option is not present
        in the section, we search for the global option if fallback is
        True. And we return `default` as a fallback as a last resort.
        """
        if self.default and (not default) and fallback:
            default = self.default.get(self.default_section, {}).get(option, '')
        if tabname in self.sections():
            if option in self.options(tabname):
                # We go the tab-specific option
                return self.get(option, default, tabname.full)
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
        try:
            server = JID(jid).server
        except InvalidJID:
            server = ''
        if server:
            server = '@' + server
            if server in self.sections() and option in self.options(server):
                return self.get(option, default, server)
        if fallback:
            return self.get(option, default)
        return default

    def __get(self, option, section=USE_DEFAULT_SECTION, **kwargs):
        """
        facility for RawConfigParser.get
        """
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        return self.configparser.get(section, option, **kwargs)

    def _get(self, section, conv, option, **kwargs):
        """
        Redirects RawConfigParser._get
        """
        return conv(self.__get(option, section, **kwargs))

    def getstr(self, option, section=USE_DEFAULT_SECTION) -> str:
        """
        get a value and returns it as a string
        """
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        try:
            return self.configparser.get(section, option)
        except (NoOptionError, NoSectionError, ValueError, AttributeError):
            return cast(str, self._get_default(option, section))

    def getint(self, option, section=USE_DEFAULT_SECTION) -> int:
        """
        get a value and returns it as an int
        """
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        try:
            return self.configparser.getint(section, option)
        except (NoOptionError, NoSectionError, ValueError, AttributeError):
            return cast(int, self._get_default(option, section))

    def getfloat(self, option, section=USE_DEFAULT_SECTION) -> float:
        """
        get a value and returns it as a float
        """
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        try:
            return self.configparser.getfloat(section, option)
        except (NoOptionError, NoSectionError, ValueError, AttributeError):
            return cast(float, self._get_default(option, section))

    def getbool(self, option, section=USE_DEFAULT_SECTION) -> bool:
        """
        get a value and returns it as a boolean
        """
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        try:
            return self.configparser.getboolean(section, option)
        except (NoOptionError, NoSectionError, ValueError, AttributeError):
            return cast(bool, self._get_default(option, section))

    def getlist(self, option, section=USE_DEFAULT_SECTION) -> List[str]:
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        return self.getstr(option, section).split(':')

    def write_in_file(self, section: str, option: str,
                      value: ConfigValue) -> bool:
        """
        Our own way to save write the value in the file
        Just find the right section, and then find the
        right option, and edit it.
        """
        result = self._parse_file()
        if not result:
            return False
        else:
            sections, result_lines = result

        if section not in sections:
            result_lines.append('[%s]' % section)
            result_lines.append('%s = %s' % (option, value))
        else:
            begin, end = sections[section]
            pos = find_line(result_lines, begin, end, option)

            if pos == -1:
                result_lines.insert(end, '%s = %s' % (option, value))
            else:
                result_lines[pos] = '%s = %s' % (option, value)

        return self._write_file(result_lines)

    def remove_in_file(self, section: str, option: str) -> bool:
        """
        Our own way to remove an option from the file.
        """
        result = self._parse_file()
        if not result:
            return False
        else:
            sections, result_lines = result

        if section not in sections:
            log.error(
                'Tried to remove the option %s from a non-'
                'existing section (%s)', option, section)
            return True
        else:
            begin, end = sections[section]
            pos = find_line(result_lines, begin, end, option)

            if pos == -1:
                log.error(
                    'Tried to remove a non-existing option %s'
                    ' from section %s', option, section)
                return True
            else:
                del result_lines[pos]

        return self._write_file(result_lines)

    def _write_file(self, lines: List[str]) -> bool:
        """
        Write the config file, write to a temporary file
        before copying it to the final destination
        """
        try:
            filename = self.file_name.parent / (
                '.%s.tmp' % self.file_name.name)
            with os.fdopen(
                    os.open(
                        str(filename),
                        os.O_WRONLY | os.O_CREAT,
                        0o600,
                    ),
                    'w',
                    encoding='utf-8') as fd:
                for line in lines:
                    fd.write('%s\n' % line)
            filename.replace(self.file_name)
        except:
            success = False
            log.error('Unable to save the config file.', exc_info=True)
        else:
            success = True
        return success

    def _parse_file(self) -> Optional[Tuple[Dict[str, List[int]], List[str]]]:
        """
        Parse the config file and return the list of sections with
        their start and end positions, and the lines in the file.

        Duplicate sections are preserved but ignored for the parsing.

        Returns an empty tuple if reading fails
        """
        if file_ok(self.file_name):
            try:
                with self.file_name.open('r', encoding='utf-8') as df:
                    lines_before: List[str] = [line.strip() for line in df]
            except OSError:
                log.error(
                    'Unable to read the config file %s',
                    self.file_name,
                    exc_info=True)
                return None
        else:
            lines_before = []

        sections: Dict[str, List[int]] = {}
        duplicate_section = False
        current_section = ''
        current_line = 0

        for line in lines_before:
            if line.startswith('['):
                if not duplicate_section and current_section:
                    sections[current_section][1] = current_line

                duplicate_section = False
                current_section = line[1:-1]

                if current_section in sections:
                    log.error('Error while reading the configuration file,'
                              ' skipping until next section')
                    duplicate_section = True
                else:
                    sections[current_section] = [current_line, current_line]

            current_line += 1
        if not duplicate_section and current_section:
            sections[current_section][1] = current_line

        return (sections, lines_before)

    def set_and_save(self, option: str, value: ConfigValue,
                     section=USE_DEFAULT_SECTION) -> Tuple[str, str]:
        """
        set the value in the configuration then save it
        to the file
        """
        # Special case for a 'toggle' value. We take the current value
        # and set the opposite. Warning if the no current value exists
        # or it is not a bool.
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        if isinstance(value, str) and value == "toggle":
            current = self.getbool(option, section)
            if isinstance(current, bool):
                value = str(not current).lower()
            else:
                if current.lower() == "false":
                    value = "true"
                elif current.lower() == "true":
                    value = "false"
                else:
                    return (
                        'Could not toggle option: %s.'
                        ' Current value is %s.' % (option, current or "empty"),
                        'Warning')
        value = str(value)
        if self.has_section(section):
            self.configparser.set(section, option, value)
        else:
            self.add_section(section)
            self.configparser.set(section, option, value)
        if not self.write_in_file(section, option, value):
            return ('Unable to write in the config file', 'Error')
        if isinstance(option, str) and 'password' in option and 'eval_password' not in option:
            value = '********'
        return ("%s=%s" % (option, value), 'Info')

    def remove_and_save(self, option: str,
                        section=USE_DEFAULT_SECTION) -> Tuple[str, str]:
        """
        Remove an option and then save it the config file
        """
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        if self.has_section(section):
            self.configparser.remove_option(section, option)
        if not self.remove_in_file(section, option):
            return ('Unable to save the config file', 'Error')
        return ('Option %s deleted' % option, 'Info')

    def silent_set(self, option: str, value: ConfigValue, section=USE_DEFAULT_SECTION):
        """
        Set a value, save, and return True on success and False on failure
        """
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        if self.has_section(section):
            self.configparser.set(section, option, str(value))
        else:
            self.add_section(section)
            self.configparser.set(section, option, str(value))
        return self.write_in_file(section, option, str(value))

    def set(self, option: str, value: ConfigValue, section=USE_DEFAULT_SECTION):
        """
        Set the value of an option temporarily
        """
        if section == USE_DEFAULT_SECTION:
            section = self.default_section
        try:
            self.configparser.set(section, option, str(value))
        except NoSectionError:
            pass

    def to_dict(self) -> Dict[str, Dict[str, Optional[ConfigValue]]]:
        """
        Returns a dict of the form {section: {option: value, option: value}, …}
        """
        res: Dict[str, Dict[str, Optional[ConfigValue]]] = {}
        for section in self.sections():
            res[section] = {}
            for option in self.options(section):
                res[section][option] = self.get(option, "", section)
        return res


def find_line(lines: List[str], start: int, end: int, option: str) -> int:
    """
    Get the number of the line containing the option in the
    relevant part of the config file.

    Returns -1 if the option isn’t found
    """
    current = start
    for line in lines[start:end]:
        if (line.startswith('%s ' % option)
                or line.startswith('%s=' % option)):
            return current
        current += 1
    return -1


def file_ok(filepath: Path) -> bool:
    """
    Returns True if the file exists and is readable and writeable,
    False otherwise.
    """
    val = filepath.exists()
    val &= os.access(str(filepath), os.R_OK | os.W_OK)
    return bool(val)


def get_image_cache() -> Optional[Path]:
    if not config.get('extract_inline_images'):
        return None
    tmp_dir = config.getstr('tmp_image_dir')
    if tmp_dir:
        return Path(tmp_dir)
    return xdg.CACHE_HOME / 'images'


def check_config():
    """
    Check the config file and print results
    """
    result = {'missing': [], 'changed': []}
    for option in DEFAULT_CONFIG['Poezio']:
        value = config.get(option)
        if value != DEFAULT_CONFIG['Poezio'][option]:
            result['changed'].append((option, value,
                                      DEFAULT_CONFIG['Poezio'][option]))
        else:
            value = config.get(option, default='')
            upper = value.upper()
            default = str(DEFAULT_CONFIG['Poezio'][option]).upper()
            if upper != default:
                result['missing'].append(option)

    result['changed'].sort(key=lambda x: x[0])
    result['missing'].sort()
    if result['changed']:
        print(
            '\033[1mOptions changed from the default configuration:\033[0m\n')
        for option, new_value, default in result['changed']:
            print(
                '    \033[1m%s\033[0m = \033[33m%s\033[0m (default: \033[32m%s\033[0m)'
                % (option, new_value, default))

    if result['missing']:
        print('\n\033[1mMissing options:\033[0m (the defaults are used)\n')
        for option in result['missing']:
            print('    \033[31m%s\033[0m' % option)


def create_global_config(filename):
    "Create the global config object, or crash"
    try:
        global config
        config = Config(filename, DEFAULT_CONFIG)
    except:
        import traceback
        sys.stderr.write('Poezio was unable to read or'
                         ' parse the config file.\n')
        traceback.print_exc(limit=0)
        sys.exit(1)


def setup_logging(debug_file=''):
    "Change the logging config according to the cmdline options and config"
    global LOG_DIR
    LOG_DIR = config.get('log_dir')
    LOG_DIR = Path(LOG_DIR).expanduser() if LOG_DIR else xdg.DATA_HOME / 'logs'
    from copy import deepcopy
    logging_config = deepcopy(LOGGING_CONFIG)
    if config.get('log_errors'):
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            # We can’t really log any error here, because logging isn’t setup yet.
            pass
        else:
            logging_config['root']['handlers'].append('error')
            logging_config['handlers']['error'] = {
                'level': 'ERROR',
                'class': 'logging.FileHandler',
                'filename': str(LOG_DIR / 'errors.log'),
                'formatter': 'simple',
            }
            logging.disable(logging.WARNING)

    if debug_file:
        logging_config['root']['handlers'].append('debug')
        logging_config['handlers']['debug'] = {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': debug_file,
            'formatter': 'simple',
        }
        logging.disable(logging.NOTSET)

    if logging_config['root']['handlers']:
        logging.config.dictConfig(logging_config)
    else:
        logging.disable(logging.ERROR)
        logging.basicConfig(level=logging.CRITICAL)


LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s %(levelname)s:%(module)s:%(message)s'
        }
    },
    'handlers': {},
    'root': {
        'handlers': [],
        'propagate': True,
        'level': 'DEBUG',
    }
}

# Global config object. Is setup for real in poezio.py
config = Config(Path('/dev/null'))

# the global log dir
LOG_DIR = Path()
