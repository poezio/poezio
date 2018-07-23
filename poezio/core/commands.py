"""
Global commands which are to be linked to the Core class
"""

import logging

log = logging.getLogger(__name__)

from xml.etree import cElementTree as ET

from slixmpp.exceptions import XMPPError
from slixmpp.xmlstream.xmlstream import NotConnectedError
from slixmpp.xmlstream.stanzabase import StanzaBase
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import StanzaPath

from poezio import common
from poezio import pep
from poezio import tabs
from poezio.bookmarks import Bookmark
from poezio.common import safeJID
from poezio.config import config, DEFAULT_CONFIG, options as config_opts
from poezio import multiuserchat as muc
from poezio.plugin import PluginConfig
from poezio.roster import roster
from poezio.theming import dump_tuple, get_theme
from poezio.decorators import command_args_parser

from poezio.core.structs import Command, POSSIBLE_SHOW


class CommandCore:
    def __init__(self, core):
        self.core = core

    @command_args_parser.quoted(0, 1)
    def help(self, args):
        """
        /help [command_name]
        """
        if not args:
            color = dump_tuple(get_theme().COLOR_HELP_COMMANDS)
            acc = []
            buff = ['Global commands:']
            for name, command in self.core.commands.items():
                if isinstance(command, Command):
                    acc.append('  \x19%s}%s\x19o - %s' % (color, name,
                                                          command.short_desc))
                else:
                    acc.append('  \x19%s}%s\x19o' % (color, name))
            acc = sorted(acc)
            buff.extend(acc)
            acc = []
            buff.append('Tab-specific commands:')
            tab_commands = self.core.tabs.current_tab.commands
            for name, command in tab_commands.items():
                if isinstance(command, Command):
                    acc.append('  \x19%s}%s\x19o - %s' % (color, name,
                                                          command.short_desc))
                else:
                    acc.append('  \x19%s}%s\x19o' % (color, name))
            acc = sorted(acc)
            buff.extend(acc)

            msg = '\n'.join(buff)
            msg += "\nType /help <command_name> to know what each command does"
        else:
            command = args[0].lstrip('/').strip()

            tab_commands = self.core.tabs.current_tab.commands
            if command in tab_commands:
                tup = tab_commands[command]
            elif command in self.core.commands:
                tup = self.core.commands[command]
            else:
                self.core.information('Unknown command: %s' % command, 'Error')
                return
            if isinstance(tup, Command):
                msg = 'Usage: /%s %s\n' % (command, tup.usage)
                msg += tup.desc
            else:
                msg = tup[1]
        self.core.information(msg, 'Help')

    @command_args_parser.quoted(1)
    def runkey(self, args):
        """
        /runkey <key>
        """

        def replace_line_breaks(key):
            "replace ^J with \n"
            if key == '^J':
                return '\n'
            return key

        if args is None:
            return self.help('runkey')
        char = args[0]
        func = self.core.key_func.get(char, None)
        if func:
            func()
        else:
            res = self.core.do_command(replace_line_breaks(char), False)
            if res:
                self.core.refresh_window()

    @command_args_parser.quoted(1, 1, [None])
    def status(self, args):
        """
        /status <status> [msg]
        """
        if args is None:
            return self.help('status')

        if args[0] not in POSSIBLE_SHOW.keys():
            return self.help('status')

        show = POSSIBLE_SHOW[args[0]]
        msg = args[1]

        pres = self.core.xmpp.make_presence()
        if msg:
            pres['status'] = msg
        pres['type'] = show
        self.core.events.trigger('send_normal_presence', pres)
        pres.send()
        current = self.core.tabs.current_tab
        is_muctab = isinstance(current, tabs.MucTab)
        if is_muctab and current.joined and show in ('away', 'xa'):
            current.send_chat_state('inactive')
        for tab in self.core.tabs:
            if isinstance(tab, tabs.MucTab) and tab.joined:
                muc.change_show(self.core.xmpp, tab.name, tab.own_nick, show,
                                msg)
            if hasattr(tab, 'directed_presence'):
                del tab.directed_presence
        self.core.set_status(show, msg)
        if is_muctab and current.joined and show not in ('away', 'xa'):
            current.send_chat_state('active')

    @command_args_parser.quoted(1, 2, [None, None])
    def presence(self, args):
        """
        /presence <JID> [type] [status]
        """
        if args is None:
            return self.help('presence')

        jid, ptype, status = args[0], args[1], args[2]
        if jid == '.' and isinstance(self.core.tabs.current_tab, tabs.ChatTab):
            jid = self.core.tabs.current_tab.name
        if ptype == 'available':
            ptype = None
        try:
            pres = self.core.xmpp.make_presence(
                pto=jid, ptype=ptype, pstatus=status)
            self.core.events.trigger('send_normal_presence', pres)
            pres.send()
        except (XMPPError, NotConnectedError):
            self.core.information('Could not send directed presence', 'Error')
            log.debug(
                'Could not send directed presence to %s', jid, exc_info=True)
            return
        tab = self.core.tabs.by_name(jid)
        if tab:
            if ptype in ('xa', 'away'):
                tab.directed_presence = False
                chatstate = 'inactive'
            else:
                tab.directed_presence = True
                chatstate = 'active'
            if tab == self.core.tabs.current_tab:
                tab.send_chat_state(chatstate, True)
            if isinstance(tab, tabs.MucTab):
                for private in tab.privates:
                    private.directed_presence = tab.directed_presence
                if self.core.tabs.current_tab in tab.privates:
                    self.core.tabs.current_tab.send_chat_state(chatstate, True)

    @command_args_parser.quoted(1)
    def theme(self, args=None):
        """/theme <theme name>"""
        if args is None:
            return self.help('theme')
        self.set('theme %s' % (args[0], ))

    @command_args_parser.quoted(1)
    def win(self, args):
        """
        /win <number or name>
        """
        if args is None:
            return self.help('win')

        name = args[0]
        try:
            number = int(name)
        except ValueError:
            number = -1
            name = name.lower()
        if number != -1 and self.core.tabs.current_tab == number:
            return
        prev_nb = self.core.previous_tab_nb
        self.core.previous_tab_nb = self.core.tabs.current_tab
        old_tab = self.core.tabs.current_tab
        if 0 <= number < len(self.core.tabs):
            if not self.core.tabs[number]:
                self.core.previous_tab_nb = prev_nb
                return
            self.core.tabs.set_current_index(number)
        else:
            match = self.core.tabs.find_match(name)
            if match is None:
                return
            self.core.tabs.set_current_tab(match)

    @command_args_parser.quoted(2)
    def move_tab(self, args):
        """
        /move_tab old_pos new_pos
        """
        if args is None:
            return self.help('move_tab')

        current_tab = self.core.tabs.current_tab
        if args[0] == '.':
            args[0] = current_tab.nb
        if args[1] == '.':
            args[1] = current_tab.nb

        def get_nb_from_value(value):
            "parse the cmdline to guess the tab the users wants"
            ref = None
            try:
                ref = int(value)
            except ValueError:
                old_tab = None
                for tab in self.core.tabs:
                    if not old_tab and value == tab.name:
                        old_tab = tab
                if not old_tab:
                    self.core.information("Tab %s does not exist" % args[0],
                                          "Error")
                    return None
                ref = old_tab.nb
            return ref

        old = get_nb_from_value(args[0])
        new = get_nb_from_value(args[1])
        if new is None or old is None:
            return self.core.information('Unable to move the tab.', 'Info')
        result = self.core.insert_tab(old, new)
        if not result:
            self.core.information('Unable to move the tab.', 'Info')
        self.core.refresh_window()

    @command_args_parser.quoted(0, 1)
    def list(self, args):
        """
        /list [server]
        Opens a MucListTab containing the list of the room in the specified server
        """
        if args is None:
            return self.help('list')
        elif args:
            jid = safeJID(args[0])
        else:
            if not isinstance(self.core.tabs.current_tab, tabs.MucTab):
                return self.core.information('Please provide a server',
                                             'Error')
            jid = safeJID(self.core.tabs.current_tab.name)
        list_tab = tabs.MucListTab(self.core, jid)
        self.core.add_tab(list_tab, True)
        cb = list_tab.on_muc_list_item_received
        self.core.xmpp.plugin['xep_0030'].get_items(jid=jid, callback=cb)

    @command_args_parser.quoted(1)
    def version(self, args):
        """
        /version <jid>
        """
        if args is None:
            return self.help('version')
        jid = safeJID(args[0])
        if jid.resource or jid not in roster or not roster[jid].resources:
            self.core.xmpp.plugin['xep_0092'].get_version(
                jid, callback=self.core.handler.on_version_result)
        elif jid in roster:
            for resource in roster[jid].resources:
                self.core.xmpp.plugin['xep_0092'].get_version(
                    resource.jid, callback=self.core.handler.on_version_result)

    def _empty_join(self):
        tab = self.core.tabs.current_tab
        if not isinstance(tab, (tabs.MucTab, tabs.PrivateTab)):
            return (None, None)
        room = safeJID(tab.name).bare
        nick = tab.own_nick
        return (room, nick)

    def _parse_join_jid(self, jid_string):
        # we try to join a server directly
        if jid_string.startswith('@'):
            server_root = True
            info = safeJID(jid_string[1:])
        else:
            info = safeJID(jid_string)
            server_root = False

        set_nick = ''
        if len(jid_string) > 1 and jid_string.startswith('/'):
            set_nick = jid_string[1:]
        elif info.resource:
            set_nick = info.resource

        # happens with /join /nickname, which is OK
        if info.bare == '':
            tab = self.core.tabs.current_tab
            if not isinstance(tab, tabs.MucTab):
                room, set_nick = (None, None)
            else:
                room = tab.name
                if not set_nick:
                    set_nick = tab.own_nick
        else:
            room = info.bare
            # no server is provided, like "/join hello":
            # use the server of the current room if available
            # check if the current room's name has a server
            if room.find('@') == -1 and not server_root:
                tab = self.core.tabs.current_tab
                if isinstance(tab, tabs.MucTab):
                    if tab.name.find('@') != -1:
                        domain = safeJID(tab.name).domain
                        room += '@%s' % domain
        return (room, set_nick)

    @command_args_parser.quoted(0, 2)
    def join(self, args):
        """
        /join [room][/nick] [password]
        """
        if len(args) == 0:
            room, nick = self._empty_join()
        else:
            room, nick = self._parse_join_jid(args[0])
        if not room and not nick:
            return  # nothing was parsed

        room = room.lower()
        if nick == '':
            nick = self.core.own_nick

        # a password is provided
        if len(args) == 2:
            password = args[1]
        else:
            password = config.get_by_tabname('password', room, fallback=False)

        if room in self.core.pending_invites:
            del self.core.pending_invites[room]

        tab = self.core.tabs.by_name_and_class(room, tabs.MucTab)
        # New tab
        if tab is None:
            tab = self.core.open_new_room(room, nick, password=password)
            tab.join()
        else:
            self.core.focus_tab(tab)
            if tab.own_nick == nick and tab.joined:
                self.core.information('/join: Nothing to do.', 'Info')
            else:
                tab.command_part('')
                tab.own_nick = nick
                tab.password = password
                tab.join()

        if config.get('bookmark_on_join'):
            method = 'remote' if config.get(
                'use_remote_bookmarks') else 'local'
            self._add_bookmark('%s/%s' % (room, nick), True, password, method)

        if tab == self.core.tabs.current_tab:
            tab.refresh()
            self.core.doupdate()

    @command_args_parser.quoted(0, 2)
    def bookmark_local(self, args):
        """
        /bookmark_local [room][/nick] [password]
        """
        if not args and not isinstance(self.core.tabs.current_tab,
                                       tabs.MucTab):
            return
        password = args[1] if len(args) > 1 else None
        jid = args[0] if args else None

        self._add_bookmark(jid, True, password, 'local')

    @command_args_parser.quoted(0, 3)
    def bookmark(self, args):
        """
        /bookmark [room][/nick] [autojoin] [password]
        """
        if not args and not isinstance(self.core.tabs.current_tab,
                                       tabs.MucTab):
            return
        jid = args[0] if args else ''
        password = args[2] if len(args) > 2 else None

        if not config.get('use_remote_bookmarks'):
            return self._add_bookmark(jid, True, password, 'local')

        if len(args) > 1:
            autojoin = False if args[1].lower() != 'true' else True
        else:
            autojoin = True

        self._add_bookmark(jid, autojoin, password, 'remote')

    def _add_bookmark(self, jid, autojoin, password, method):
        nick = None
        if not jid:
            tab = self.core.tabs.current_tab
            roomname = tab.name
            if tab.joined and tab.own_nick != self.core.own_nick:
                nick = tab.own_nick
            if password is None and tab.password is not None:
                password = tab.password
        elif jid == '*':
            return self._add_wildcard_bookmarks(method)
        else:
            info = safeJID(jid)
            roomname, nick = info.bare, info.resource
            if roomname == '':
                tab = self.core.tabs.current_tab
                if not isinstance(tab, tabs.MucTab):
                    return
                roomname = tab.name
        bookmark = self.core.bookmarks[roomname]
        if bookmark is None:
            bookmark = Bookmark(roomname)
            self.core.bookmarks.append(bookmark)
        bookmark.method = method
        bookmark.autojoin = autojoin
        if nick:
            bookmark.nick = nick
        if password:
            bookmark.password = password

        def callback(iq):
            if iq["type"] != "error":
                self.core.information('Bookmark added.', 'Info')
            else:
                self.core.information("Could not add the bookmarks.", "Info")

        self.core.bookmarks.save_local()
        self.core.bookmarks.save_remote(self.core.xmpp, callback)

    def _add_wildcard_bookmarks(self, method):
        new_bookmarks = []
        for tab in self.core.get_tabs(tabs.MucTab):
            bookmark = self.core.bookmarks[tab.name]
            if not bookmark:
                bookmark = Bookmark(tab.name, autojoin=True, method=method)
                new_bookmarks.append(bookmark)
            else:
                bookmark.method = method
                new_bookmarks.append(bookmark)
                self.core.bookmarks.remove(bookmark)
        new_bookmarks.extend(self.core.bookmarks.bookmarks)
        self.core.bookmarks.set(new_bookmarks)

        def _cb(iq):
            if iq["type"] != "error":
                self.core.information("Bookmarks saved.", "Info")
            else:
                self.core.information("Could not save the remote bookmarks.",
                                      "Info")

        self.core.bookmarks.save_local()
        self.core.bookmarks.save_remote(self.core.xmpp, _cb)

    @command_args_parser.ignored
    def bookmarks(self):
        """/bookmarks"""
        tab = self.core.tabs.by_name_and_class('Bookmarks', tabs.BookmarksTab)
        old_tab = self.core.tabs.current_tab
        if tab:
            self.core.tabs.set_current_tab(tab)
        else:
            tab = tabs.BookmarksTab(self.core, self.core.bookmarks)
            self.core.tabs.append(tab)
            self.core.tabs.set_current_tab(tab)

    @command_args_parser.quoted(0, 1)
    def remove_bookmark(self, args):
        """/remove_bookmark [jid]"""

        def cb(success):
            if success:
                self.core.information('Bookmark deleted', 'Info')
            else:
                self.core.information('Error while deleting the bookmark',
                                      'Error')

        if not args:
            tab = self.core.tabs.current_tab
            if isinstance(tab, tabs.MucTab) and self.core.bookmarks[tab.name]:
                self.core.bookmarks.remove(tab.name)
                self.core.bookmarks.save(self.core.xmpp, callback=cb)
            else:
                self.core.information('No bookmark to remove', 'Info')
        else:
            if self.core.bookmarks[args[0]]:
                self.core.bookmarks.remove(args[0])
                self.core.bookmarks.save(self.core.xmpp, callback=cb)
            else:
                self.core.information('No bookmark to remove', 'Info')

    @command_args_parser.quoted(0, 3)
    def set(self, args):
        """
        /set [module|][section] <option> [value]
        """
        if args is None or len(args) == 0:
            config_dict = config.to_dict()
            lines = []
            theme = get_theme()
            for section_name, section in config_dict.items():
                lines.append(
                    '\x19%(section_col)s}[%(section)s]\x19o' % {
                        'section': section_name,
                        'section_col': dump_tuple(
                            theme.COLOR_INFORMATION_TEXT),
                    })
                for option_name, option_value in section.items():
                    lines.append(
                        '%s\x19%s}=\x19o%s' %
                        (option_name, dump_tuple(
                            theme.COLOR_REVISIONS_MESSAGE), option_value))
            info = ('Current  options:\n%s' % '\n'.join(lines), 'Info')
        elif len(args) == 1:
            option = args[0]
            value = config.get(option)
            if value is None and '=' in option:
                args = option.split('=', 1)
            info = ('%s=%s' % (option, value), 'Info')
        if len(args) == 2:
            if '|' in args[0]:
                plugin_name, section = args[0].split('|')[:2]
                if not section:
                    section = plugin_name
                option = args[1]
                if plugin_name not in self.core.plugin_manager.plugins:
                    file_name = self.core.plugin_manager.plugins_conf_dir / (
                        plugin_name + '.cfg')
                    plugin_config = PluginConfig(file_name, plugin_name)
                else:
                    plugin_config = self.core.plugin_manager.plugins[
                        plugin_name].config
                value = plugin_config.get(option, default='', section=section)
                info = ('%s=%s' % (option, value), 'Info')
            else:
                possible_section = args[0]
                if config.has_section(possible_section):
                    section = possible_section
                    option = args[1]
                    value = config.get(option, section=section)
                    info = ('%s=%s' % (option, value), 'Info')
                else:
                    option = args[0]
                    value = args[1]
                    info = config.set_and_save(option, value)
                    self.core.trigger_configuration_change(option, value)
        elif len(args) == 3:
            if '|' in args[0]:
                plugin_name, section = args[0].split('|')[:2]
                if not section:
                    section = plugin_name
                option = args[1]
                value = args[2]
                if plugin_name not in self.core.plugin_manager.plugins:
                    file_name = self.core.plugin_manager.plugins_conf_dir / (
                        plugin_name + '.cfg')
                    plugin_config = PluginConfig(file_name, plugin_name)
                else:
                    plugin_config = self.core.plugin_manager.plugins[
                        plugin_name].config
                info = plugin_config.set_and_save(option, value, section)
            else:
                if args[0] == '.':
                    name = safeJID(self.core.tabs.current_tab.name).bare
                    if not name:
                        self.core.information(
                            'Invalid tab to use the "." argument.', 'Error')
                        return
                    section = name
                else:
                    section = args[0]
                option = args[1]
                value = args[2]
                info = config.set_and_save(option, value, section)
                self.core.trigger_configuration_change(option, value)
        elif len(args) > 3:
            return self.help('set')
        self.core.information(*info)

    @command_args_parser.quoted(1, 2)
    def set_default(self, args):
        """
        /set_default [section] <option>
        """
        if len(args) == 1:
            option = args[0]
            section = 'Poezio'
        elif len(args) == 2:
            section = args[0]
            option = args[1]
        else:
            return self.help('set_default')

        default_config = DEFAULT_CONFIG.get(section, tuple())
        if option not in default_config:
            info = ("Option %s has no default value" % (option), "Error")
            return self.core.information(*info)
        self.set('%s %s %s' % (section, option, default_config[option]))

    @command_args_parser.quoted(1)
    def toggle(self, args):
        """
        /toggle <option>
        shortcut for /set <option> toggle
        """
        if args is None:
            return self.help('toggle')

        if args[0]:
            self.set('%s toggle' % args[0])

    @command_args_parser.quoted(1, 1)
    def server_cycle(self, args):
        """
        Do a /cycle on each room of the given server.
        If none, do it on the current tab
        """
        tab = self.core.tabs.current_tab
        message = ""
        if args:
            domain = args[0]
            if len(args) == 2:
                message = args[1]
        else:
            if isinstance(tab, tabs.MucTab):
                domain = safeJID(tab.name).domain
            else:
                return self.core.information("No server specified", "Error")
        for tab in self.core.get_tabs(tabs.MucTab):
            if tab.name.endswith(domain):
                tab.leave_room(message)
                tab.join()

    @command_args_parser.quoted(1)
    def last_activity(self, args):
        """
        /last_activity <jid>
        """

        def callback(iq):
            "Callback for the last activity"
            if iq['type'] != 'result':
                if iq['error']['type'] == 'auth':
                    self.core.information(
                        'You are not allowed to see the '
                        'activity of this contact.', 'Error')
                else:
                    self.core.information('Error retrieving the activity',
                                          'Error')
                return
            seconds = iq['last_activity']['seconds']
            status = iq['last_activity']['status']
            from_ = iq['from']
            if not safeJID(from_).user:
                msg = 'The uptime of %s is %s.' % (
                    from_, common.parse_secs_to_str(seconds))
            else:
                msg = 'The last activity of %s was %s ago%s' % (
                    from_, common.parse_secs_to_str(seconds),
                    (' and his/her last status was %s' % status)
                    if status else '')
            self.core.information(msg, 'Info')

        if args is None:
            return self.help('last_activity')
        jid = safeJID(args[0])
        self.core.xmpp.plugin['xep_0012'].get_last_activity(
            jid, callback=callback)

    @command_args_parser.quoted(0, 2)
    def mood(self, args):
        """
        /mood [<mood> [text]]
        """
        if not args:
            return self.core.xmpp.plugin['xep_0107'].stop()

        mood = args[0]
        if mood not in pep.MOODS:
            return self.core.information(
                '%s is not a correct value for a mood.' % mood, 'Error')
        if len(args) == 2:
            text = args[1]
        else:
            text = None
        self.core.xmpp.plugin['xep_0107'].publish_mood(
            mood, text, callback=dumb_callback)

    @command_args_parser.quoted(0, 3)
    def activity(self, args):
        """
        /activity [<general> [specific] [text]]
        """
        length = len(args)
        if not length:
            return self.core.xmpp.plugin['xep_0108'].stop()

        general = args[0]
        if general not in pep.ACTIVITIES:
            return self.core.information(
                '%s is not a correct value for an activity' % general, 'Error')
        specific = None
        text = None
        if length == 2:
            if args[1] in pep.ACTIVITIES[general]:
                specific = args[1]
            else:
                text = args[1]
        elif length == 3:
            specific = args[1]
            text = args[2]
        if specific and specific not in pep.ACTIVITIES[general]:
            return self.core.information(
                '%s is not a correct value '
                'for an activity' % specific, 'Error')
        self.core.xmpp.plugin['xep_0108'].publish_activity(
            general, specific, text, callback=dumb_callback)

    @command_args_parser.quoted(0, 2)
    def gaming(self, args):
        """
        /gaming [<game name> [server address]]
        """
        if not args:
            return self.core.xmpp.plugin['xep_0196'].stop()

        name = args[0]
        if len(args) > 1:
            address = args[1]
        else:
            address = None
        return self.core.xmpp.plugin['xep_0196'].publish_gaming(
            name=name, server_address=address, callback=dumb_callback)

    @command_args_parser.quoted(2, 1, [None])
    def invite(self, args):
        """/invite <to> <room> [reason]"""

        if args is None:
            return self.help('invite')

        reason = args[2]
        to = safeJID(args[0])
        room = safeJID(args[1]).bare
        self.core.invite(to.full, room, reason=reason)
        self.core.information('Invited %s to %s' % (to.bare, room), 'Info')

    @command_args_parser.quoted(1, 1, [''])
    def decline(self, args):
        """/decline <room@server.tld> [reason]"""
        if args is None:
            return self.help('decline')
        jid = safeJID(args[0])
        if jid.bare not in self.core.pending_invites:
            return
        reason = args[1]
        del self.core.pending_invites[jid.bare]
        self.core.xmpp.plugin['xep_0045'].decline_invite(
            jid.bare, self.core.pending_invites[jid.bare], reason)


### Commands without a completion in this class ###

    @command_args_parser.ignored
    def invitations(self):
        """/invitations"""
        build = ""
        for invite in self.core.pending_invites:
            build += "%s by %s" % (
                invite, safeJID(self.core.pending_invites[invite]).bare)
        if self.core.pending_invites:
            build = "You are invited to the following rooms:\n" + build
        else:
            build = "You do not have any pending invitations."
        self.core.information(build, 'Info')

    @command_args_parser.quoted(0, 1, [None])
    def quit(self, args):
        """
        /quit [message]
        """
        if not self.core.xmpp.is_connected():
            self.core.exit()
            return

        msg = args[0]
        if config.get('enable_user_mood'):
            self.core.xmpp.plugin['xep_0107'].stop()
        if config.get('enable_user_activity'):
            self.core.xmpp.plugin['xep_0108'].stop()
        if config.get('enable_user_gaming'):
            self.core.xmpp.plugin['xep_0196'].stop()
        self.core.save_config()
        self.core.plugin_manager.disable_plugins()
        self.core.disconnect(msg)
        self.core.xmpp.add_event_handler(
            "disconnected", self.core.exit, disposable=True)

    @command_args_parser.quoted(0, 1, [''])
    def destroy_room(self, args):
        """
        /destroy_room [JID]
        """
        room = safeJID(args[0]).bare
        if room:
            muc.destroy_room(self.core.xmpp, room)
        elif isinstance(self.core.tabs.current_tab,
                        tabs.MucTab) and not args[0]:
            muc.destroy_room(self.core.xmpp,
                             self.core.tabs.current_tab.general_jid)
        else:
            self.core.information('Invalid JID: "%s"' % args[0], 'Error')

    @command_args_parser.quoted(1, 1, [''])
    def bind(self, args):
        """
        Bind a key.
        """
        if args is None:
            return self.help('bind')

        if not config.silent_set(args[0], args[1], section='bindings'):
            self.core.information('Unable to write in the config file',
                                  'Error')

        if args[1]:
            self.core.information('%s is now bound to %s' % (args[0], args[1]),
                                  'Info')
        else:
            self.core.information(
                '%s is now reset to the default binding' % args[0], 'Info')

    @command_args_parser.raw
    def rawxml(self, args):
        """
        /rawxml <xml stanza>
        """

        if not args:
            return

        stanza = args
        try:
            stanza = StanzaBase(self.core.xmpp, xml=ET.fromstring(stanza))
            if stanza.xml.tag == 'iq' and stanza.xml.attrib.get('type') in (
                    'get', 'set'):
                iq_id = stanza.xml.attrib.get('id')
                if not iq_id:
                    iq_id = self.core.xmpp.new_id()
                    stanza['id'] = iq_id

                def iqfunc(iq):
                    "handler for an iq reply"
                    self.core.information(str(iq), 'Iq')
                    self.core.xmpp.remove_handler('Iq %s' % iq_id)

                self.core.xmpp.register_handler(
                    Callback('Iq %s' % iq_id, StanzaPath('iq@id=%s' % iq_id),
                             iqfunc))
            stanza.send()
        except:
            self.core.information('Could not send custom stanza', 'Error')
            log.debug(
                '/rawxml: Could not send custom stanza (%s)',
                repr(stanza),
                exc_info=True)

    @command_args_parser.quoted(1, 256)
    def load(self, args):
        """
        /load <plugin> [<otherplugin> …]
        # TODO: being able to load more than 256 plugins at once, hihi.
        """
        for plugin in args:
            self.core.plugin_manager.load(plugin)

    @command_args_parser.quoted(1, 256)
    def unload(self, args):
        """
        /unload <plugin> [<otherplugin> …]
        """
        for plugin in args:
            self.core.plugin_manager.unload(plugin)

    @command_args_parser.ignored
    def plugins(self):
        """
        /plugins
        """
        self.core.information(
            "Plugins currently in use: %s" % repr(
                list(self.core.plugin_manager.plugins.keys())), 'Info')

    @command_args_parser.quoted(1, 1)
    def message(self, args):
        """
        /message <jid> [message]
        """
        if args is None:
            return self.help('message')
        jid = safeJID(args[0])
        if not jid.user and not jid.domain and not jid.resource:
            return self.core.information('Invalid JID.', 'Error')
        tab = self.core.get_conversation_by_jid(
            jid.full, False, fallback_barejid=False)
        muc = self.core.tabs.by_name_and_class(jid.bare, tabs.MucTab)
        if not tab and not muc:
            tab = self.core.open_conversation_window(jid.full, focus=True)
        elif muc:
            if jid.resource:
                tab = self.core.tabs.by_name_and_class(jid.full,
                                                       tabs.PrivateTab)
                if tab:
                    self.core.focus_tab(tab)
                else:
                    tab = self.core.open_private_window(jid.bare, jid.resource)
            else:
                tab = muc
        else:
            self.core.focus_tab(tab)
        if len(args) == 2:
            tab.command_say(args[1])

    @command_args_parser.ignored
    def xml_tab(self):
        """/xml_tab"""
        xml_tab = self.core.focus_tab_named('XMLTab', tabs.XMLTab)
        if not xml_tab:
            tab = tabs.XMLTab(self.core)
            self.core.add_tab(tab, True)
            self.core.xml_tab = tab

    @command_args_parser.quoted(1)
    def adhoc(self, args):
        if not args:
            return self.help('ad-hoc')
        jid = safeJID(args[0])
        list_tab = tabs.AdhocCommandsListTab(self.core, jid)
        self.core.add_tab(list_tab, True)
        cb = list_tab.on_list_received
        self.core.xmpp.plugin['xep_0050'].get_commands(
            jid=jid, local=False, callback=cb)

    @command_args_parser.ignored
    def self_(self):
        """
        /self
        """
        status = self.core.get_status()
        show, message = status.show, status.message
        nick = self.core.own_nick
        jid = self.core.xmpp.boundjid.full
        info = ('Your JID is %s\nYour current status is "%s" (%s)'
                '\nYour default nickname is %s\nYou are running poezio %s' %
                (jid, message if message else '', show
                 if show else 'available', nick, config_opts.version))
        self.core.information(info, 'Info')

    @command_args_parser.ignored
    def reload(self):
        """
        /reload
        """
        self.core.reload_config()


def dumb_callback(*args, **kwargs):
    "mock callback"
