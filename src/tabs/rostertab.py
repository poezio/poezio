"""
The RosterInfoTab is the tab showing roster info, the list of contacts,
half of it is dedicated to showing the information buffer, and a small
rectangle shows the current contact info.

This module also includes functions to match users in the roster.
"""
from gettext import gettext as _

import logging
log = logging.getLogger(__name__)

import curses
import difflib
import os
from os import getenv, path

from . import Tab

import common
import windows
from common import safeJID
from config import config
from contact import Contact, Resource
from decorators import refresh_wrapper
from roster import RosterGroup, roster
from theming import get_theme, dump_tuple

class RosterInfoTab(Tab):
    """
    A tab, splitted in two, containing the roster and infos
    """
    plugin_commands = {}
    plugin_keys = {}
    def __init__(self):
        Tab.__init__(self)
        self.name = "Roster"
        self.v_separator = windows.VerticalSeparator()
        self.information_win = windows.TextWin()
        self.core.information_buffer.add_window(self.information_win)
        self.roster_win = windows.RosterWin()
        self.contact_info_win = windows.ContactInfoWin()
        self.default_help_message = windows.HelpText("Enter commands with “/”. “o”: toggle offline show")
        self.input = self.default_help_message
        self.state = 'normal'
        self.key_func['^I'] = self.completion
        self.key_func[' '] = self.on_space
        self.key_func["/"] = self.on_slash
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
        self.key_func["n"] = self.change_contact_name
        self.key_func["s"] = self.start_search
        self.key_func["S"] = self.start_search_slow
        self.register_command('deny', self.command_deny,
                usage=_('[jid]'),
                desc=_('Deny your presence to the provided JID (or the selected contact in your roster), who is asking you to be in his/here roster.'),
                shortdesc=_('Deny an user your presence.'),
                completion=self.completion_deny)
        self.register_command('accept', self.command_accept,
                usage=_('[jid]'),
                desc=_('Allow the provided JID (or the selected contact in your roster), to see your presence.'),
                shortdesc=_('Allow an user your presence.'),
                completion=self.completion_deny)
        self.register_command('add', self.command_add,
                usage=_('<jid>'),
                desc=_('Add the specified JID to your roster, ask him to allow you to see his presence, and allow him to see your presence.'),
                shortdesc=_('Add an user to your roster.'))
        self.register_command('name', self.command_name,
                usage=_('<jid> <name>'),
                shortdesc=_('Set the given JID\'s name.'),
                completion=self.completion_name)
        self.register_command('groupadd', self.command_groupadd,
                usage=_('<jid> <group>'),
                desc=_('Add the given JID to the given group.'),
                shortdesc=_('Add an user to a group'),
                completion=self.completion_groupadd)
        self.register_command('groupmove', self.command_groupmove,
                usage=_('<jid> <old group> <new group>'),
                desc=_('Move the given JID from the old group to the new group.'),
                shortdesc=_('Move an user to another group.'),
                completion=self.completion_groupmove)
        self.register_command('groupremove', self.command_groupremove,
                usage=_('<jid> <group>'),
                desc=_('Remove the given JID from the given group.'),
                shortdesc=_('Remove an user from a group.'),
                completion=self.completion_groupremove)
        self.register_command('remove', self.command_remove,
                usage=_('[jid]'),
                desc=_('Remove the specified JID from your roster. This wil unsubscribe you from its presence, cancel its subscription to yours, and remove the item from your roster.'),
                shortdesc=_('Remove an user from your roster.'),
                completion=self.completion_remove)
        self.register_command('reconnect', self.command_reconnect,
                desc=_('Disconnect from the remote server if you are currently connected and then connect to it again.'),
                shortdesc=_('Disconnect and reconnect to the server.'))
        self.register_command('disconnect', self.command_disconnect,
                desc=_('Disconnect from the remote server.'),
                shortdesc=_('Disconnect from the server.'))
        self.register_command('export', self.command_export,
                usage=_('[/path/to/file]'),
                desc=_('Export your contacts into /path/to/file if specified, or $HOME/poezio_contacts if not.'),
                shortdesc=_('Export your roster to a file.'),
                completion=self.completion_file)
        self.register_command('import', self.command_import,
                usage=_('[/path/to/file]'),
                desc=_('Import your contacts from /path/to/file if specified, or $HOME/poezio_contacts if not.'),
                shortdesc=_('Import your roster from a file.'),
                completion=self.completion_file)
        self.register_command('clear', self.command_clear,
                shortdesc=_('Clear the info buffer.'))
        self.register_command('last_activity', self.command_last_activity,
                usage=_('<jid>'),
                desc=_('Informs you of the last activity of a JID.'),
                shortdesc=_('Get the activity of someone.'),
                completion=self.core.completion_last_activity)
        self.register_command('password', self.command_password,
                usage='<password>',
                shortdesc=_('Change your password'))

        self.resize()
        self.update_commands()
        self.update_keys()

    def check_blocking(self, features):
        if 'urn:xmpp:blocking' in features:
            self.register_command('block', self.command_block,
                    usage=_('[jid]'),
                    shortdesc=_('Prevent a JID from talking to you.'),
                    completion=self.completion_block)
            self.register_command('unblock', self.command_unblock,
                    usage=_('[jid]'),
                    shortdesc=_('Allow a JID to talk to you.'),
                    completion=self.completion_unblock)
            self.register_command('list_blocks', self.command_list_blocks,
                    shortdesc=_('Show the blocked contacts.'))
            self.core.xmpp.del_event_handler('session_start', self.check_blocking)
            self.core.xmpp.add_event_handler('blocked_message', self.on_blocked_message)

    def on_blocked_message(self, message):
        """
        When we try to send a message to a blocked contact
        """
        tab = self.core.get_conversation_by_jid(message['from'], False)
        if not tab:
            log.debug('Received message from nonexistent tab: %s', message['from'])
        message = '\x19%(info_col)s}Cannot send message to %(jid)s: contact blocked' % {
                'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
                'jid': message['from'],
            }
        tab.add_message(message)

    def command_block(self, arg):
        """
        /block [jid]
        """
        def callback(iq):
            if iq['type'] == 'error':
                return self.core.information('Could not block the contact.', 'Error')
            elif iq['type'] == 'result':
                return self.core.information('Contact blocked.', 'Info')

        item = self.roster_win.selected_row
        if arg:
            jid = safeJID(arg)
        elif isinstance(item, Contact):
            jid = item.bare_jid
        elif isinstance(item, Resource):
            jid = item.jid.bare
        self.core.xmpp.plugin['xep_0191'].block(jid, block=False, callback=callback)

    def completion_block(self, the_input):
        """
        Completion for /block
        """
        if the_input.get_argument_position() == 1:
            jids = roster.jids()
            return the_input.new_completion(jids, 1, '', quotify=False)

    def command_unblock(self, arg):
        """
        /unblock [jid]
        """
        def callback(iq):
            if iq['type'] == 'error':
                return self.core.information('Could not unblock the contact.', 'Error')
            elif iq['type'] == 'result':
                return self.core.information('Contact unblocked.', 'Info')

        item = self.roster_win.selected_row
        if arg:
            jid = safeJID(arg)
        elif isinstance(item, Contact):
            jid = item.bare_jid
        elif isinstance(item, Resource):
            jid = item.jid.bare
        self.core.xmpp.plugin['xep_0191'].unblock(jid, block=False, callback=callback)

    def completion_unblock(self, the_input):
        """
        Completion for /unblock
        """
        if the_input.get_argument_position():
            try:
                iq = self.core.xmpp.plugin['xep_0191'].get_blocked(block=True)
            except Exception as e:
                iq = e.iq
            finally:
                if iq['type'] == 'error':
                    return
                l = sorted(str(item) for item in iq['blocklist']['items'])
                return the_input.new_completion(l, 1, quotify=False)

    def command_list_blocks(self, arg=None):
        """
        /list_blocks
        """
        def callback(iq):
            if iq['type'] == 'error':
                return self.core.information('Could not retrieve the blocklist.', 'Error')
            s = 'List of blocked JIDs:\n'
            items = (str(item) for item in iq['blocklist']['items'])
            jids = '\n'.join(items)
            if jids:
                s += jids
            else:
                s = 'No blocked JIDs.'
            self.core.information(s, 'Info')

        self.core.xmpp.plugin['xep_0191'].get_blocked(block=False, callback=callback)

    def command_reconnect(self, args=None):
        """
        /reconnect
        """
        self.core.disconnect(reconnect=True)

    def command_disconnect(self, args=None):
        """
        /disconnect
        """
        self.core.disconnect()

    def command_last_activity(self, arg=None):
        """
        /activity [jid]
        """
        item = self.roster_win.selected_row
        if arg:
            jid = arg
        elif isinstance(item, Contact):
            jid = item.bare_jid
        elif isinstance(item, Resource):
            jid = item.jid.bare
        else:
            self.core.information('No JID selected.', 'Error')
            return
        self.core.command_last_activity(jid)

    def resize(self):
        if not self.visible:
            return
        self.need_resize = False
        roster_width = self.width//2
        info_width = self.width-roster_width-1
        self.v_separator.resize(self.height-1 - Tab.tab_win_height(), 1, 0, roster_width)
        self.information_win.resize(self.height-2-4, info_width, 0, roster_width+1, self.core.information_buffer)
        self.roster_win.resize(self.height-1 - Tab.tab_win_height(), roster_width, 0, 0)
        self.contact_info_win.resize(5 - Tab.tab_win_height(), info_width, self.height-2-4, roster_width+1)
        self.input.resize(1, self.width, self.height-1, 0)
        self.default_help_message.resize(1, self.width, self.height-1, 0)

    def completion(self):
        # Check if we are entering a command (with the '/' key)
        if isinstance(self.input, windows.Input) and\
                not self.input.help_message:
            self.complete_commands(self.input)

    def completion_file(self, the_input):
        """
        Completion for /import and /export
        """
        text = the_input.get_text()
        args = text.split()
        n = len(args)
        if n == 1:
            home = os.getenv('HOME') or '/'
            return the_input.auto_completion([home, '/tmp'], '')
        else:
            the_path = text[text.index(' ')+1:]
            try:
                names = os.listdir(the_path)
            except:
                names = []
            end_list = []
            for name in names:
                value = os.path.join(the_path, name)
                if not name.startswith('.'):
                    end_list.append(value)

            return the_input.auto_completion(end_list, '')

    def command_clear(self, arg=''):
        """
        /clear
        """
        self.core.information_buffer.messages = []
        self.information_win.rebuild_everything(self.core.information_buffer)
        self.core.information_win.rebuild_everything(self.core.information_buffer)
        self.refresh()

    def command_password(self, arg):
        """
        /password <password>
        """
        def callback(iq):
            if iq['type'] == 'result':
                self.core.information('Password updated', 'Account')
                if config.get('password', ''):
                    config.silent_set('password', arg)
            else:
                self.core.information('Unable to change the password', 'Account')
        self.core.xmpp.plugin['xep_0077'].change_password(arg, callback=callback)



    def command_deny(self, arg):
        """
        /deny [jid]
        Denies a JID from our roster
        """
        if not arg:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            else:
                self.core.information('No subscription to deny')
                return
        else:
            jid = safeJID(arg).bare
            if not jid in [jid for jid in roster.jids()]:
                self.core.information('No subscription to deny')
                return

        contact = roster[jid]
        if contact:
            contact.unauthorize()

    def command_add(self, args):
        """
        Add the specified JID to the roster, and set automatically
        accept the reverse subscription
        """
        jid = safeJID(safeJID(args.strip()).bare)
        if not jid:
            self.core.information(_('No JID specified'), 'Error')
            return
        if jid in roster and roster[jid].subscription in ('to', 'both'):
            return self.core.information('Already subscribed.', 'Roster')
        roster.add(jid)
        roster.modified()

    def command_name(self, arg):
        """
        Set a name for the specified JID in your roster
        """
        def callback(iq):
            if not iq:
                self.core.information('The name could not be set.', 'Error')
                log.debug('Error in /name:\n%s', iq)
        args = common.shell_split(arg)
        if not args:
            return self.core.command_help('name')
        jid = safeJID(args[0]).bare
        name = args[1] if len(args) == 2 else ''

        contact = roster[jid]
        if contact is None:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        groups = set(contact.groups)
        if 'none' in groups:
            groups.remove('none')
        subscription = contact.subscription
        self.core.xmpp.update_roster(jid, name=name, groups=groups, subscription=subscription,
                callback=callback, block=False)

    def command_groupadd(self, args):
        """
        Add the specified JID to the specified group
        """
        args = common.shell_split(args)
        if len(args) != 2:
            return
        jid = safeJID(args[0]).bare
        group = args[1]

        contact = roster[jid]
        if contact is None:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        new_groups = set(contact.groups)
        if group in new_groups:
            self.core.information(_('JID already in group'), 'Error')
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

        self.core.xmpp.update_roster(jid, name=name, groups=new_groups, subscription=subscription,
                callback=callback, block=False)

    def command_groupmove(self, arg):
        """
        Remove the specified JID from the first specified group and add it to the second one
        """
        args = common.shell_split(arg)
        if len(args) != 3:
            return self.core.command_help('groupmove')
        jid = safeJID(args[0]).bare
        group_from = args[1]
        group_to = args[2]

        contact = roster[jid]
        if not contact:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        new_groups = set(contact.groups)
        if 'none' in new_groups:
            new_groups.remove('none')

        if group_to == 'none' or group_from == 'none':
            self.core.information(_('"none" is not a group.'), 'Error')
            return

        if group_from not in new_groups:
            self.core.information(_('JID not in first group'), 'Error')
            return

        if group_to in new_groups:
            self.core.information(_('JID already in second group'), 'Error')
            return

        if group_to == group_from:
            self.core.information(_('The groups are the same.'), 'Error')
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
                self.core.information('The group could not be set')
                log.debug('Error in groupmove:\n%s', iq)

        self.core.xmpp.update_roster(jid, name=name, groups=new_groups, subscription=subscription,
                callback=callback, block=False)

    def command_groupremove(self, args):
        """
        Remove the specified JID from the specified group
        """
        args = common.shell_split(args)
        if len(args) != 2:
            return
        jid = safeJID(args[0]).bare
        group = args[1]

        contact = roster[jid]
        if contact is None:
            self.core.information(_('No such JID in roster'), 'Error')
            return

        new_groups = set(contact.groups)
        try:
            new_groups.remove('none')
        except KeyError:
            pass
        if group not in new_groups:
            self.core.information(_('JID not in group'), 'Error')
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

        self.core.xmpp.update_roster(jid, name=name, groups=new_groups, subscription=subscription,
                callback=callback, block=False)

    def command_remove(self, args):
        """
        Remove the specified JID from the roster. i.e.: unsubscribe
        from its presence, and cancel its subscription to our.
        """
        if args.strip():
            jid = safeJID(args.strip()).bare
        else:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            else:
                self.core.information('No roster item to remove')
                return
        roster.remove(jid)
        del roster[jid]

    def command_import(self, arg):
        """
        Import the contacts
        """
        args = common.shell_split(arg)
        if len(args):
            if args[0].startswith('/'):
                filepath = args[0]
            else:
                filepath = path.join(getenv('HOME'), args[0])
        else:
            filepath = path.join(getenv('HOME'), 'poezio_contacts')
        if not path.isfile(filepath):
            self.core.information('The file %s does not exist' % filepath, 'Error')
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

    def command_export(self, arg):
        """
        Export the contacts
        """
        args = common.shell_split(arg)
        if len(args):
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
            self.core.information('Failed to export contacts to %s' % filepath, 'Info')

    def completion_remove(self, the_input):
        """
        Completion for /remove
        """
        jids = [jid for jid in roster.jids()]
        return the_input.auto_completion(jids, '', quotify=False)

    def completion_name(self, the_input):
        """Completion for /name"""
        n = the_input.get_argument_position()
        if n == 1:
            jids = [jid for jid in roster.jids()]
            return the_input.new_completion(jids, n, quotify=True)
        return False

    def completion_groupadd(self, the_input):
        n = the_input.get_argument_position()
        if n == 1:
            jids = sorted(jid for jid in roster.jids())
            return the_input.new_completion(jids, n, '', quotify=True)
        elif n == 2:
            groups = sorted(group for group in roster.groups if group != 'none')
            return the_input.new_completion(groups, n, '', quotify=True)
        return False

    def completion_groupmove(self, the_input):
        args = common.shell_split(the_input.text)
        n = the_input.get_argument_position()
        if n == 1:
            jids = sorted(jid for jid in roster.jids())
            return the_input.new_completion(jids, n, '', quotify=True)
        elif n == 2:
            contact = roster[args[1]]
            if not contact:
                return False
            groups = list(contact.groups)
            if 'none' in groups:
                groups.remove('none')
            return the_input.new_completion(groups, n, '', quotify=True)
        elif n == 3:
            groups = sorted(group for group in roster.groups)
            return the_input.new_completion(groups, n, '', quotify=True)
        return False

    def completion_groupremove(self, the_input):
        args = common.shell_split(the_input.text)
        n = the_input.get_argument_position()
        if n == 1:
            jids = sorted(jid for jid in roster.jids())
            return the_input.new_completion(jids, n, '', quotify=True)
        elif n == 2:
            contact = roster[args[1]]
            if contact is None:
                return False
            groups = sorted(contact.groups)
            try:
                groups.remove('none')
            except ValueError:
                pass
            return the_input.new_completion(groups, n, '', quotify=True)
        return False

    def completion_deny(self, the_input):
        """
        Complete the first argument from the list of the
        contact with ask=='subscribe'
        """
        jids = sorted(str(contact.bare_jid) for contact in roster.contacts.values()
             if contact.pending_in)
        return the_input.new_completion(jids, 1, '', quotify=False)

    def command_accept(self, arg):
        """
        Accept a JID from in roster. Authorize it AND subscribe to it
        """
        if not arg:
            item = self.roster_win.selected_row
            if isinstance(item, Contact):
                jid = item.bare_jid
            else:
                self.core.information('No subscription to accept')
                return
        else:
            jid = safeJID(arg).bare
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
        if contact.subscription in ('from', 'none') and not contact.pending_out:
            self.core.xmpp.send_presence(pto=jid, ptype='subscribe', pnick=self.core.own_nick)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        self.v_separator.refresh()
        self.roster_win.refresh(roster)
        self.contact_info_win.refresh(self.roster_win.get_selected_row())
        self.information_win.refresh()
        self.refresh_tab_win()
        self.input.refresh()

    def get_name(self):
        return self.name

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
        value = config.get(option, False)
        success = config.silent_set(option, str(not value))
        roster.modified()
        if not success:
            self.core.information(_('Unable to write in the config file'), 'Error')
        return True

    def on_slash(self):
        """
        '/' is pressed, we enter "input mode"
        """
        curses.curs_set(1)
        self.input = windows.CommandInput("", self.reset_help_message, self.execute_slash_command)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.do_command("/") # we add the slash

    def reset_help_message(self, _=None):
        self.input = self.default_help_message
        if self.core.current_tab() is self:
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
        if isinstance(self.input, windows.Input) and not self.input.history_disabled:
            return
        return self.roster_win.move_cursor_down()

    @refresh_wrapper.conditional
    def move_cursor_up(self):
        if isinstance(self.input, windows.Input) and not self.input.history_disabled:
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
                self.core.command_version(str(resource.jid))
        elif isinstance(selected_row, Resource):
            self.core.command_version(str(selected_row.jid))
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
            acc.append('Contact: %s (%s)' % (cont.bare_jid, res.presence if res else 'unavailable'))
            if res:
                acc.append('%s connected resource%s' % (len(cont), '' if len(cont) == 1 else 's'))
                acc.append('Current status: %s' % res.status)
            if cont.tune:
                acc.append('Tune: %s' % common.format_tune_string(cont.tune))
            if cont.mood:
                acc.append('Mood: %s' % cont.mood)
            if cont.activity:
                acc.append('Activity: %s' % cont.activity)
            if cont.gaming:
                acc.append('Game: %s' % (common.format_gaming_string(cont.gaming)))
            msg = '\n'.join(acc)
        elif isinstance(selected_row, Resource):
            res = selected_row
            msg = 'Resource: %s (%s)\nCurrent status: %s\nPriority: %s' % (
                    res.jid,
                    res.presence,
                    res.status,
                    res.priority)
        elif isinstance(selected_row, RosterGroup):
            rg = selected_row
            msg = 'Group: %s [%s/%s] contacts online' % (
                    rg.name,
                    rg.get_nb_connected_contacts(),
                    len(rg),)
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
        self.input = windows.CommandInput("[Search]", self.on_search_terminate, self.on_search_terminate, self.set_roster_filter)
        self.input.resize(1, self.width, self.height-1, 0)
        self.input.disable_history()
        roster.modified()
        self.refresh()
        return True

    @refresh_wrapper.always
    def start_search_slow(self):
        curses.curs_set(1)
        self.input = windows.CommandInput("[Search]", self.on_search_terminate, self.on_search_terminate, self.set_roster_filter_slow)
        self.input.resize(1, self.width, self.height-1, 0)
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
        roster.contact_filter = None
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
        if difflib.SequenceMatcher(None, search, string[i:i+l]).ratio() >= ratio:
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
        return True             # Everything matches when search is empty
    user = safeJID(contact.bare_jid).bare
    if diffmatch(txt, user):
        return True
    if contact.name and diffmatch(txt, contact.name):
        return True
    return False
