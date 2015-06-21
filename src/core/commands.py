"""
Global commands which are to be linked to the Core class
"""

import logging

log = logging.getLogger(__name__)

import os
from datetime import datetime
from xml.etree import cElementTree as ET

from slixmpp.xmlstream.stanzabase import StanzaBase
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import StanzaPath

import common
import fixes
import pep
import tabs
from bookmarks import Bookmark
from common import safeJID
from config import config, DEFAULT_CONFIG, options as config_opts
import multiuserchat as muc
from plugin import PluginConfig
from roster import roster
from theming import dump_tuple, get_theme
from decorators import command_args_parser

from . structs import Command, possible_show


@command_args_parser.quoted(0, 1)
def command_help(self, args):
    """
    /help [command_name]
    """
    if not args:
        color = dump_tuple(get_theme().COLOR_HELP_COMMANDS)
        acc = []
        buff = ['Global commands:']
        for command in self.commands:
            if isinstance(self.commands[command], Command):
                acc.append('  \x19%s}%s\x19o - %s' % (
                               color,
                               command,
                               self.commands[command].short))
            else:
                acc.append('  \x19%s}%s\x19o' % (color, command))
        acc = sorted(acc)
        buff.extend(acc)
        acc = []
        buff.append('Tab-specific commands:')
        commands = self.current_tab().commands
        for command in commands:
            if isinstance(commands[command], Command):
                acc.append('  \x19%s}%s\x19o - %s' % (
                                color,
                                command,
                                commands[command].short))
            else:
                acc.append('  \x19%s}%s\x19o' % (color, command))
        acc = sorted(acc)
        buff.extend(acc)

        msg = '\n'.join(buff)
        msg += "\nType /help <command_name> to know what each command does"
    else:
        command = args[0].lstrip('/').strip()

        if command in self.current_tab().commands:
            tup = self.current_tab().commands[command]
        elif command in self.commands:
            tup = self.commands[command]
        else:
            self.information('Unknown command: %s' % command, 'Error')
            return
        if isinstance(tup, Command):
            msg = 'Usage: /%s %s\n' % (command, tup.usage)
            msg += tup.desc
        else:
            msg = tup[1]
    self.information(msg, 'Help')

@command_args_parser.quoted(1)
def command_runkey(self, args):
    """
    /runkey <key>
    """
    def replace_line_breaks(key):
        "replace ^J with \n"
        if key == '^J':
            return '\n'
        return key
    if args is None:
        return self.command_help('runkey')
    char = args[0]
    func = self.key_func.get(char, None)
    if func:
        func()
    else:
        res = self.do_command(replace_line_breaks(char), False)
        if res:
            self.refresh_window()

@command_args_parser.quoted(1, 1, [None])
def command_status(self, args):
    """
    /status <status> [msg]
    """
    if args is None:
        return self.command_help('status')

    if not args[0] in possible_show.keys():
        return self.command_help('status')

    show = possible_show[args[0]]
    msg = args[1]

    pres = self.xmpp.make_presence()
    if msg:
        pres['status'] = msg
    pres['type'] = show
    self.events.trigger('send_normal_presence', pres)
    pres.send()
    current = self.current_tab()
    is_muctab = isinstance(current, tabs.MucTab)
    if is_muctab and current.joined and show in ('away', 'xa'):
        current.send_chat_state('inactive')
    for tab in self.tabs:
        if isinstance(tab, tabs.MucTab) and tab.joined:
            muc.change_show(self.xmpp, tab.name, tab.own_nick, show, msg)
        if hasattr(tab, 'directed_presence'):
            del tab.directed_presence
    self.set_status(show, msg)
    if is_muctab and current.joined and show not in ('away', 'xa'):
        current.send_chat_state('active')

@command_args_parser.quoted(1, 2, [None, None])
def command_presence(self, args):
    """
    /presence <JID> [type] [status]
    """
    if args is None:
        return self.command_help('presence')

    jid, type, status = args[0], args[1], args[2]
    if jid == '.' and isinstance(self.current_tab(), tabs.ChatTab):
        jid = self.current_tab().name
    if type == 'available':
        type = None
    try:
        pres = self.xmpp.make_presence(pto=jid, ptype=type, pstatus=status)
        self.events.trigger('send_normal_presence', pres)
        pres.send()
    except:
        self.information('Could not send directed presence', 'Error')
        log.debug('Could not send directed presence to %s', jid, exc_info=True)
        return
    tab = self.get_tab_by_name(jid)
    if tab:
        if type in ('xa', 'away'):
            tab.directed_presence = False
            chatstate = 'inactive'
        else:
            tab.directed_presence = True
            chatstate = 'active'
        if tab == self.current_tab():
            tab.send_chat_state(chatstate, True)
        if isinstance(tab, tabs.MucTab):
            for private in tab.privates:
                private.directed_presence = tab.directed_presence
            if self.current_tab() in tab.privates:
                self.current_tab().send_chat_state(chatstate, True)

@command_args_parser.quoted(1)
def command_theme(self, args=None):
    """/theme <theme name>"""
    if args is None:
        return self.command_help('theme')
    self.command_set('theme %s' % (args[0],))

@command_args_parser.quoted(1)
def command_win(self, args):
    """
    /win <number>
    """
    if args is None:
        return self.command_help('win')

    nb = args[0]
    try:
        nb = int(nb)
    except ValueError:
        pass
    if self.current_tab_nb == nb:
        return
    self.previous_tab_nb = self.current_tab_nb
    old_tab = self.current_tab()
    if isinstance(nb, int):
        if 0 <= nb < len(self.tabs):
            if not self.tabs[nb]:
                return
            self.current_tab_nb = nb
    else:
        matchs = []
        for tab in self.tabs:
            for name in tab.matching_names():
                if nb.lower() in name[1].lower():
                    matchs.append((name[0], tab))
                    self.current_tab_nb = tab.nb
        if not matchs:
            return
        tab = min(matchs, key=lambda m: m[0])[1]
        self.current_tab_nb = tab.nb
    old_tab.on_lose_focus()
    self.current_tab().on_gain_focus()
    self.refresh_window()

@command_args_parser.quoted(2)
def command_move_tab(self, args):
    """
    /move_tab old_pos new_pos
    """
    if args is None:
        return self.command_help('move_tab')

    current_tab = self.current_tab()
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
            for tab in self.tabs:
                if not old_tab and value == tab.name:
                    old_tab = tab
            if not old_tab:
                self.information("Tab %s does not exist" % args[0], "Error")
                return None
            ref = old_tab.nb
        return ref
    old = get_nb_from_value(args[0])
    new = get_nb_from_value(args[1])
    if new is None or old is None:
        return self.information('Unable to move the tab.', 'Info')
    result = self.insert_tab(old, new)
    if not result:
        self.information('Unable to move the tab.', 'Info')
    else:
        self.current_tab_nb = self.tabs.index(current_tab)
    self.refresh_window()

@command_args_parser.quoted(0, 1)
def command_list(self, args):
    """
    /list [server]
    Opens a MucListTab containing the list of the room in the specified server
    """
    if args is None:
        return self.command_help('list')
    elif args:
        server = safeJID(args[0]).server
    else:
        if not isinstance(self.current_tab(), tabs.MucTab):
            return self.information('Please provide a server', 'Error')
        server = safeJID(self.current_tab().name).server
    list_tab = tabs.MucListTab(server)
    self.add_tab(list_tab, True)
    cb = list_tab.on_muc_list_item_received
    self.xmpp.plugin['xep_0030'].get_items(jid=server,
                                           callback=cb)

@command_args_parser.quoted(1)
def command_version(self, args):
    """
    /version <jid>
    """
    def callback(res):
        "Callback for /version"
        if not res:
            return self.information('Could not get the software'
                                    ' version from %s' % jid,
                                    'Warning')
        version = '%s is running %s version %s on %s' % (
                        jid,
                        res.get('name') or 'an unknown software',
                        res.get('version') or 'unknown',
                        res.get('os') or 'an unknown platform')
        self.information(version, 'Info')

    if args is None:
        return self.command_help('version')

    jid = safeJID(args[0])
    if jid.resource or jid not in roster:
        fixes.get_version(self.xmpp, jid, callback=callback)
    elif jid in roster:
        for resource in roster[jid].resources:
            fixes.get_version(self.xmpp, resource.jid, callback=callback)
        else:
            fixes.get_version(self.xmpp, jid, callback=callback)

@command_args_parser.quoted(0, 2)
def command_join(self, args, histo_length=None):
    """
    /join [room][/nick] [password]
    """
    password = None
    if len(args) == 0:
        tab = self.current_tab()
        if not isinstance(tab, (tabs.MucTab, tabs.PrivateTab)):
            return
        room = safeJID(tab.name).bare
        nick = tab.own_nick
    else:
        if args[0].startswith('@'): # we try to join a server directly
            server_root = True
            info = safeJID(args[0][1:])
        else:
            info = safeJID(args[0])
            server_root = False
        if info == '' and len(args[0]) > 1 and args[0][0] == '/':
            nick = args[0][1:]
        elif info.resource == '':
            nick = self.own_nick
        else:
            nick = info.resource
        if info.bare == '':   # happens with /join /nickname, which is OK
            tab = self.current_tab()
            if not isinstance(tab, tabs.MucTab):
                return
            room = tab.name
            if nick == '':
                nick = tab.own_nick
        else:
            room = info.bare
            # no server is provided, like "/join hello":
            # use the server of the current room if available
            # check if the current room's name has a server
            if room.find('@') == -1 and not server_root:
                if isinstance(self.current_tab(), tabs.MucTab) and\
                        self.current_tab().name.find('@') != -1:
                    domain = safeJID(self.current_tab().name).domain
                    room += '@%s' % domain
                else:
                    room = args[0]
    room = room.lower()
    if room in self.pending_invites:
        del self.pending_invites[room]
    tab = self.get_tab_by_name(room, tabs.MucTab)
    if len(args) == 2:       # a password is provided
        password = args[1]
    if tab and tab.joined:       # if we are already in the room
        self.focus_tab_named(tab.name)
        if tab.own_nick == nick:
            self.information('/join: Nothing to do.', 'Info')
        else:
            tab.own_nick = nick
            tab.command_cycle('')
        return

    if room.startswith('@'):
        room = room[1:]
    current_status = self.get_status()
    if not histo_length:
        histo_length = config.get('muc_history_length')
        if histo_length == -1:
            histo_length = None
    if histo_length is not None:
        histo_length = str(histo_length)
    if password is None: # try to use a saved password
        password = config.get_by_tabname('password', room, fallback=False)
    if tab and not tab.joined:
        if tab.last_connection:
            if tab.last_connection is not None:
                delta = datetime.now() - tab.last_connection
                seconds = delta.seconds + delta.days * 24 * 3600
            else:
                seconds = 0
            seconds = int(seconds)
        else:
            seconds = 0
        # If we didn’t have a password by now (from a bookmark or the
        # explicit argument), just use the password that is stored in the
        # tab because of our last join
        if not password:
            password = tab.password
        muc.join_groupchat(self, room, nick, password,
                           histo_length,
                           current_status.message,
                           current_status.show,
                           seconds=seconds)
        # Store in the tab the password we used, for later use
        tab.password = password
    if not tab:
        self.open_new_room(room, nick, password=password)
        muc.join_groupchat(self, room, nick, password,
                           histo_length,
                           current_status.message,
                           current_status.show)
    else:
        tab.own_nick = nick
        tab.users = []
    if tab and tab.joined:
        self.enable_private_tabs(room)
        tab.state = "normal"
        if tab == self.current_tab():
            tab.refresh()
            self.doupdate()

@command_args_parser.quoted(0, 2)
def command_bookmark_local(self, args):
    """
    /bookmark_local [room][/nick] [password]
    """
    if not args and not isinstance(self.current_tab(), tabs.MucTab):
        return
    password = args[1] if len(args) > 1 else None
    jid = args[0] if args else None

    _add_bookmark(self, jid, True, password, 'local')

@command_args_parser.quoted(0, 3)
def command_bookmark(self, args):
    """
    /bookmark [room][/nick] [autojoin] [password]
    """
    if not args and not isinstance(self.current_tab(), tabs.MucTab):
        return
    jid = args[0] if args else ''
    password = args[2] if len(args) > 2 else None

    if not config.get('use_remote_bookmarks'):
        return _add_bookmark(self, jid, True, password, 'local')

    if len(args) > 1:
        autojoin = False if args[1].lower() != 'true' else True
    else:
        autojoin = True

    _add_bookmark(self, jid, autojoin, password, 'remote')

def _add_bookmark(self, jid, autojoin, password, method):
    nick = None
    if not jid:
        tab = self.current_tab()
        roomname = tab.name
        if tab.joined and tab.own_nick != self.own_nick:
            nick = tab.own_nick
        if password is None and tab.password is not None:
            password = tab.password
    elif jid == '*':
        return _add_wildcard_bookmarks(self, method)
    else:
        info = safeJID(jid)
        roomname, nick = info.bare, info.resource
        if roomname == '':
            if not isinstance(self.current_tab(), tabs.MucTab):
                return
            roomname = self.current_tab().name
    bookmark = self.bookmarks[roomname]
    if bookmark is None:
        bookmark = Bookmark(roomname)
        self.bookmarks.append(bookmark)
    bookmark.method = method
    bookmark.autojoin = autojoin
    if nick:
        bookmark.nick = nick
    if password:
        bookmark.password = password
    def callback(iq):
        if iq["type"] != "error":
            self.information('Bookmark added.', 'Info')
        else:
            self.information("Could not add the bookmarks.", "Info")
    self.bookmarks.save_local()
    self.bookmarks.save_remote(self.xmpp, callback)

def _add_wildcard_bookmarks(self, method):
    new_bookmarks = []
    for tab in self.get_tabs(tabs.MucTab):
        bookmark = self.bookmarks[tab.name]
        if not bookmark:
            bookmark = Bookmark(tab.name, autojoin=True,
                                method=method)
            new_bookmarks.append(bookmark)
        else:
            bookmark.method = method
            new_bookmarks.append(bookmark)
            self.bookmarks.remove(bookmark)
    new_bookmarks.extend(self.bookmarks.bookmarks)
    self.bookmarks.set(new_bookmarks)
    def _cb(iq):
        if iq["type"] != "error":
            self.information("Bookmarks saved.", "Info")
        else:
            self.information("Could not save the remote bookmarks.", "Info")
    self.bookmarks.save_local()
    self.bookmarks.save_remote(self.xmpp, _cb)

@command_args_parser.ignored
def command_bookmarks(self):
    """/bookmarks"""
    tab = self.get_tab_by_name('Bookmarks', tabs.BookmarksTab)
    old_tab = self.current_tab()
    if tab:
        self.current_tab_nb = tab.nb
    else:
        tab = tabs.BookmarksTab(self.bookmarks)
        self.tabs.append(tab)
        self.current_tab_nb = tab.nb
    old_tab.on_lose_focus()
    tab.on_gain_focus()
    self.refresh_window()

@command_args_parser.quoted(0, 1)
def command_remove_bookmark(self, args):
    """/remove_bookmark [jid]"""

    def cb(success):
        if success:
            self.information('Bookmark deleted', 'Info')
        else:
            self.information('Error while deleting the bookmark', 'Error')

    if not args:
        tab = self.current_tab()
        if isinstance(tab, tabs.MucTab) and self.bookmarks[tab.name]:
            self.bookmarks.remove(tab.name)
            self.bookmarks.save(self.xmpp, callback=cb)
        else:
            self.information('No bookmark to remove', 'Info')
    else:
        if self.bookmarks[args[0]]:
            self.bookmarks.remove(args[0])
            self.bookmarks.save(self.xmpp, callback=cb)
        else:
            self.information('No bookmark to remove', 'Info')

@command_args_parser.quoted(0, 3)
def command_set(self, args):
    """
    /set [module|][section] <option> [value]
    """
    if args is None or len(args) == 0:
        config_dict = config.to_dict()
        lines = []
        theme = get_theme()
        for section_name, section in config_dict.items():
            lines.append('\x19%(section_col)s}[%(section)s]\x19o' %
                    {
                        'section': section_name,
                        'section_col': dump_tuple(theme.COLOR_INFORMATION_TEXT),
                    })
            for option_name, option_value in section.items():
                lines.append('%s\x19%s}=\x19o%s' % (option_name,
                                                    dump_tuple(theme.COLOR_REVISIONS_MESSAGE),
                                                    option_value))
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
            if not plugin_name in self.plugin_manager.plugins:
                file_name = self.plugin_manager.plugins_conf_dir
                file_name = os.path.join(file_name, plugin_name + '.cfg')
                plugin_config = PluginConfig(file_name, plugin_name)
            else:
                plugin_config = self.plugin_manager.plugins[plugin_name].config
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
                self.trigger_configuration_change(option, value)
    elif len(args) == 3:
        if '|' in args[0]:
            plugin_name, section = args[0].split('|')[:2]
            if not section:
                section = plugin_name
            option = args[1]
            value = args[2]
            if not plugin_name in self.plugin_manager.plugins:
                file_name = self.plugin_manager.plugins_conf_dir
                file_name = os.path.join(file_name, plugin_name + '.cfg')
                plugin_config = PluginConfig(file_name, plugin_name)
            else:
                plugin_config = self.plugin_manager.plugins[plugin_name].config
            info = plugin_config.set_and_save(option, value, section)
        else:
            if args[0] == '.':
                name = safeJID(self.current_tab().name).bare
                if not name:
                    self.information('Invalid tab to use the "." argument.',
                                     'Error')
                    return
                section = name
            else:
                section = args[0]
            option = args[1]
            value = args[2]
            info = config.set_and_save(option, value, section)
            self.trigger_configuration_change(option, value)
    elif len(args) > 3:
        return self.command_help('set')
    self.information(*info)

@command_args_parser.quoted(1, 2)
def command_set_default(self, args):
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
        return self.command_help('set_default')

    default_config = DEFAULT_CONFIG.get(section, tuple())
    if option not in default_config:
        info = ("Option %s has no default value" % (option), "Error")
        return self.information(*info)
    self.command_set('%s %s %s' % (section, option, default_config[option]))

@command_args_parser.quoted(1)
def command_toggle(self, args):
    """
    /toggle <option>
    shortcut for /set <option> toggle
    """
    if args is None:
        return self.command_help('toggle')

    if args[0]:
        self.command_set('%s toggle' % args[0])

@command_args_parser.quoted(1, 1)
def command_server_cycle(self, args):
    """
    Do a /cycle on each room of the given server.
    If none, do it on the current tab
    """
    tab = self.current_tab()
    message = ""
    if args:
        domain = args[0]
        if len(args) == 2:
            message = args[1]
    else:
        if isinstance(tab, tabs.MucTab):
            domain = safeJID(tab.name).domain
        else:
            return self.information("No server specified", "Error")
    for tab in self.get_tabs(tabs.MucTab):
        if tab.name.endswith(domain):
            if tab.joined:
                muc.leave_groupchat(tab.core.xmpp,
                                    tab.name,
                                    tab.own_nick,
                                    message)
            tab.joined = False
            if tab.name == domain:
                self.command_join('"@%s/%s"' %(tab.name, tab.own_nick))
            else:
                self.command_join('"%s/%s"' %(tab.name, tab.own_nick))

@command_args_parser.quoted(1)
def command_last_activity(self, args):
    """
    /last_activity <jid>
    """
    def callback(iq):
        "Callback for the last activity"
        if iq['type'] != 'result':
            if iq['error']['type'] == 'auth':
                self.information('You are not allowed to see the '
                                 'activity of this contact.',
                                 'Error')
            else:
                self.information('Error retrieving the activity', 'Error')
            return
        seconds = iq['last_activity']['seconds']
        status = iq['last_activity']['status']
        from_ = iq['from']
        if not safeJID(from_).user:
            msg = 'The uptime of %s is %s.' % (
                    from_,
                    common.parse_secs_to_str(seconds))
        else:
            msg = 'The last activity of %s was %s ago%s' % (
                from_,
                common.parse_secs_to_str(seconds),
                (' and his/her last status was %s' % status) if status else '')
        self.information(msg, 'Info')

    if args is None:
        return self.command_help('last_activity')
    jid = safeJID(args[0])
    self.xmpp.plugin['xep_0012'].get_last_activity(jid,
                                                   callback=callback)

@command_args_parser.quoted(0, 2)
def command_mood(self, args):
    """
    /mood [<mood> [text]]
    """
    if not args:
        return self.xmpp.plugin['xep_0107'].stop()

    mood = args[0]
    if mood not in pep.MOODS:
        return self.information('%s is not a correct value for a mood.'
                                % mood,
                                'Error')
    if len(args) == 2:
        text = args[1]
    else:
        text = None
    self.xmpp.plugin['xep_0107'].publish_mood(mood, text,
                                              callback=dumb_callback)

@command_args_parser.quoted(0, 3)
def command_activity(self, args):
    """
    /activity [<general> [specific] [text]]
    """
    length = len(args)
    if not length:
        return self.xmpp.plugin['xep_0108'].stop()

    general = args[0]
    if general not in pep.ACTIVITIES:
        return self.information('%s is not a correct value for an activity'
                                    % general,
                                'Error')
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
        return self.information('%s is not a correct value '
                                'for an activity' % specific,
                                'Error')
    self.xmpp.plugin['xep_0108'].publish_activity(general, specific, text,
                                                  callback=dumb_callback)

@command_args_parser.quoted(0, 2)
def command_gaming(self, args):
    """
    /gaming [<game name> [server address]]
    """
    if not args:
        return self.xmpp.plugin['xep_0196'].stop()

    name = args[0]
    if len(args) > 1:
        address = args[1]
    else:
        address = None
    return self.xmpp.plugin['xep_0196'].publish_gaming(name=name,
                                                       server_address=address,
                                                       callback=dumb_callback)

@command_args_parser.quoted(2, 1, [None])
def command_invite(self, args):
    """/invite <to> <room> [reason]"""

    if args is None:
        return self.command_help('invite')

    reason = args[2]
    to = safeJID(args[0])
    room = safeJID(args[1]).bare
    self.invite(to.full, room, reason=reason)

@command_args_parser.quoted(1, 1, [''])
def command_decline(self, args):
    """/decline <room@server.tld> [reason]"""
    if args is None:
        return self.command_help('decline')
    jid = safeJID(args[0])
    if jid.bare not in self.pending_invites:
        return
    reason = args[1]
    del self.pending_invites[jid.bare]
    self.xmpp.plugin['xep_0045'].decline_invite(jid.bare,
                                                self.pending_invites[jid.bare],
                                                reason)

### Commands without a completion in this class ###

@command_args_parser.ignored
def command_invitations(self):
    """/invitations"""
    build = ""
    for invite in self.pending_invites:
        build += "%s by %s" % (invite,
                               safeJID(self.pending_invites[invite]).bare)
    if self.pending_invites:
        build = "You are invited to the following rooms:\n" + build
    else:
        build = "You do not have any pending invitations."
    self.information(build, 'Info')

@command_args_parser.quoted(0, 1, [None])
def command_quit(self, args):
    """
    /quit [message]
    """
    if not self.xmpp.is_connected():
        self.exit()
        return

    msg = args[0]
    if config.get('enable_user_mood'):
        self.xmpp.plugin['xep_0107'].stop()
    if config.get('enable_user_activity'):
        self.xmpp.plugin['xep_0108'].stop()
    if config.get('enable_user_gaming'):
        self.xmpp.plugin['xep_0196'].stop()
    self.save_config()
    self.plugin_manager.disable_plugins()
    self.disconnect(msg)
    self.xmpp.add_event_handler("disconnected", self.exit, disposable=True)

@command_args_parser.quoted(0, 1, [''])
def command_destroy_room(self, args):
    """
    /destroy_room [JID]
    """
    room = safeJID(args[0]).bare
    if room:
        muc.destroy_room(self.xmpp, room)
    elif isinstance(self.current_tab(), tabs.MucTab) and not args[0]:
        muc.destroy_room(self.xmpp, self.current_tab().general_jid)
    else:
        self.information('Invalid JID: "%s"' % args[0], 'Error')

@command_args_parser.quoted(1, 1, [''])
def command_bind(self, args):
    """
    Bind a key.
    """
    if args is None:
        return self.command_help('bind')

    if not config.silent_set(args[0], args[1], section='bindings'):
        self.information('Unable to write in the config file', 'Error')

    if args[1]:
        self.information('%s is now bound to %s' % (args[0], args[1]), 'Info')
    else:
        self.information('%s is now unbound' % args[0], 'Info')

@command_args_parser.raw
def command_rawxml(self, args):
    """
    /rawxml <xml stanza>
    """

    if not args:
        return

    stanza = args
    try:
        stanza = StanzaBase(self.xmpp, xml=ET.fromstring(stanza))
        if stanza.xml.tag == 'iq' and stanza.xml.attrib.get('type') in ('get', 'set'):
            iq_id = stanza.xml.attrib.get('id')
            if not iq_id:
                iq_id = self.xmpp.new_id()
                stanza['id'] = iq_id

            def iqfunc(iq):
                "handler for an iq reply"
                self.information('%s' % iq, 'Iq')
                self.xmpp.remove_handler('Iq %s' % iq_id)

            self.xmpp.register_handler(
                    Callback('Iq %s' % iq_id,
                        StanzaPath('iq@id=%s' % iq_id),
                        iqfunc
                        )
                    )
            log.debug('handler')
        log.debug('%s %s', stanza.xml.tag, stanza.xml.attrib)

        stanza.send()
    except:
        self.information('Could not send custom stanza', 'Error')
        log.debug('/rawxml: Could not send custom stanza (%s)',
                repr(stanza),
                exc_info=True)


@command_args_parser.quoted(1, 256)
def command_load(self, args):
    """
    /load <plugin> [<otherplugin> …]
    # TODO: being able to load more than 256 plugins at once, hihi.
    """
    for plugin in args:
        self.plugin_manager.load(plugin)

@command_args_parser.quoted(1, 256)
def command_unload(self, args):
    """
    /unload <plugin> [<otherplugin> …]
    """
    for plugin in args:
        self.plugin_manager.unload(plugin)

@command_args_parser.ignored
def command_plugins(self):
    """
    /plugins
    """
    self.information("Plugins currently in use: %s" %
                        repr(list(self.plugin_manager.plugins.keys())),
                     'Info')

@command_args_parser.quoted(1, 1)
def command_message(self, args):
    """
    /message <jid> [message]
    """
    if args is None:
        return self.command_help('message')
    jid = safeJID(args[0])
    if not jid.user and not jid.domain and not jid.resource:
        return self.information('Invalid JID.', 'Error')
    tab = self.get_conversation_by_jid(jid.full, False, fallback_barejid=False)
    muc = self.get_tab_by_name(jid.bare, typ=tabs.MucTab)
    if not tab and not muc:
        tab = self.open_conversation_window(jid.full, focus=True)
    elif muc:
        tab = self.get_tab_by_name(jid.full, typ=tabs.PrivateTab)
        if tab:
            self.focus_tab_named(tab.name)
        else:
            tab = self.open_private_window(jid.bare, jid.resource)
    else:
        self.focus_tab_named(tab.name)
    if len(args) == 2:
        tab.command_say(args[1])

@command_args_parser.ignored
def command_xml_tab(self):
    """/xml_tab"""
    xml_tab = self.focus_tab_named('XMLTab', tabs.XMLTab)
    if not xml_tab:
        tab = tabs.XMLTab()
        self.add_tab(tab, True)
        self.xml_tab = tab

@command_args_parser.quoted(1)
def command_adhoc(self, args):
    if not args:
        return self.command_help('ad-hoc')
    jid = safeJID(args[0])
    list_tab = tabs.AdhocCommandsListTab(jid)
    self.add_tab(list_tab, True)
    cb = list_tab.on_list_received
    self.xmpp.plugin['xep_0050'].get_commands(jid=jid, local=False,
                                              callback=cb)

@command_args_parser.ignored
def command_self(self):
    """
    /self
    """
    status = self.get_status()
    show, message = status.show, status.message
    nick = self.own_nick
    jid = self.xmpp.boundjid.full
    info = ('Your JID is %s\nYour current status is "%s" (%s)'
            '\nYour default nickname is %s\nYou are running poezio %s' % (
            jid,
            message if message else '',
            show if show else 'available',
            nick,
            config_opts.version))
    self.information(info, 'Info')


@command_args_parser.ignored
def command_reload(self):
    """
    /reload
    """
    self.reload_config()

def dumb_callback(*args, **kwargs):
    "mock callback"

