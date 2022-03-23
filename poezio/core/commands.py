"""
Global commands which are to be linked to the Core class
"""

import asyncio
from urllib.parse import unquote
from xml.etree import ElementTree as ET
from typing import List, Optional, Tuple
import logging

from slixmpp import JID, InvalidJID
from slixmpp.exceptions import XMPPError, IqError, IqTimeout
from slixmpp.xmlstream.xmlstream import NotConnectedError
from slixmpp.xmlstream.stanzabase import StanzaBase
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import StanzaPath

from poezio import common, config as config_module, tabs, multiuserchat as muc
from poezio.bookmarks import Bookmark
from poezio.config import config, DEFAULT_CONFIG
from poezio.contact import Contact, Resource
from poezio.decorators import deny_anonymous
from poezio.plugin import PluginConfig
from poezio.roster import roster
from poezio.theming import dump_tuple, get_theme
from poezio.decorators import command_args_parser
from poezio.core.structs import Command, POSSIBLE_SHOW


log = logging.getLogger(__name__)


class CommandCore:
    def __init__(self, core):
        self.core = core

    @command_args_parser.ignored
    def rotate_rooms_left(self, args=None):
        self.core.rotate_rooms_left()

    @command_args_parser.ignored
    def rotate_rooms_right(self, args=None):
        self.core.rotate_rooms_right()

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
                muc.change_show(self.core.xmpp, tab.jid, tab.own_nick, show,
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
            jid = self.core.tabs.current_tab.jid
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

    @command_args_parser.quoted(1)
    def wup(self, args):
        """
        /wup <prefix of name>
        """
        if args is None:
            return self.help('wup')

        prefix = args[0]
        _, match = self.core.tabs.find_by_unique_prefix(prefix)
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
    def list(self, args: List[str]) -> None:
        """
        /list [server]
        Opens a MucListTab containing the list of the room in the specified server
        """
        if args is None:
            return self.help('list')
        elif args:
            try:
                jid = JID(args[0])
            except InvalidJID:
                return self.core.information('Invalid server %r' % jid, 'Error')
        else:
            if not isinstance(self.core.tabs.current_tab, tabs.MucTab):
                return self.core.information('Please provide a server',
                                             'Error')
            jid = self.core.tabs.current_tab.jid
        if jid is None or not jid.domain:
            return None
        asyncio.create_task(
            self._list_async(jid)
        )

    async def _list_async(self, jid: JID):
        jid = JID(jid.domain)
        list_tab = tabs.MucListTab(self.core, jid)
        self.core.add_tab(list_tab, True)
        iq = await self.core.xmpp.plugin['xep_0030'].get_items(jid=jid)
        list_tab.on_muc_list_item_received(iq)

    @command_args_parser.quoted(1)
    async def version(self, args):
        """
        /version <jid>
        """
        if args is None:
            return self.help('version')
        try:
            jid = JID(args[0])
        except InvalidJID:
            return self.core.information(
                'Invalid JID for /version: %s' % args[0],
                'Error'
            )
        if jid.resource or jid not in roster or not roster[jid].resources:
            iq = await self.core.xmpp.plugin['xep_0092'].get_version(jid)
            self.core.handler.on_version_result(iq)
        elif jid in roster:
            for resource in roster[jid].resources:
                iq = await self.core.xmpp.plugin['xep_0092'].get_version(
                    resource.jid
                )
                self.core.handler.on_version_result(iq)

    def _empty_join(self):
        tab = self.core.tabs.current_tab
        if not isinstance(tab, (tabs.MucTab, tabs.PrivateTab)):
            return (None, None)
        room = tab.jid.bare
        nick = tab.own_nick
        return (room, nick)

    def _parse_join_jid(self, jid_string: str) -> Tuple[Optional[str], Optional[str]]:
        # we try to join a server directly
        server_root = False
        if jid_string.startswith('xmpp:') and jid_string.endswith('?join'):
            jid_string = unquote(jid_string[5:-5])
        try:
            if jid_string.startswith('@'):
                server_root = True
                info = JID(jid_string[1:])
            else:
                info = JID(jid_string)
                server_root = False
        except InvalidJID:
            info = JID('')

        set_nick: Optional[str] = ''
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
                room = tab.jid.bare
                if not set_nick:
                    set_nick = tab.own_nick
        else:
            room = info.bare
            # no server is provided, like "/join hello":
            # use the server of the current room if available
            # check if the current room's name has a server
            if room.find('@') == -1 and not server_root:
                tab = self.core.tabs.current_tab
                if isinstance(tab, tabs.MucTab) and tab.jid.domain:
                    room += '@%s' % tab.jid.domain
        return (room, set_nick)

    @command_args_parser.quoted(0, 2)
    async def join(self, args):
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

        # Has the nick been specified explicitely when joining
        config_nick = False
        if nick == '':
            config_nick = True
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

        if config.getbool('synchronise_open_rooms') and room not in self.core.bookmarks:
            method = 'remote' if config.getbool(
                'use_remote_bookmarks') else 'local'
            await self._add_bookmark(
                room=room,
                nick=nick if not config_nick else None,
                autojoin=True,
                password=password,
                method=method,
            )

        if tab == self.core.tabs.current_tab:
            tab.refresh()
            self.core.doupdate()

    @command_args_parser.quoted(0, 2)
    def bookmark_local(self, args):
        """
        /bookmark_local [room][/nick] [password]
        """
        tab = self.core.tabs.current_tab
        if not args and not isinstance(tab, tabs.MucTab):
            return

        room, nick = self._parse_join_jid(args[0] if args else '')
        password = args[1] if len(args) > 1 else None

        if not room:
            room = tab.jid.bare
        if password is None and tab.password is not None:
            password = tab.password

        asyncio.create_task(
            self._add_bookmark(
                room=room,
                nick=nick,
                autojoin=True,
                password=password,
                method='local',
            )
        )

    @command_args_parser.quoted(0, 3)
    def bookmark(self, args):
        """
        /bookmark [room][/nick] [autojoin] [password]
        """
        tab = self.core.tabs.current_tab
        if not args and not isinstance(tab, tabs.MucTab):
            return
        room, nick = self._parse_join_jid(args[0] if args else '')
        password = args[2] if len(args) > 2 else None

        method = 'remote' if config.getbool('use_remote_bookmarks') else 'local'
        autojoin = (method == 'local' or
                    (len(args) > 1 and args[1].lower() == 'true'))

        if not room:
            room = tab.jid.bare
        if password is None and tab.password is not None:
            password = tab.password

        asyncio.create_task(
            self._add_bookmark(room, nick, autojoin, password, method)
        )

    async def _add_bookmark(
        self,
        room: str,
        nick: Optional[str],
        autojoin: bool,
        password: str,
        method: str,
    ) -> None:
        '''
        Adds a bookmark.

        Args:
            room: room Jid.
            nick: optional nick. Will always be added to the bookmark if
                specified. This takes precedence over tab.own_nick which takes
                precedence over core.own_nick (global config).
            autojoin: set the bookmark to join automatically.
            password: room password.
            method: 'local' or 'remote'.
        '''


        if room == '*':
            return await self._add_wildcard_bookmarks(method)

        # Once we found which room to bookmark, find corresponding tab if it
        # exists and fill nickname if none was specified and not default.
        tab = self.core.tabs.by_name_and_class(room, tabs.MucTab)
        if tab and isinstance(tab, tabs.MucTab) and \
           tab.joined and tab.own_nick != self.core.own_nick:
            nick = nick or tab.own_nick

        # Validate / Normalize
        try:
            if not nick:
                jid = JID(room)
            else:
                jid = JID('{}/{}'.format(room, nick))
            room = jid.bare
            nick = jid.resource or None
        except InvalidJID:
            self.core.information(f'Invalid address for bookmark: {room}/{nick}', 'Error')
            return

        bookmark = self.core.bookmarks[room]
        if bookmark is None:
            bookmark = Bookmark(room)
            self.core.bookmarks.append(bookmark)
        bookmark.method = method
        bookmark.autojoin = autojoin
        if nick:
            bookmark.nick = nick
        if password:
            bookmark.password = password

        self.core.bookmarks.save_local()
        try:
            result = await self.core.bookmarks.save_remote(
                self.core.xmpp,
            )
            self.core.handler.on_bookmark_result(result)
        except (IqError, IqTimeout) as iq:
            self.core.handler.on_bookmark_result(iq)

    async def _add_wildcard_bookmarks(self, method):
        new_bookmarks = []
        for tab in self.core.get_tabs(tabs.MucTab):
            bookmark = self.core.bookmarks[tab.jid.bare]
            if not bookmark:
                bookmark = Bookmark(tab.jid.bare, autojoin=True, method=method)
                new_bookmarks.append(bookmark)
            else:
                bookmark.method = method
                new_bookmarks.append(bookmark)
                self.core.bookmarks.remove(bookmark)
        new_bookmarks.extend(self.core.bookmarks.bookmarks)
        self.core.bookmarks.set(new_bookmarks)
        self.core.bookmarks.save_local()
        try:
            iq = await self.core.bookmarks.save_remote(self.core.xmpp)
            self.core.handler.on_bookmark_result(iq)
        except IqError as iq:
            self.core.handler.on_bookmark_result(iq)

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
        jid = None
        if not args:
            tab = self.core.tabs.current_tab
            if isinstance(tab, tabs.MucTab):
                jid = tab.jid.bare
        else:
            jid = args[0]

        asyncio.create_task(
            self._remove_bookmark_routine(jid)
        )

    async def _remove_bookmark_routine(self, jid: str):
        """Asynchronously remove a bookmark"""
        if self.core.bookmarks[jid]:
            self.core.bookmarks.remove(jid)
            try:
                await self.core.bookmarks.save(self.core.xmpp)
                self.core.information('Bookmark deleted', 'Info')
            except (IqError, IqTimeout):
                self.core.information('Error while deleting the bookmark',
                                      'Error')
        else:
            self.core.information('No bookmark to remove', 'Info')

    @deny_anonymous
    @command_args_parser.quoted(0, 1)
    def accept(self, args):
        """
        Accept a JID. Authorize it AND subscribe to it
        """
        if not args:
            tab = self.core.tabs.current_tab
            RosterInfoTab = tabs.RosterInfoTab
            if not isinstance(tab, RosterInfoTab):
                return self.core.information('No JID specified', 'Error')
            else:
                item = tab.selected_row
                if isinstance(item, Contact):
                    jid = item.bare_jid
                else:
                    return self.core.information('No subscription to accept', 'Warning')
        else:
            try:
                jid = JID(args[0]).bare
            except InvalidJID:
                return self.core.information('Invalid JID for /accept: %s' % args[0], 'Error')
        jid = JID(jid)
        nodepart = jid.user
        # crappy transports putting resources inside the node part
        if '\\2f' in nodepart:
            jid.user = nodepart.split('\\2f')[0]
        contact = roster[jid]
        if contact is None:
            return self.core.information('No subscription to accept', 'Warning')
        contact.pending_in = False
        roster.modified()
        self.core.xmpp.send_presence(pto=jid, ptype='subscribed')
        self.core.xmpp.client_roster.send_last_presence()
        if contact.subscription in ('from',
                                    'none') and not contact.pending_out:
            self.core.xmpp.send_presence(
                pto=jid, ptype='subscribe', pnick=self.core.own_nick)
        self.core.information('%s is now authorized' % jid, 'Roster')

    @deny_anonymous
    @command_args_parser.quoted(1)
    def add(self, args):
        """
        Add the specified JID to the roster, and automatically
        accept the reverse subscription
        """
        if args is None:
            tab = self.core.tabs.current_tab
            ConversationTab = tabs.ConversationTab
            if isinstance(tab, ConversationTab):
                jid = tab.general_jid
                if jid in roster and roster[jid].subscription in ('to', 'both'):
                    return self.core.information('Already subscribed.', 'Roster')
                roster.add(jid)
                roster.modified()
                return self.core.information('%s was added to the roster' % jid, 'Roster')
            else:
                return self.core.information('No JID specified', 'Error')
        try:
            jid = JID(args[0]).bare
        except InvalidJID:
            return self.core.information('Invalid JID for /add: %s' % args[0], 'Error')
        if jid in roster and roster[jid].subscription in ('to', 'both'):
            return self.core.information('Already subscribed.', 'Roster')
        roster.add(jid)
        roster.modified()
        self.core.information('%s was added to the roster' % jid, 'Roster')

    @deny_anonymous
    @command_args_parser.quoted(0, 1)
    def deny(self, args):
        """
        /deny [jid]
        Denies a JID from our roster
        """
        jid = None
        if not args:
            tab = self.core.tabs.current_tab
            if isinstance(tab, tabs.RosterInfoTab):
                item = tab.roster_win.selected_row
                if isinstance(item, Contact):
                    jid = item.bare_jid
        else:
            try:
                jid = JID(args[0]).bare
            except InvalidJID:
                return self.core.information('Invalid JID for /deny: %s' % args[0], 'Error')
            if jid not in [jid for jid in roster.jids()]:
                jid = None
        if jid is None:
            self.core.information('No subscription to deny', 'Warning')
            return

        contact = roster[jid]
        if contact:
            contact.unauthorize()
            self.core.information('Subscription to %s was revoked' % jid,
                                  'Roster')

    @deny_anonymous
    @command_args_parser.quoted(0, 1)
    def remove(self, args):
        """
        Remove the specified JID from the roster. i.e.: unsubscribe
        from its presence, and cancel its subscription to our.
        """
        jid = None
        if args:
            try:
                jid = JID(args[0]).bare
            except InvalidJID:
                return self.core.information('Invalid JID for /remove: %s' % args[0], 'Error')
        else:
            tab = self.core.tabs.current_tab
            if isinstance(tab, tabs.RosterInfoTab):
                item = tab.roster_win.selected_row
                if isinstance(item, Contact):
                    jid = item.bare_jid
        if jid is None:
            self.core.information('No roster item to remove', 'Error')
            return
        roster.remove(jid)
        del roster[jid]

    @command_args_parser.ignored
    def command_reconnect(self):
        """
        /reconnect
        """
        if self.core.xmpp.is_connected():
            self.core.disconnect(reconnect=True)
        else:
            self.core.xmpp.start()

    @command_args_parser.quoted(0, 3)
    def set(self, args):
        """
        /set [module|][section] <option> [value]
        """
        if len(args) == 3 and args[1] == '=':
            args = [args[0], args[2]]
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
                    if isinstance(option_name, str) and \
                        'password' in option_name and 'eval_password' not in option_name:
                        option_value = '********'
                    lines.append(
                        '%s\x19%s}=\x19o%s' %
                        (option_name, dump_tuple(
                            theme.COLOR_REVISIONS_MESSAGE), option_value))
            info = ('Current  options:\n%s' % '\n'.join(lines), 'Info')
        elif len(args) == 1:
            option = args[0]
            value = config.get(option)
            if isinstance(option, str) and \
                'password' in option and 'eval_password' not in option and value is not None:
                value = '********'
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
                if (not config.has_option(section='Poezio', option=possible_section)
                        and config.has_section(possible_section)):
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
                    name = self.core.tabs.current_tab.jid.bare
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
        If none, do it on the server of the current tab
        """
        tab = self.core.tabs.current_tab
        message = ""
        if args:
            try:
                domain = JID(args[0]).domain
            except InvalidJID:
                return self.core.information(
                    "Invalid server domain: %s" % args[0],
                    "Error"
                )
            if len(args) == 2:
                message = args[1]
        else:
            if isinstance(tab, tabs.MucTab):
                domain = tab.jid.domain
            else:
                return self.core.information("No server specified", "Error")
        for tab in self.core.get_tabs(tabs.MucTab):
            if tab.jid.domain == domain:
                tab.leave_room(message)
                tab.join()

    @command_args_parser.quoted(1)
    async def last_activity(self, args):
        """
        /last_activity <jid>
        """

        if args is None:
            return self.help('last_activity')
        try:
            jid = JID(args[0])
        except InvalidJID:
            return self.core.information('Invalid JID for /last_activity: %s' % args[0], 'Error')

        try:
            iq = await self.core.xmpp.plugin['xep_0012'].get_last_activity(jid)
        except IqError as error:
            if error.etype == 'auth':
                msg = 'You are not allowed to see the activity of %s' % jid
            else:
                msg = 'Error retrieving the activity of %s: %s' % (jid, error)
            return self.core.information(msg, 'Error')
        except IqTimeout:
            return self.core.information('Timeout while retrieving the last activity of %s' % jid, 'Error')

        seconds = iq['last_activity']['seconds']
        status = iq['last_activity']['status']
        from_ = iq['from']
        if not from_.user:
            msg = 'The uptime of %s is %s.' % (
                from_, common.parse_secs_to_str(seconds))
        else:
            msg = 'The last activity of %s was %s ago%s' % (
                from_, common.parse_secs_to_str(seconds),
                (' and their last status was %s' % status)
                if status else '')
        self.core.information(msg, 'Info')

    @command_args_parser.quoted(2, 1, [None])
    async def invite(self, args):
        """/invite <to> <room> [reason]"""

        if args is None:
            return self.help('invite')

        reason = args[2]
        try:
            to = JID(args[0])
        except InvalidJID:
            self.core.information('Invalid JID specified for invite: %s' % args[0], 'Error')
            return None
        try:
            room = JID(args[1]).bare
        except InvalidJID:
            self.core.information('Invalid room JID specified to invite: %s' % args[1], 'Error')
            return None
        result = await self.core.invite(to.full, room, reason=reason)
        if result:
            self.core.information('Invited %s to %s' % (to.bare, room), 'Info')

    @command_args_parser.quoted(1, 0)
    def impromptu(self, args: str) -> None:
        """/impromptu <jid> [<jid> ...]"""

        if args is None:
            return self.help('impromptu')

        jids = set()
        current_tab = self.core.tabs.current_tab
        if isinstance(current_tab, tabs.ConversationTab):
            jids.add(current_tab.general_jid)

        for jid in common.shell_split(' '.join(args)):
            try:
                bare = JID(jid).bare
            except InvalidJID:
                return self.core.information('Invalid JID for /impromptu: %s' % args[0], 'Error')
            jids.add(bare)

        asyncio.create_task(self.core.impromptu(jids))

    @command_args_parser.quoted(1, 1, [''])
    def decline(self, args):
        """/decline <room@server.tld> [reason]"""
        if args is None:
            return self.help('decline')
        try:
            jid = JID(args[0])
        except InvalidJID:
            return self.core.information('Invalid JID for /decline: %s' % args[0], 'Error')
        if jid.bare not in self.core.pending_invites:
            return
        reason = args[1]
        del self.core.pending_invites[jid.bare]
        self.core.xmpp.plugin['xep_0045'].decline_invite(
            jid.bare, self.core.pending_invites[jid.bare], reason)

    @command_args_parser.quoted(0, 1)
    def block(self, args: List[str]) -> None:
        """
        /block [jid]

        If a JID is specified, use it. Otherwise if in RosterInfoTab, use the
        selected JID, if in ConversationsTab use the Tab's JID.
        """

        jid = None
        if args:
            try:
                jid = JID(args[0])
            except InvalidJID:
                self.core.information('Invalid JID %s' % args, 'Error')
                return

        current_tab = self.core.tabs.current_tab
        if jid is None:
            if isinstance(current_tab, tabs.RosterInfoTab):
                roster_win = self.core.tabs.by_name_and_class(
                    'Roster',
                    tabs.RosterInfoTab,
                )
                item = roster_win.selected_row
                if isinstance(item, Contact):
                    jid = item.bare_jid
                elif isinstance(item, Resource):
                    jid = JID(item.jid)

            chattabs = (
                tabs.ConversationTab,
                tabs.StaticConversationTab,
                tabs.DynamicConversationTab,
            )
            if isinstance(current_tab, chattabs):
                jid = JID(current_tab.jid.bare)

        if jid is None:
            self.core.information('No specified JID to block', 'Error')
        else:
            asyncio.create_task(self._block_async(jid))

    async def _block_async(self, jid: JID):
        """Block a JID, asynchronously"""
        try:
            await self.core.xmpp.plugin['xep_0191'].block(jid)
            return self.core.information('Blocked %s.' % jid, 'Info')
        except (IqError, IqTimeout):
            return self.core.information(
                'Could not block %s.' % jid, 'Error',
            )

    @command_args_parser.quoted(0, 1)
    def unblock(self, args: List[str]) -> None:
        """
        /unblock [jid]
        """

        item = self.core.tabs.by_name_and_class(
            'Roster',
            tabs.RosterInfoTab,
        ).selected_row

        jid = None
        if args:
            try:
                jid = JID(args[0])
            except InvalidJID:
                self.core.information('Invalid JID %s' % args, 'Error')
                return

        current_tab = self.core.tabs.current_tab
        if jid is None:
            if isinstance(current_tab, tabs.RosterInfoTab):
                roster_win = self.core.tabs.by_name_and_class(
                    'Roster',
                    tabs.RosterInfoTab,
                )
                item = roster_win.selected_row
                if isinstance(item, Contact):
                    jid = item.bare_jid
                elif isinstance(item, Resource):
                    jid = JID(item.jid)

            chattabs = (
                tabs.ConversationTab,
                tabs.StaticConversationTab,
                tabs.DynamicConversationTab,
            )
            if isinstance(current_tab, chattabs):
                jid = JID(current_tab.jid.bare)

        if jid is not None:
            asyncio.create_task(
                self._unblock_async(jid)
            )
        else:
            self.core.information('No specified JID to unblock', 'Error')

    async def _unblock_async(self, jid: JID):
        """Unblock a JID, asynchrously"""
        try:
            await self.core.xmpp.plugin['xep_0191'].unblock(jid)
            return self.core.information('Unblocked %s.' % jid, 'Info')
        except (IqError, IqTimeout):
            return self.core.information('Could not unblock the contact.',
                                         'Error')

### Commands without a completion in this class ###

    @command_args_parser.ignored
    def invitations(self):
        """/invitations"""
        build = []
        for room, inviter in self.core.pending_invites.items():
            try:
                bare = JID(inviter).bare
            except InvalidJID:
                self.core.information(
                    f'Invalid JID found in /invitations: {inviter}',
                    'Error'
                )
            build.append(f'{room} by {bare}')
        if build:
            message = 'You are invited to the following rooms:\n' + ','.join(build)
        else:
            message = 'You do not have any pending invitations.'
        self.core.information(message, 'Info')

    @command_args_parser.quoted(0, 1, [None])
    def quit(self, args):
        """
        /quit [message]
        """
        if not self.core.xmpp.is_connected():
            self.core.exit()
            return

        msg = args[0]
        self.core.save_config()
        self.core.plugin_manager.disable_plugins()
        self.core.xmpp.add_event_handler(
            "disconnected", self.core.exit, disposable=True)
        self.core.disconnect(msg)

    @command_args_parser.quoted(0, 3, ['', '', ''])
    def destroy_room(self, args: List[str]):
        """
        /destroy_room [JID [reason [alternative room JID]]]
        """
        async def do_destroy(room: JID, reason: str, altroom: Optional[JID]):
            try:
                await self.core.xmpp['xep_0045'].destroy(room, reason, altroom)
            except (IqError, IqTimeout) as e:
                self.core.information('Unable to destroy room %s: %s' % (room, e), 'Info')
            else:
                self.core.information('Room %s destroyed' % room, 'Info')

        room: Optional[JID]
        if not args[0] and isinstance(self.core.tabs.current_tab, tabs.MucTab):
            room = self.core.tabs.current_tab.general_jid
        else:
            try:
                room = JID(args[0])
            except InvalidJID:
                room = None
            else:
                if room.resource:
                    room = None

        if room is None:
            self.core.information('Invalid room JID: "%s"' % args[0], 'Error')
            return

        reason = args[1]
        altroom = None
        if args[2]:
            try:
                altroom = JID(args[2])
            except InvalidJID:
                self.core.information('Invalid alternative room JID: "%s"' % args[2], 'Error')
                return

        asyncio.create_task(do_destroy(room, reason, altroom))

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
    def load(self, args: List[str]) -> None:
        """
        /load <plugin> [<otherplugin> …]
        # TODO: being able to load more than 256 plugins at once, hihi.
        """

        usage = '/load <plugin> [<otherplugin> …]'
        if not args:
            self.core.information(usage, 'Error')
            return

        for plugin in args:
            self.core.plugin_manager.load(plugin)

    @command_args_parser.quoted(1, 256)
    def unload(self, args):
        """
        /unload <plugin> [<otherplugin> …]
        """

        usage = '/unload <plugin> [<otherplugin> …]'
        if not args:
            self.core.information(usage, 'Error')
            return

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
    async def message(self, args):
        """
        /message <jid> [message]
        """
        if args is None:
            return self.help('message')
        try:
            jid = JID(args[0])
        except InvalidJID:
            return self.core.information('Invalid JID for /message: %s' % args[0], 'Error')
        if not jid.user and not jid.domain and not jid.resource:
            return self.core.information('Invalid JID.', 'Error')
        tab = self.core.get_conversation_by_jid(
            jid.full, False, fallback_barejid=False)
        muc = self.core.tabs.by_name_and_class(jid.bare, tabs.MucTab)
        if not tab and not muc:
            tab = self.core.open_conversation_window(JID(jid.full), focus=True)
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
            await tab.command_say(args[1])

    @command_args_parser.ignored
    def xml_tab(self):
        """/xml_tab"""
        xml_tab = self.core.focus_tab_named('XMLTab', tabs.XMLTab)
        if not xml_tab:
            tab = tabs.XMLTab(self.core)
            self.core.add_tab(tab, True)
            self.core.xml_tab = tab

    @command_args_parser.quoted(1)
    async def adhoc(self, args):
        if not args:
            return self.help('ad-hoc')
        try:
            jid = JID(args[0])
        except InvalidJID:
            return self.core.information(
                'Invalid JID for ad-hoc command: %s' % args[0],
                'Error',
            )
        list_tab = tabs.AdhocCommandsListTab(self.core, jid)
        self.core.add_tab(list_tab, True)
        iq = await self.core.xmpp.plugin['xep_0050'].get_commands(
            jid=jid,
            local=False
        )
        list_tab.on_list_received(iq)

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
                 if show else 'available', nick, self.core.custom_version))
        self.core.information(info, 'Info')

    @command_args_parser.ignored
    def reload(self):
        """
        /reload
        """
        self.core.reload_config()

    @command_args_parser.raw
    def debug(self, args):
        """/debug [filename]"""
        if not args.strip():
            config_module.setup_logging('')
            self.core.information('Debug logging disabled!', 'Info')
        elif args:
            config_module.setup_logging(args)
            self.core.information(f'Debug logging to {args} enabled!', 'Info')


def dumb_callback(*args, **kwargs):
    "mock callback"
