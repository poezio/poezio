"""
The RosterInfoTab is the tab showing roster info, the list of contacts,
half of it is dedicated to showing the information buffer, and a small
rectangle shows the current contact info.

This module also includes functions to match users in the roster.
"""
import logging
log = logging.getLogger(__name__)

import base64
import curses
import difflib
import os
import ssl
from os import getenv, path
from functools import partial
from pathlib import Path

from poezio import common
from poezio import windows
from poezio.common import safeJID, shell_split
from poezio.config import config
from poezio.contact import Contact, Resource
from poezio.decorators import refresh_wrapper
from poezio.roster import RosterGroup, roster
from poezio.theming import get_theme, dump_tuple
from poezio.decorators import command_args_parser
from poezio.core.structs import Completion

from poezio.tabs import Tab


class RosterInfoTab(Tab):
    """
    A tab, splitted in two, containing the roster and infos
    """
    plugin_commands = {}
    plugin_keys = {}

    def __init__(self, core):
        Tab.__init__(self, core)
        self.name = "Roster"
        self.v_separator = windows.VerticalSeparator()
        self.information_win = windows.TextWin()
        self.core.information_buffer.add_window(self.information_win)
        self.roster_win = windows.RosterWin()
        self.contact_info_win = windows.ContactInfoWin()
        self.avatar_win = windows.ImageWin()
        self.default_help_message = windows.HelpText(
            "Enter commands with “/”. “o”: toggle offline show")
        self.input = self.default_help_message
        self.state = 'normal'
        self.key_func['^I'] = self.completion
        self.key_func["/"] = self.on_slash
        # disable most of the roster features when in anonymous mode
        if not self.core.xmpp.anon:
            self.key_func[' '] = self.on_space
            self.key_func["KEY_UP"] = self.move_cursor_up
            self.key_func["KEY_DOWN"] = self.move_cursor_down
            self.key_func["M-u"] = self.move_cursor_to_next_contact
            self.key_func["M-y"] = self.move_cursor_to_prev_contact
            self.key_func["M-U"] = self.move_cursor_to_next_group
            self.key_func["M-Y"] = self.move_cursor_to_prev_group
            self.key_func["M-[1;5B"] = self.move_cursor_to_next_group
            self.key_func["M-[1;5A"] = self.move_cursor_to_prev_group
            self.key_func["l"] = self.command_last_activity
            self.key_func["o"] = self.toggle_offline_show
            self.key_func["v"] = self.get_contact_version
            self.key_func["i"] = self.show_contact_info
            self.key_func["s"] = self.start_search
            self.key_func["S"] = self.start_search_slow
            self.key_func["n"] = self.change_contact_name
            self.register_command(
                'deny',
                self.command_deny,
                usage='[jid]',
                desc='Deny your presence to the provided JID (or the '
                'selected contact in your roster), who is asking'
                'you to be in his/here roster.',
                shortdesc='Deny a user your presence.',
                completion=self.completion_deny)
            self.register_command(
                'accept',
                self.command_accept,
                usage='[jid]',
                desc='Allow the provided JID (or the selected contact '
                'in your roster), to see your presence.',
                shortdesc='Allow a user your presence.',
                completion=self.completion_deny)
            self.register_command(
                'add',
                self.command_add,
                usage='<jid>',
                desc='Add the specified JID to your roster, ask them to'
                ' allow you to see his presence, and allow them to'
                ' see your presence.',
                shortdesc='Add a user to your roster.')
            self.register_command(
                'name',
                self.command_name,
                usage='<jid> [name]',
                shortdesc='Set the given JID\'s name.',
                completion=self.completion_name)
            self.register_command(
                'groupadd',
                self.command_groupadd,
                usage='[<jid> <group>]|<group>',
                desc='Add the given JID or selected line to the given group.',
                shortdesc='Add a user to a group',
                completion=self.completion_groupadd)
            self.register_command(
                'groupmove',
                self.command_groupmove,
                usage='<jid> <old group> <new group>',
                desc='Move the given JID from the old group to the new group.',
                shortdesc='Move a user to another group.',
                completion=self.completion_groupmove)
            self.register_command(
                'groupremove',
                self.command_groupremove,
                usage='<jid> <group>',
                desc='Remove the given JID from the given group.',
                shortdesc='Remove a user from a group.',
                completion=self.completion_groupremove)
            self.register_command(
                'remove',
                self.command_remove,
                usage='[jid]',
                desc='Remove the specified JID from your roster. This '
                'will unsubscribe you from its presence, cancel '
                'its subscription to yours, and remove the item '
                'from your roster.',
                shortdesc='Remove a user from your roster.',
                completion=self.completion_remove)
            self.register_command(
                'export',
                self.command_export,
                usage='[/path/to/file]',
                desc='Export your contacts into /path/to/file if '
                'specified, or $HOME/poezio_contacts if not.',
                shortdesc='Export your roster to a file.',
                completion=partial(self.completion_file, 1))
            self.register_command(
                'import',
                self.command_import,
                usage='[/path/to/file]',
                desc='Import your contacts from /path/to/file if '
                'specified, or $HOME/poezio_contacts if not.',
                shortdesc='Import your roster from a file.',
                completion=partial(self.completion_file, 1))
            self.register_command(
                'password',
                self.command_password,
                usage='<password>',
                shortdesc='Change your password')

        self.register_command(
            'reconnect',
            self.command_reconnect,
            desc='Disconnect from the remote server if you are '
            'currently connected and then connect to it again.',
            shortdesc='Disconnect and reconnect to the server.')
        self.register_command(
            'disconnect',
            self.command_disconnect,
            desc='Disconnect from the remote server.',
            shortdesc='Disconnect from the server.')
        self.register_command(
            'clear', self.command_clear, shortdesc='Clear the info buffer.')
        self.register_command(
            'last_activity',
            self.command_last_activity,
            usage='<jid>',
            desc='Informs you of the last activity of a JID.',
            shortdesc='Get the activity of someone.',
            completion=self.core.completion.last_activity)

        self.resize()
        self.update_commands()
        self.update_keys()

    def check_blocking(self, features):
        if 'urn:xmpp:blocking' in features and not self.core.xmpp.anon:
            self.register_command(
                'block',
                self.command_block,
                usage='[jid]',
                shortdesc='Prevent a JID from talking to you.',
                completion=self.completion_block)
            self.register_command(
                'unblock',
                self.command_unblock,
                usage='[jid]',
                shortdesc='Allow a JID to talk to you.',
                completion=self.completion_unblock)
            self.register_command(
                'list_blocks',
                self.command_list_blocks,
                shortdesc='Show the blocked contacts.')
            self.core.xmpp.del_event_handler('session_start',
                                             self.check_blocking)
            self.core.xmpp.add_event_handler('blocked_message',
                                             self.on_blocked_message)

    def check_saslexternal(self, features):
        if 'urn:xmpp:saslcert:1' in features and not self.core.xmpp.anon:
            self.register_command(
                'certs',
                self.command_certs,
                desc='List the fingerprints of certificates'
                ' which can connect to your account.',
                shortdesc='List allowed client certs.')
            self.register_command(
                'cert_add',
                self.command_cert_add,
                desc='Add a client certificate to the authorized ones. '
                'It must have an unique name and be contained in '
                'a PEM file. [management] is a boolean indicating'
                ' if a client connected using this certificate can'
                ' manage the certificates itself.',
                shortdesc='Add a client certificate.',
                usage='<name> <certificate path> [management]',
                completion=self.completion_cert_add)
            self.register_command(
                'cert_disable',
                self.command_cert_disable,
                desc='Remove a certificate from the list '
                'of allowed ones. Clients currently '
                'using this certificate will not be '
                'forcefully disconnected.',
                shortdesc='Disable a certificate',
                usage='<name>')
            self.register_command(
                'cert_revoke',
                self.command_cert_revoke,
                desc='Remove a certificate from the list '
                'of allowed ones. Clients currently '
                'using this certificate will be '
                'forcefully disconnected.',
                shortdesc='Revoke a certificate',
                usage='<name>')
            self.register_command(
                'cert_fetch',
                self.command_cert_fetch,
                desc='Retrieve a certificate with its '
                'name. It will be stored in <path>.',
                shortdesc='Fetch a certificate',
                usage='<name> <path>',
                completion=self.completion_cert_fetch)

    @property
    def selected_row(self):
        return self.roster_win.get_selected_row()

    @command_args_parser.ignored
    def command_certs(self):
        """
        /certs
        """

        def cb(iq):
            if iq['type'] == 'error':
                self.core.information(
                    'Unable to retrieve the certificate list.', 'Error')
                return
            certs = []
            for item in iq['sasl_certs']['items']:
                users = '\n'.join(item['users'])
                certs.append((item['name'], users))

            if not certs:
                return self.core.information('No certificates found', 'Info')
            msg = 'Certificates:\n'
            msg += '\n'.join(
                (('  %s%s' % (item[0] + (': ' if item[1] else ''), item[1]))
                 for item in certs))
            self.core.information(msg, 'Info')

        self.core.xmpp.plugin['xep_0257'].get_certs(callback=cb, timeout=3)

    @command_args_parser.quoted(2, 1)
    def command_cert_add(self, args):
        """
        /cert_add <name> <certfile> [cert-management]
        """
        if not args or len(args) < 2:
            return self.core.command.help('cert_add')

        def cb(iq):
            if iq['type'] == 'error':
                self.core.information('Unable to add the certificate.',
                                      'Error')
            else:
                self.core.information('Certificate added.', 'Info')

        name = args[0]

        try:
            with open(args[1]) as fd:
                crt = fd.read()
            crt = crt.replace(ssl.PEM_FOOTER, '').replace(
                ssl.PEM_HEADER, '').replace(' ', '').replace('\n', '')
        except Exception as e:
            self.core.information('Unable to read the certificate: %s' % e,
                                  'Error')
            return

        if len(args) > 2:
            management = args[2]
            if management:
                management = management.lower()
                if management not in ('false', '0'):
                    management = True
                else:
                    management = False
            else:
                management = False
        else:
            management = True

        self.core.xmpp.plugin['xep_0257'].add_cert(
            name, crt, callback=cb, allow_management=management)

    def completion_cert_add(self, the_input):
        """
        completion for /cert_add <name> <path> [management]
        """
        n = the_input.get_argument_position()
        log.debug('%s %s %s', the_input.text, n, the_input.pos)
        if n == 1:
            return
        elif n == 2:
            return self.completion_file(2, the_input)
        elif n == 3:
            return Completion(the_input.new_completion, ['true', 'false'], n)

    @command_args_parser.quoted(1)
    def command_cert_disable(self, args):
        """
        /cert_disable <name>
        """
        if not args:
            return self.core.command.help('cert_disable')

        def cb(iq):
            if iq['type'] == 'error':
                self.core.information('Unable to disable the certificate.',
                                      'Error')
            else:
                self.core.information('Certificate disabled.', 'Info')

        name = args[0]

        self.core.xmpp.plugin['xep_0257'].disable_cert(name, callback=cb)

    @command_args_parser.quoted(1)
    def command_cert_revoke(self, args):
        """
        /cert_revoke <name>
        """
        if not args:
            return self.core.command.help('cert_revoke')

        def cb(iq):
            if iq['type'] == 'error':
                self.core.information('Unable to revoke the certificate.',
                                      'Error')
            else:
                self.core.information('Certificate revoked.', 'Info')

        name = args[0]

        self.core.xmpp.plugin['xep_0257'].revoke_cert(name, callback=cb)

    @command_args_parser.quoted(2)
    def command_cert_fetch(self, args):
        """
        /cert_fetch <name> <path>
        """
        if not args or len(args) < 2:
            return self.core.command.help('cert_fetch')

        def cb(iq):
            if iq['type'] == 'error':
                self.core.information('Unable to fetch the certificate.',
                                      'Error')
                return

            cert = None
            for item in iq['sasl_certs']['items']:
                if item['name'] == name:
                    cert = base64.b64decode(item['x509cert'])
                    break

            if not cert:
                return self.core.information('Certificate not found.', 'Info')

            cert = ssl.DER_cert_to_PEM_cert(cert)
            with open(path, 'w') as fd:
                fd.write(cert)

            self.core.information('File stored at %s' % path, 'Info')

        name = args[0]
        path = args[1]

        self.core.xmpp.plugin['xep_0257'].get_certs(callback=cb)

    def completion_cert_fetch(self, the_input):
        """
        completion for /cert_fetch <name> <path>
        """
        n = the_input.get_argument_position()
        log.debug('%s %s %s', the_input.text, n, the_input.pos)
        if n == 1:
            return
        elif n == 2:
            return self.completion_file(2, the_input)

    def on_blocked_message(self, message):
        """
        When we try to send a message to a blocked contact
        """
        tab = self.core.get_conversation_by_jid(message['from'], False)
        if not tab:
            log.debug('Received message from nonexistent tab: %s',
                      message['from'])
        message = '\x19%(info_col)s}Cannot send message to %(jid)s: contact blocked' % {
            'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
            'jid': message['from'],
        }
        tab.add_message(message)

    @command_args_parser.quoted(0, 1)
    def command_block(self, args):
        """
        /block [jid]
        """
        item = self.roster_win.selected_row
        if args:
            jid = safeJID(args[0])
        elif isinstance(item, Contact):
            jid = item.bare_jid
        elif isinstance(item, Resource):
            jid = item.jid.bare

        def callback(iq):
            if iq['type'] == 'error':
                return self.core.information('Could not block %s.' % jid,
                                             'Error')
            elif iq['type'] == 'result':
                return self.core.information('Blocked %s.' % jid, 'Info')

        self.core.xmpp.plugin['xep_0191'].block(jid, callback=callback)

    def completion_block(self, the_input):
        """
        Completion for /block
        """
        if the_input.get_argument_position() == 1:
            jids = roster.jids()
            return Completion(
                the_input.new_completion, jids, 1, '', quotify=False)

    @command_args_parser.quoted(0, 1)
    def command_unblock(self, args):
        """
        /unblock [jid]
        """

        def callback(iq):
            if iq['type'] == 'error':
                return self.core.information('Could not unblock the contact.',
                                             'Error')
            elif iq['type'] == 'result':
                return self.core.information('Contact unblocked.', 'Info')

        item = self.roster_win.selected_row
        if args:
            jid = safeJID(args[0])
        elif isinstance(item, Contact):
            jid = item.bare_jid
        elif isinstance(item, Resource):
            jid = item.jid.bare
        self.core.xmpp.plugin['xep_0191'].unblock(jid, callback=callback)

    def completion_unblock(self, the_input):
        """
        Completion for /unblock
        """

        def on_result(iq):
            if iq['type'] == 'error':
                return
            l = sorted(str(item) for item in iq['blocklist']['items'])
            return Completion(the_input.new_completion, l, 1, quotify=False)

        if the_input.get_argument_position():
            self.core.xmpp.plugin['xep_0191'].get_blocked(callback=on_result)
        return True

    @command_args_parser.ignored
    def command_list_blocks(self):
        """
        /list_blocks
        """

        def callback(iq):
            if iq['type'] == 'error':
                return self.core.information(
                    'Could not retrieve the blocklist.', 'Error')
            s = 'List of blocked JIDs:\n'
            items = (str(item) for item in iq['blocklist']['items'])
            jids = '\n'.join(items)
            if jids:
                s += jids
            else:
                s = 'No blocked JIDs.'
            self.core.information(s, 'Info')

        self.core.xmpp.plugin['xep_0191'].get_blocked(callback=callback)

    @command_args_parser.ignored
    def command_reconnect(self):
        """
        /reconnect
        """
        if self.core.xmpp.is_connected():
            self.core.disconnect(reconnect=True)
        else:
            self.core.xmpp.connect()

    @command_args_parser.ignored
    def command_disconnect(self):
        """
        /disconnect
        """
        self.core.disconnect()

    @command_args_parser.quoted(0, 1)
    def command_last_activity(self, args):
        """
        /activity [jid]
        """
        item = self.roster_win.selected_row
        if args:
            jid = args[0]
        elif isinstance(item, Contact):
            jid = item.bare_jid
        elif isinstance(item, Resource):
            jid = item.jid
        else:
            self.core.information('No JID selected.', 'Error')
            return
        self.core.command.last_activity(jid)

    def resize(self):
        self.need_resize = False
        if self.size.tab_degrade_x:
            display_info = False
            roster_width = self.width
        else:
            display_info = True
            roster_width = self.width // 2
            if self.size.tab_degrade_y:
                display_contact_win = False
                contact_win_h = 0
            else:
                display_contact_win = True
                contact_win_h = 8
        if self.size.tab_degrade_y:
            tab_win_height = 0
        else:
            tab_win_height = Tab.tab_win_height()

        info_width = self.width - roster_width - 1
        if display_info:
            self.v_separator.resize(self.height - 1 - tab_win_height, 1, 0,
                                    roster_width)
            self.information_win.resize(
                self.height - 1 - tab_win_height - contact_win_h, info_width,
                0, roster_width + 1, self.core.information_buffer)
            if display_contact_win:
                y = self.height - tab_win_height - contact_win_h - 1
                avatar_width = contact_win_h * 2
                self.contact_info_win.resize(contact_win_h,
                                             info_width - avatar_width, y,
                                             roster_width + 1)
                self.avatar_win.resize(contact_win_h, avatar_width, y,
                                       self.width - avatar_width)
        self.roster_win.resize(self.height - 1 - Tab.tab_win_height(),
                               roster_width, 0, 0)
        self.input.resize(1, self.width, self.height - 1, 0)
        self.default_help_message.resize(1, self.width, self.height - 1, 0)

    def completion(self):
        # Check if we are entering a command (with the '/' key)
        if isinstance(self.input, windows.Input) and\
                not self.input.help_message:
            self.complete_commands(self.input)

    def completion_file(self, complete_number, the_input):
        """
        Generic quoted completion for files/paths
        (use functools.partial to use directly as a completion
        for a command)
        """
        text = the_input.get_text()
        args = shell_split(text)
        n = the_input.get_argument_position()
        if n == complete_number:
            if args[n - 1] == '' or len(args) < n + 1:
                home = os.getenv('HOME') or '/'
                return Completion(
                    the_input.new_completion, [home, '/tmp'], n, quotify=True)
            path_ = Path(args[n])
            if path_.is_dir():
                dir_ = path_
                base = ''
            else:
                dir_ = path_.parent
                base = path_.name
            try:
                names = list(dir_.iterdir())
            except OSError:
                names = []
            names_filtered = [
                name for name in names if str(name).startswith(base)
            ]
            if names_filtered:
                names = names_filtered
            if not names:
                names = [path_]
            end_list = []
            for name in names:
                if not str(name).startswith('.'):
                    value = dir_ / name
                    end_list.append(str(value))

            return Completion(
                the_input.new_completion, end_list, n, quotify=True)

    @command_args_parser.ignored
    def command_clear(self):
        """
        /clear
        """
        self.core.information_buffer.messages = []
        self.information_win.rebuild_everything(self.core.information_buffer)
        self.core.information_win.rebuild_everything(
            self.core.information_buffer)
        self.refresh()

    @command_args_parser.quoted(1)
    def command_password(self, args):
        """
        /password <password>
        """

        def callback(iq):
            if iq['type'] == 'result':
                self.core.information('Password updated', 'Account')
                if config.get('password'):
                    config.silent_set('password', args[0])
            else:
                self.core.information('Unable to change the password',
                                      'Account')

        self.core.xmpp.plugin['xep_0077'].change_password(
            args[0], callback=callback)

    @command_args_parser.quoted(0, 1)
    def command_deny(self, args):
        """
        /deny [jid]
        Denies a JID from our roster
        """
        if not args:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            else:
                self.core.information('No subscription to deny', 'Warning')
                return
        else:
            jid = safeJID(args[0]).bare
            if jid not in [jid for jid in roster.jids()]:
                self.core.information('No subscription to deny', 'Warning')
                return

        contact = roster[jid]
        if contact:
            contact.unauthorize()
            self.core.information('Subscription to %s was revoked' % jid,
                                  'Roster')

    @command_args_parser.quoted(1)
    def command_add(self, args):
        """
        Add the specified JID to the roster, and automatically
        accept the reverse subscription
        """
        if args is None:
            self.core.information('No JID specified', 'Error')
            return
        jid = safeJID(safeJID(args[0]).bare)
        if not str(jid):
            self.core.information(
                'The provided JID (%s) is not valid' % (args[0], ), 'Error')
            return
        if jid in roster and roster[jid].subscription in ('to', 'both'):
            return self.core.information('Already subscribed.', 'Roster')
        roster.add(jid)
        roster.modified()
        self.core.information('%s was added to the roster' % jid, 'Roster')

    @command_args_parser.quoted(1, 1)
    def command_name(self, args):
        """
        Set a name for the specified JID in your roster
        """

        def callback(iq):
            if not iq:
                self.core.information('The name could not be set.', 'Error')
                log.debug('Error in /name:\n%s', iq)

        if args is None:
            return self.core.command.help('name')
        jid = safeJID(args[0]).bare
        name = args[1] if len(args) == 2 else ''

        contact = roster[jid]
        if contact is None:
            self.core.information('No such JID in roster', 'Error')
            return

        groups = set(contact.groups)
        if 'none' in groups:
            groups.remove('none')
        subscription = contact.subscription
        self.core.xmpp.update_roster(
            jid,
            name=name,
            groups=groups,
            subscription=subscription,
            callback=callback)

    @command_args_parser.quoted(1, 1)
    def command_groupadd(self, args):
        """
        Add the specified JID to the specified group
        """
        if args is None:
            return self.core.command.help('groupadd')
        if len(args) == 1:
            group = args[0]
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            elif isinstance(item, Resource):
                jid = item.jid
            else:
                return self.core.command.help('groupadd')
        else:
            jid = safeJID(args[0]).bare
            group = args[1]

        contact = roster[jid]
        if contact is None:
            self.core.information('No such JID in roster', 'Error')
            return

        new_groups = set(contact.groups)
        if group in new_groups:
            self.core.information('JID already in group', 'Error')
            return

        roster.modified()
        new_groups.add(group)
        try:
            new_groups.remove('none')
        except KeyError:
            pass

        name = contact.name
        subscription = contact.subscription

        def callback(iq):
            if iq:
                roster.update_contact_groups(jid)
            else:
                self.core.information('The group could not be set.', 'Error')
                log.debug('Error in groupadd:\n%s', iq)

        self.core.xmpp.update_roster(
            jid,
            name=name,
            groups=new_groups,
            subscription=subscription,
            callback=callback)

    @command_args_parser.quoted(3)
    def command_groupmove(self, args):
        """
        Remove the specified JID from the first specified group and add it to the second one
        """
        if args is None:
            return self.core.command.help('groupmove')
        jid = safeJID(args[0]).bare
        group_from = args[1]
        group_to = args[2]

        contact = roster[jid]
        if not contact:
            self.core.information('No such JID in roster', 'Error')
            return

        new_groups = set(contact.groups)
        if 'none' in new_groups:
            new_groups.remove('none')

        if group_to == 'none' or group_from == 'none':
            self.core.information('"none" is not a group.', 'Error')
            return

        if group_from not in new_groups:
            self.core.information('JID not in first group', 'Error')
            return

        if group_to in new_groups:
            self.core.information('JID already in second group', 'Error')
            return

        if group_to == group_from:
            self.core.information('The groups are the same.', 'Error')
            return

        roster.modified()
        new_groups.add(group_to)
        if 'none' in new_groups:
            new_groups.remove('none')

        new_groups.remove(group_from)
        name = contact.name
        subscription = contact.subscription

        def callback(iq):
            if iq:
                roster.update_contact_groups(contact)
            else:
                self.core.information('The group could not be set', 'Error')
                log.debug('Error in groupmove:\n%s', iq)

        self.core.xmpp.update_roster(
            jid,
            name=name,
            groups=new_groups,
            subscription=subscription,
            callback=callback)

    @command_args_parser.quoted(2)
    def command_groupremove(self, args):
        """
        Remove the specified JID from the specified group
        """
        if args is None:
            return self.core.command.help('groupremove')

        jid = safeJID(args[0]).bare
        group = args[1]

        contact = roster[jid]
        if contact is None:
            self.core.information('No such JID in roster', 'Error')
            return

        new_groups = set(contact.groups)
        try:
            new_groups.remove('none')
        except KeyError:
            pass
        if group not in new_groups:
            self.core.information('JID not in group', 'Error')
            return

        roster.modified()

        new_groups.remove(group)
        name = contact.name
        subscription = contact.subscription

        def callback(iq):
            if iq:
                roster.update_contact_groups(jid)
            else:
                self.core.information('The group could not be set')
                log.debug('Error in groupremove:\n%s', iq)

        self.core.xmpp.update_roster(
            jid,
            name=name,
            groups=new_groups,
            subscription=subscription,
            callback=callback)

    @command_args_parser.quoted(0, 1)
    def command_remove(self, args):
        """
        Remove the specified JID from the roster. i.e.: unsubscribe
        from its presence, and cancel its subscription to our.
        """
        if args:
            jid = safeJID(args[0]).bare
        else:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            else:
                self.core.information('No roster item to remove', 'Error')
                return
        roster.remove(jid)
        del roster[jid]

    @command_args_parser.quoted(0, 1)
    def command_import(self, args):
        """
        Import the contacts
        """
        if args:
            if args[0].startswith('/'):
                filepath = args[0]
            else:
                filepath = path.join(getenv('HOME'), args[0])
        else:
            filepath = path.join(getenv('HOME'), 'poezio_contacts')
        if not path.isfile(filepath):
            self.core.information('The file %s does not exist' % filepath,
                                  'Error')
            return
        try:
            handle = open(filepath, 'r', encoding='utf-8')
            lines = handle.readlines()
            handle.close()
        except IOError:
            self.core.information('Could not open %s' % filepath, 'Error')
            log.error('Unable to correct a message', exc_info=True)
            return
        for jid in lines:
            self.command_add(jid.lstrip('\n'))
        self.core.information('Contacts imported from %s' % filepath, 'Info')

    @command_args_parser.quoted(0, 1)
    def command_export(self, args):
        """
        Export the contacts
        """
        if args:
            if args[0].startswith('/'):
                filepath = args[0]
            else:
                filepath = path.join(getenv('HOME'), args[0])
        else:
            filepath = path.join(getenv('HOME'), 'poezio_contacts')
        if path.isfile(filepath):
            self.core.information('The file already exists', 'Error')
            return
        elif not path.isdir(path.dirname(filepath)):
            self.core.information('Parent directory not found', 'Error')
            return
        if roster.export(filepath):
            self.core.information('Contacts exported to %s' % filepath, 'Info')
        else:
            self.core.information('Failed to export contacts to %s' % filepath,
                                  'Info')

    def completion_remove(self, the_input):
        """
        Completion for /remove
        """
        jids = [jid for jid in roster.jids()]
        return Completion(the_input.auto_completion, jids, '', quotify=False)

    def completion_name(self, the_input):
        """Completion for /name"""
        n = the_input.get_argument_position()
        if n == 1:
            jids = [jid for jid in roster.jids()]
            return Completion(the_input.new_completion, jids, n, quotify=True)
        return False

    def completion_groupadd(self, the_input):
        n = the_input.get_argument_position()
        if n == 1:
            jids = sorted(jid for jid in roster.jids())
            return Completion(
                the_input.new_completion, jids, n, '', quotify=True)
        elif n == 2:
            groups = sorted(
                group for group in roster.groups if group != 'none')
            return Completion(
                the_input.new_completion, groups, n, '', quotify=True)
        return False

    def completion_groupmove(self, the_input):
        args = shell_split(the_input.text)
        n = the_input.get_argument_position()
        if n == 1:
            jids = sorted(jid for jid in roster.jids())
            return Completion(
                the_input.new_completion, jids, n, '', quotify=True)
        elif n == 2:
            contact = roster[args[1]]
            if not contact:
                return False
            groups = list(contact.groups)
            if 'none' in groups:
                groups.remove('none')
            return Completion(
                the_input.new_completion, groups, n, '', quotify=True)
        elif n == 3:
            groups = sorted(group for group in roster.groups)
            return Completion(
                the_input.new_completion, groups, n, '', quotify=True)
        return False

    def completion_groupremove(self, the_input):
        args = shell_split(the_input.text)
        n = the_input.get_argument_position()
        if n == 1:
            jids = sorted(jid for jid in roster.jids())
            return Completion(
                the_input.new_completion, jids, n, '', quotify=True)
        elif n == 2:
            contact = roster[args[1]]
            if contact is None:
                return False
            groups = sorted(contact.groups)
            try:
                groups.remove('none')
            except ValueError:
                pass
            return Completion(
                the_input.new_completion, groups, n, '', quotify=True)
        return False

    def completion_deny(self, the_input):
        """
        Complete the first argument from the list of the
        contact with ask=='subscribe'
        """
        jids = sorted(
            str(contact.bare_jid) for contact in roster.contacts.values()
            if contact.pending_in)
        return Completion(the_input.new_completion, jids, 1, '', quotify=False)

    @command_args_parser.quoted(0, 1)
    def command_accept(self, args):
        """
        Accept a JID from in roster. Authorize it AND subscribe to it
        """
        if not args:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            else:
                self.core.information('No subscription to accept', 'Warning')
                return
        else:
            jid = safeJID(args[0]).bare
        nodepart = safeJID(jid).user
        jid = safeJID(jid)
        # crappy transports putting resources inside the node part
        if '\\2f' in nodepart:
            jid.user = nodepart.split('\\2f')[0]
        contact = roster[jid]
        if contact is None:
            return
        contact.pending_in = False
        roster.modified()
        self.core.xmpp.send_presence(pto=jid, ptype='subscribed')
        self.core.xmpp.client_roster.send_last_presence()
        if contact.subscription in ('from',
                                    'none') and not contact.pending_out:
            self.core.xmpp.send_presence(
                pto=jid, ptype='subscribe', pnick=self.core.own_nick)

        self.core.information('%s is now authorized' % jid, 'Roster')

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)

        display_info = not self.size.tab_degrade_x
        display_contact_win = not self.size.tab_degrade_y

        self.roster_win.refresh(roster)
        if display_info:
            self.v_separator.refresh()
            self.information_win.refresh()
            if display_contact_win:
                row = self.roster_win.get_selected_row()
                self.contact_info_win.refresh(row)
                if isinstance(row, Contact):
                    self.avatar_win.refresh(row.avatar)
                else:
                    self.avatar_win.refresh(None)
        self.refresh_tab_win()
        self.input.refresh()

    def on_input(self, key, raw):
        if key == '^M':
            selected_row = self.roster_win.get_selected_row()
        res = self.input.do_command(key, raw=raw)
        if res and not isinstance(self.input, windows.Input):
            return True
        elif res:
            return False
        if key == '^M':
            self.core.on_roster_enter_key(selected_row)
            return selected_row
        elif not raw and key in self.key_func:
            return self.key_func[key]()

    @refresh_wrapper.conditional
    def toggle_offline_show(self):
        """
        Show or hide offline contacts
        """
        option = 'roster_show_offline'
        value = config.get(option)
        success = config.silent_set(option, str(not value))
        roster.modified()
        if not success:
            self.core.information('Unable to write in the config file',
                                  'Error')
        return True

    def on_slash(self):
        """
        '/' is pressed, we enter "input mode"
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message,
                                          self.execute_slash_command)
        self.input.resize(1, self.width, self.height - 1, 0)
        self.input.do_command("/")  # we add the slash

    def reset_help_message(self, _=None):
        self.input = self.default_help_message
        if self.core.tabs.current_tab is self:
            curses.curs_set(0)
            self.input.refresh()
            self.core.doupdate()
        return True

    def execute_slash_command(self, txt):
        if txt.startswith('/'):
            self.input.key_enter()
            self.execute_command(txt)
        return self.reset_help_message()

    def on_lose_focus(self):
        self.state = 'normal'

    def on_gain_focus(self):
        self.state = 'current'
        if isinstance(self.input, windows.HelpText):
            curses.curs_set(0)
        else:
            curses.curs_set(1)

    @refresh_wrapper.conditional
    def move_cursor_down(self):
        if isinstance(self.input,
                      windows.Input) and not self.input.history_disabled:
            return
        return self.roster_win.move_cursor_down()

    @refresh_wrapper.conditional
    def move_cursor_up(self):
        if isinstance(self.input,
                      windows.Input) and not self.input.history_disabled:
            return
        return self.roster_win.move_cursor_up()

    def move_cursor_to_prev_contact(self):
        self.roster_win.move_cursor_up()
        while not isinstance(self.roster_win.get_selected_row(), Contact):
            if not self.roster_win.move_cursor_up():
                break
        self.roster_win.refresh(roster)

    def move_cursor_to_next_contact(self):
        self.roster_win.move_cursor_down()
        while not isinstance(self.roster_win.get_selected_row(), Contact):
            if not self.roster_win.move_cursor_down():
                break
        self.roster_win.refresh(roster)

    def move_cursor_to_prev_group(self):
        self.roster_win.move_cursor_up()
        while not isinstance(self.roster_win.get_selected_row(), RosterGroup):
            if not self.roster_win.move_cursor_up():
                break
        self.roster_win.refresh(roster)

    def move_cursor_to_next_group(self):
        self.roster_win.move_cursor_down()
        while not isinstance(self.roster_win.get_selected_row(), RosterGroup):
            if not self.roster_win.move_cursor_down():
                break
        self.roster_win.refresh(roster)

    def on_scroll_down(self):
        return self.roster_win.move_cursor_down(self.height // 2)

    def on_scroll_up(self):
        return self.roster_win.move_cursor_up(self.height // 2)

    @refresh_wrapper.conditional
    def on_space(self):
        if isinstance(self.input, windows.Input):
            return
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, RosterGroup):
            selected_row.toggle_folded()
            roster.modified()
            return True
        elif isinstance(selected_row, Contact):
            group = "none"
            found_group = False
            pos = self.roster_win.pos
            while not found_group and pos >= 0:
                row = self.roster_win.roster_cache[pos]
                pos -= 1
                if isinstance(row, RosterGroup):
                    found_group = True
                    group = row.name
            selected_row.toggle_folded(group)
            roster.modified()
            return True
        return False

    def get_contact_version(self):
        """
        Show the versions of the resource(s) currently selected
        """
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, Contact):
            for resource in selected_row.resources:
                self.core.command.version(str(resource.jid))
        elif isinstance(selected_row, Resource):
            self.core.command.version(str(selected_row.jid))
        else:
            self.core.information('Nothing to get versions from', 'Info')

    def show_contact_info(self):
        """
        Show the contact info (resource number, status, presence, etc)
        when 'i' is pressed.
        """
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, Contact):
            cont = selected_row
            res = selected_row.get_highest_priority_resource()
            acc = []
            acc.append('Contact: %s (%s)' % (cont.bare_jid, res.presence
                                             if res else 'unavailable'))
            if res:
                acc.append(
                    '%s connected resource%s' % (len(cont), ''
                                                 if len(cont) == 1 else 's'))
                acc.append('Current status: %s' % res.status)
            if cont.tune:
                acc.append('Tune: %s' % common.format_tune_string(cont.tune))
            if cont.mood:
                acc.append('Mood: %s' % cont.mood)
            if cont.activity:
                acc.append('Activity: %s' % cont.activity)
            if cont.gaming:
                acc.append(
                    'Game: %s' % (common.format_gaming_string(cont.gaming)))
            msg = '\n'.join(acc)
        elif isinstance(selected_row, Resource):
            res = selected_row
            msg = 'Resource: %s (%s)\nCurrent status: %s\nPriority: %s' % (
                res.jid, res.presence, res.status, res.priority)
        elif isinstance(selected_row, RosterGroup):
            rg = selected_row
            msg = 'Group: %s [%s/%s] contacts online' % (
                rg.name,
                rg.get_nb_connected_contacts(),
                len(rg),
            )
        else:
            msg = None
        if msg:
            self.core.information(msg, 'Info')

    def change_contact_name(self):
        """
        Auto-fill a /name command when 'n' is pressed
        """
        selected_row = self.roster_win.get_selected_row()
        if isinstance(selected_row, Contact):
            jid = selected_row.bare_jid
        elif isinstance(selected_row, Resource):
            jid = safeJID(selected_row.jid).bare
        else:
            return
        self.on_slash()
        self.input.text = '/name "%s" ' % jid
        self.input.key_end()
        self.input.refresh()

    @refresh_wrapper.always
    def start_search(self):
        """
        Start the search. The input should appear with a short instruction
        in it.
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("[Search]", self.on_search_terminate,
                                          self.on_search_terminate,
                                          self.set_roster_filter)
        self.input.resize(1, self.width, self.height - 1, 0)
        self.input.disable_history()
        roster.modified()
        self.refresh()
        return True

    @refresh_wrapper.always
    def start_search_slow(self):
        curses.curs_set(1)
        self.input = windows.CommandInput("[Search]", self.on_search_terminate,
                                          self.on_search_terminate,
                                          self.set_roster_filter_slow)
        self.input.resize(1, self.width, self.height - 1, 0)
        self.input.disable_history()
        return True

    def set_roster_filter_slow(self, txt):
        roster.contact_filter = (jid_and_name_match_slow, txt)
        roster.modified()
        self.refresh()
        return False

    def set_roster_filter(self, txt):
        roster.contact_filter = (jid_and_name_match, txt)
        roster.modified()
        self.refresh()
        return False

    @refresh_wrapper.always
    def on_search_terminate(self, txt):
        curses.curs_set(0)
        roster.contact_filter = roster.DEFAULT_FILTER
        self.reset_help_message()
        roster.modified()
        return True

    def on_close(self):
        return


def diffmatch(search, string):
    """
    Use difflib and a loop to check if search_pattern can
    be 'almost' found INSIDE a string.
    'almost' being defined by difflib
    """
    if len(search) > len(string):
        return False
    l = len(search)
    ratio = 0.7
    for i in range(len(string) - l + 1):
        if difflib.SequenceMatcher(None, search,
                                   string[i:i + l]).ratio() >= ratio:
            return True
    return False


def jid_and_name_match(contact, txt):
    """
    Match jid with text precisely
    """
    if not txt:
        return True
    txt = txt.lower()
    if txt in safeJID(contact.bare_jid).bare.lower():
        return True
    if txt in contact.name.lower():
        return True
    return False


def jid_and_name_match_slow(contact, txt):
    """
    A function used to know if a contact in the roster should
    be shown in the roster
    """
    if not txt:
        return True  # Everything matches when search is empty
    user = safeJID(contact.bare_jid).bare
    if diffmatch(txt, user):
        return True
    if contact.name and diffmatch(txt, contact.name):
        return True
    return False
