"""
Global commands which are to be linked to the Core class
"""

import logging

log = logging.getLogger(__name__)

import os
import sys
from datetime import datetime
from gettext import gettext as _
from xml.etree import cElementTree as ET

from sleekxmpp.xmlstream.stanzabase import StanzaBase
from sleekxmpp.xmlstream.handler import Callback
from sleekxmpp.xmlstream.matcher import StanzaPath

import bookmark
import common
import fixes
import pep
import tabs
import theming
from common import safeJID
from config import config, options as config_opts
import multiuserchat as muc
from roster import roster
from theming import dump_tuple, get_theme

from . structs import Command, possible_show


def command_help(self, arg):
    """
    /help <command_name>
    """
    args = arg.split()
    if not args:
        color = dump_tuple(get_theme().COLOR_HELP_COMMANDS)
        acc = []
        buff = ['Global commands:']
        for command in self.commands:
            if isinstance(self.commands[command], Command):
                acc.append('  \x19%s}%s\x19o - %s' % (color, command, self.commands[command].short))
            else:
                acc.append('  \x19%s}%s\x19o' % (color, command))
        acc = sorted(acc)
        buff.extend(acc)
        acc = []
        buff.append('Tab-specific commands:')
        commands = self.current_tab().commands
        for command in commands:
            if isinstance(commands[command], Command):
                acc.append('  \x19%s}%s\x19o - %s' % (color, command, commands[command].short))
            else:
                acc.append('  \x19%s}%s\x19o' % (color, command))
        acc = sorted(acc)
        buff.extend(acc)

        msg = '\n'.join(buff)
        msg += _("\nType /help <command_name> to know what each command does")
    if args:
        command = args[0].lstrip('/').strip()

        if command in self.current_tab().commands:
            tup = self.current_tab().commands[command]
        elif command in self.commands:
            tup = self.commands[command]
        else:
            self.information(_('Unknown command: %s') % command, 'Error')
            return
        if isinstance(tup, Command):
            msg = _('Usage: /%s %s\n' % (command, tup.usage))
            msg += tup.desc
        else:
            msg = tup[1]
    self.information(msg, 'Help')

def command_runkey(self, arg):
    """
    /runkey <key>
    """
    def replace_line_breaks(key):
        if key == '^J':
            return '\n'
        return key
    char = arg.strip()
    func = self.key_func.get(char, None)
    if func:
        func()
    else:
        res = self.do_command(replace_line_breaks(char), False)
        if res:
            self.refresh_window()

def command_status(self, arg):
    """
    /status <status> [msg]
    """
    args = common.shell_split(arg)
    if len(args) < 1:
        return
    if not args[0] in possible_show.keys():
        self.command_help('status')
        return
    show = possible_show[args[0]]
    if len(args) == 2:
        msg = args[1]
    else:
        msg = None
    pres = self.xmpp.make_presence()
    if msg:
        pres['status'] = msg
    pres['type'] = show
    self.events.trigger('send_normal_presence', pres)
    pres.send()
    current = self.current_tab()
    if isinstance(current, tabs.MucTab) and current.joined and show in ('away', 'xa'):
        current.send_chat_state('inactive')
    for tab in self.tabs:
        if isinstance(tab, tabs.MucTab) and tab.joined:
            muc.change_show(self.xmpp, tab.name, tab.own_nick, show, msg)
        if hasattr(tab, 'directed_presence'):
            del tab.directed_presence
    self.set_status(show, msg)
    if isinstance(current, tabs.MucTab) and current.joined and show not in ('away', 'xa'):
        current.send_chat_state('active')

def command_presence(self, arg):
    """
    /presence <JID> [type] [status]
    """
    args = common.shell_split(arg)
    if len(args) == 1:
        jid, type, status = args[0], None, None
    elif len(args) == 2:
        jid, type, status = args[0], args[1], None
    elif len(args) == 3:
        jid, type, status = args[0], args[1], args[2]
    else:
        return
    if jid == '.' and isinstance(self.current_tab(), tabs.ChatTab):
        jid = self.current_tab().get_name()
    if type == 'available':
        type = None
    try:
        pres = self.xmpp.make_presence(pto=jid, ptype=type, pstatus=status)
        self.events.trigger('send_normal_presence', pres)
        pres.send()
    except:
        self.information(_('Could not send directed presence'), 'Error')
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

def command_theme(self, arg=''):
    """/theme <theme name>"""
    args = arg.split()
    if args:
        self.command_set('theme %s' % (args[0],))
    warning = theming.reload_theme()
    if warning:
        self.information(warning, 'Warning')
    self.refresh_window()

def command_win(self, arg):
    """
    /win <number>
    """
    arg = arg.strip()
    if not arg:
        self.command_help('win')
        return
    try:
        nb = int(arg.split()[0])
    except ValueError:
        nb = arg
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

def command_move_tab(self, arg):
    """
    /move_tab old_pos new_pos
    """
    args = common.shell_split(arg)
    current_tab = self.current_tab()
    if len(args) != 2:
        return self.command_help('move_tab')
    def get_nb_from_value(value):
        ref = None
        try:
            ref = int(value)
        except ValueError:
            old_tab = None
            for tab in self.tabs:
                if not old_tab and value == tab.get_name():
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

def command_list(self, arg):
    """
    /list <server>
    Opens a MucListTab containing the list of the room in the specified server
    """
    arg = arg.split()
    if len(arg) > 1:
        return self.command_help('list')
    elif arg:
        server = safeJID(arg[0]).server
    else:
        if not isinstance(self.current_tab(), tabs.MucTab):
            return self.information('Please provide a server', 'Error')
        server = safeJID(self.current_tab().get_name()).server
    list_tab = tabs.MucListTab(server)
    self.add_tab(list_tab, True)
    self.xmpp.plugin['xep_0030'].get_items(jid=server, block=False, callback=list_tab.on_muc_list_item_received)

def command_version(self, arg):
    """
    /version <jid>
    """
    def callback(res):
        if not res:
            return self.information('Could not get the software version from %s' % (jid,), 'Warning')
        version = '%s is running %s version %s on %s' % (jid,
                                                         res.get('name') or _('an unknown software'),
                                                         res.get('version') or _('unknown'),
                                                         res.get('os') or _('an unknown platform'))
        self.information(version, 'Info')

    args = common.shell_split(arg)
    if len(args) < 1:
        return self.command_help('version')
    jid = safeJID(args[0])
    if jid.resource or jid not in roster:
        fixes.get_version(self.xmpp, jid, callback=callback)
    elif jid in roster:
        for resource in roster[jid].resources:
            fixes.get_version(self.xmpp, resource.jid, callback=callback)
        else:
            fixes.get_version(self.xmpp, jid, callback=callback)

def command_join(self, arg, histo_length=None):
    """
    /join [room][/nick] [password]
    """
    args = common.shell_split(arg)
    password = None
    if len(args) == 0:
        tab = self.current_tab()
        if not isinstance(tab, tabs.MucTab) and not isinstance(tab, tabs.PrivateTab):
            return
        room = safeJID(tab.get_name()).bare
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
            default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
            nick = config.get('default_nick', '')
            if nick == '':
                nick = default
        else:
            nick = info.resource
        if info.bare == '':   # happens with /join /nickname, which is OK
            tab = self.current_tab()
            if not isinstance(tab, tabs.MucTab):
                return
            room = tab.get_name()
            if nick == '':
                nick = tab.own_nick
        else:
            room = info.bare
            if room.find('@') == -1 and not server_root: # no server is provided, like "/join hello"
                # use the server of the current room if available
                # check if the current room's name has a server
                if isinstance(self.current_tab(), tabs.MucTab) and\
                        self.current_tab().get_name().find('@') != -1:
                    room += '@%s' % safeJID(self.current_tab().get_name()).domain
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
        histo_length = config.get('muc_history_length', 20)
        if histo_length == -1:
            histo_length = None
    if histo_length is not None:
        histo_length = str(histo_length)
    if password is None: # try to use a saved password
        password = config.get_by_tabname('password', None, room, fallback=False)
    if tab and not tab.joined:
        if tab.last_connection:
            delta = datetime.now() - tab.last_connection
            seconds = delta.seconds + delta.days * 24 * 3600 if tab.last_connection is not None else 0
            seconds = int(seconds)
        else:
            seconds = 0
        muc.join_groupchat(self, room, nick, password,
                           histo_length, current_status.message, current_status.show, seconds=seconds)
    if not tab:
        self.open_new_room(room, nick)
        muc.join_groupchat(self, room, nick, password,
                           histo_length, current_status.message, current_status.show)
    else:
        tab.own_nick = nick
        tab.users = []
    if tab and tab.joined:
        self.enable_private_tabs(room)
        tab.state = "normal"
        if tab == self.current_tab():
            tab.refresh()
            self.doupdate()

def command_bookmark_local(self, arg=''):
    """
    /bookmark_local [room][/nick] [password]
    """
    args = common.shell_split(arg)
    nick = None
    password = None
    if not args and not isinstance(self.current_tab(), tabs.MucTab):
        return
    if not args:
        tab = self.current_tab()
        roomname = tab.get_name()
        if tab.joined and tab.own_nick != self.own_nick:
            nick = tab.own_nick
    elif args[0] == '*':
        new_bookmarks = []
        for tab in self.get_tabs(tabs.MucTab):
            b = bookmark.get_by_jid(tab.get_name())
            if not b:
                b = bookmark.Bookmark(tab.get_name(), autojoin=True, method="local")
                new_bookmarks.append(b)
            else:
                b.method = "local"
                new_bookmarks.append(b)
                bookmark.bookmarks.remove(b)
        new_bookmarks.extend(bookmark.bookmarks)
        bookmark.bookmarks = new_bookmarks
        bookmark.save_local()
        bookmark.save_remote(self.xmpp)
        self.information('Bookmarks added and saved.', 'Info')
        return
    else:
        info = safeJID(args[0])
        if info.resource != '':
            nick = info.resource
        roomname = info.bare
        if not roomname:
            if not isinstance(self.current_tab(), tabs.MucTab):
                return
            roomname = self.current_tab().get_name()
        if len(args) > 1:
            password = args[1]

    bm = bookmark.get_by_jid(roomname)
    if not bm:
        bm = bookmark.Bookmark(jid=roomname)
        bookmark.bookmarks.append(bm)
        self.information('Bookmark added.', 'Info')
    else:
        self.information('Bookmark updated.', 'Info')
    if nick:
        bm.nick = nick
    bm.autojoin = True
    bm.password = password
    bm.method = "local"
    bookmark.save_local()
    self.information(_('Your local bookmarks are now: %s') %
            [b for b in bookmark.bookmarks if b.method == 'local'], 'Info')

def command_bookmark(self, arg=''):
    """
    /bookmark [room][/nick] [autojoin] [password]
    """

    if not config.get('use_remote_bookmarks', True):
        self.command_bookmark_local(arg)
        return
    args = common.shell_split(arg)
    nick = None
    if not args and not isinstance(self.current_tab(), tabs.MucTab):
        return
    if not args:
        tab = self.current_tab()
        roomname = tab.get_name()
        if tab.joined:
            nick = tab.own_nick
        autojoin = True
        password = None
    elif args[0] == '*':
        if len(args) > 1:
            autojoin = False if args[1].lower() != 'true' else True
        else:
            autojoin = True
        new_bookmarks = []
        for tab in self.get_tabs(tabs.MucTab):
            b = bookmark.get_by_jid(tab.get_name())
            if not b:
                b = bookmark.Bookmark(tab.get_name(), autojoin=autojoin,
                        method=bookmark.preferred)
                new_bookmarks.append(b)
            else:
                b.method = bookmark.preferred
                bookmark.bookmarks.remove(b)
                new_bookmarks.append(b)
        new_bookmarks.extend(bookmark.bookmarks)
        bookmark.bookmarks = new_bookmarks

        if bookmark.save_remote(self.xmpp):
            bookmark.save_local()
            self.information("Bookmarks added.", "Info")
        else:
            self.information("Could not add the bookmarks.", "Info")
        return
    else:
        info = safeJID(args[0])
        if info.resource != '':
            nick = info.resource
        roomname = info.bare
        if roomname == '':
            if not isinstance(self.current_tab(), tabs.MucTab):
                return
            roomname = self.current_tab().get_name()
        if len(args) > 1:
            autojoin = False if args[1].lower() != 'true' else True
        else:
            autojoin = True
        if len(args) > 2:
            password = args[2]
        else:
            password = None
    bm = bookmark.get_by_jid(roomname)
    if not bm:
        bm = bookmark.Bookmark(roomname)
        bookmark.bookmarks.append(bm)
    bm.method = config.get('use_bookmarks_method', 'pep')
    if nick:
        bm.nick = nick
    if password:
        bm.password = password
    bm.autojoin = autojoin
    if bookmark.save_remote(self.xmpp):
        self.information('Bookmark added.', 'Info')
    self.information(_('Your remote bookmarks are now: %s') %
            [b for b in bookmark.bookmarks if b.method in ('pep', 'privatexml')], 'Info')

def command_bookmarks(self, arg=''):
    """/bookmarks"""
    self.information(_('Your remote bookmarks are: %s') %
            [b for b in bookmark.bookmarks if b.method in ('pep', 'privatexml')], 'Info')
    self.information(_('Your local bookmarks are: %s') %
            [b for b in bookmark.bookmarks if b.method is 'local'], 'Info')

def command_remove_bookmark(self, arg=''):
    """/remove_bookmark [jid]"""
    args = common.shell_split(arg)
    if not args:
        tab = self.current_tab()
        if isinstance(tab, tabs.MucTab) and bookmark.get_by_jid(tab.get_name()):
            bookmark.remove(tab.get_name())
            bookmark.save(self.xmpp)
            if bookmark.save(self.xmpp):
                self.information('Bookmark deleted', 'Info')
        else:
            self.information('No bookmark to remove', 'Info')
    else:
        if bookmark.get_by_jid(args[0]):
            bookmark.remove(args[0])
            if bookmark.save(self.xmpp):
                self.information('Bookmark deleted', 'Info')

        else:
            self.information('No bookmark to remove', 'Info')

def command_set(self, arg):
    """
    /set [module|][section] <option> <value>
    """
    args = common.shell_split(arg)
    if len(args) != 2 and len(args) != 3:
        self.command_help('set')
        return
    if len(args) == 2:
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
                return
            plugin = self.plugin_manager.plugins[plugin_name]
            info = plugin.config.set_and_save(option, value, section)
        else:
            section = args[0]
            option = args[1]
            value = args[2]
            info = config.set_and_save(option, value, section)
            self.trigger_configuration_change(option, value)
    self.call_for_resize()
    self.information(*info)

def command_server_cycle(self, arg=''):
    """
    Do a /cycle on each room of the given server. If none, do it on the current tab
    """
    args = common.shell_split(arg)
    tab = self.current_tab()
    message = ""
    if len(args):
        domain = args[0]
        if len(args) > 1:
            message = args[1]
    else:
        if isinstance(tab, tabs.MucTab):
            domain = safeJID(tab.get_name()).domain
        else:
            self.information(_("No server specified"), "Error")
            return
    for tab in self.get_tabs(tabs.MucTab):
        if tab.get_name().endswith(domain):
            if tab.joined:
                muc.leave_groupchat(tab.core.xmpp, tab.get_name(), tab.own_nick, message)
            tab.joined = False
            if tab.get_name() == domain:
                self.command_join('"@%s/%s"' %(tab.get_name(), tab.own_nick))
            else:
                self.command_join('"%s/%s"' %(tab.get_name(), tab.own_nick))

def command_last_activity(self, arg):
    """
    /last_activity <jid>
    """
    def callback(iq):
        if iq['type'] != 'result':
            if iq['error']['type'] == 'auth':
                self.information('You are not allowed to see the activity of this contact.', 'Error')
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
                (' and his/her last status was %s' % status) if status else '',)
        self.information(msg, 'Info')
    jid = safeJID(arg)
    if jid == '':
        return self.command_help('last_activity')
    self.xmpp.plugin['xep_0012'].get_last_activity(jid, block=False, callback=callback)

def command_mood(self, arg):
    """
    /mood [<mood> [text]]
    """
    args = common.shell_split(arg)
    if not args:
        return self.xmpp.plugin['xep_0107'].stop(block=False)
    mood = args[0]
    if mood not in pep.MOODS:
        return self.information('%s is not a correct value for a mood.' % mood, 'Error')
    if len(args) > 1:
        text = args[1]
    else:
        text = None
    self.xmpp.plugin['xep_0107'].publish_mood(mood, text, callback=dumb_callback, block=False)

def command_activity(self, arg):
    """
    /activity [<general> [specific] [text]]
    """
    args = common.shell_split(arg)
    length = len(args)
    if not length:
        return self.xmpp.plugin['xep_0108'].stop(block=False)
    general = args[0]
    if general not in pep.ACTIVITIES:
        return self.information('%s is not a correct value for an activity' % general, 'Error')
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
        return self.information('%s is not a correct value for an activity' % specific, 'Error')
    self.xmpp.plugin['xep_0108'].publish_activity(general, specific, text, callback=dumb_callback, block=False)

def command_gaming(self, arg):
    """
    /gaming [<game name> [server address]]
    """
    args = common.shell_split(arg)
    if not args:
        return self.xmpp.plugin['xep_0196'].stop(block=False)
    name = args[0]
    if len(args) > 1:
        address = args[1]
    else:
        address = None
    return self.xmpp.plugin['xep_0196'].publish_gaming(name=name, server_address=address, callback=dumb_callback, block=False)

def command_invite(self, arg):
    """/invite <to> <room> [reason]"""
    args = common.shell_split(arg)
    if len(args) < 2:
        return
    reason = args[2] if len(args) > 2 else ''
    to = safeJID(args[0])
    room = safeJID(args[1])
    self.xmpp.plugin['xep_0045'].invite(room, str(to), reason)

def command_decline(self, arg):
    """/decline <room@server.tld> [reason]"""
    args = common.shell_split(arg)
    if not len(args):
        return
    jid = safeJID(args[0])
    if jid.bare not in self.pending_invites:
        return
    reason = args[1] if len(args) > 1 else ''
    del self.pending_invites[jid.bare]
    self.xmpp.plugin['xep_0045'].decline_invite(jid.bare, self.pending_invites[jid.bare], reason)

### Commands without a completion in this class ###

def command_invitations(self, arg=''):
    """/invitations"""
    build = ""
    for invite in self.pending_invites:
        build += "%s by %s" % (invite, safeJID(self.pending_invites[invite]).bare)
    if self.pending_invites:
        build = "You are invited to the following rooms:\n" + build
    else:
        build = "You do not have any pending invitations."
    self.information(build, 'Info')

def command_quit(self, arg=''):
    """
    /quit
    """
    if len(arg.strip()) != 0:
        msg = arg
    else:
        msg = None
    if config.get('enable_user_mood', True):
        self.xmpp.plugin['xep_0107'].stop(block=False)
    if config.get('enable_user_activity', True):
        self.xmpp.plugin['xep_0108'].stop(block=False)
    if config.get('enable_user_gaming', True):
        self.xmpp.plugin['xep_0196'].stop(block=False)
    self.save_config()
    self.plugin_manager.disable_plugins()
    self.disconnect(msg)
    self.running = False
    self.reset_curses()
    sys.exit()

def command_bind(self, arg):
    """
    Bind a key.
    """
    args = common.shell_split(arg)
    if len(args) < 1:
        return self.command_help('bind')
    elif len(args) < 2:
        args.append("")
    if not config.silent_set(args[0], args[1], section='bindings'):
        self.information(_('Unable to write in the config file'), 'Error')
    if args[1]:
        self.information('%s is now bound to %s' % (args[0], args[1]), 'Info')
    else:
        self.information('%s is now unbound' % args[0], 'Info')

def command_rawxml(self, arg):
    """
    /rawxml <xml stanza>
    """
    if not arg:
        return


    try:
        stanza = StanzaBase(self.xmpp, xml=ET.fromstring(arg))
        if stanza.xml.tag == 'iq' and \
                stanza.xml.attrib.get('type') in ('get', 'set') and \
                stanza.xml.attrib.get('id'):
            iq_id = stanza.xml.attrib.get('id')

            def iqfunc(iq):
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
        self.information(_('Could not send custom stanza'), 'Error')
        log.debug('/rawxml: Could not send custom stanza (%s)',
                repr(arg),
                exc_info=True)


def command_load(self, arg):
    """
    /load <plugin>
    """
    args = arg.split()
    if len(args) != 1:
        self.command_help('load')
        return
    filename = args[0]
    self.plugin_manager.load(filename)

def command_unload(self, arg):
    """
    /unload <plugin>
    """
    args = arg.split()
    if len(args) != 1:
        self.command_help('unload')
        return
    filename = args[0]
    self.plugin_manager.unload(filename)

def command_plugins(self, arg=''):
    """
    /plugins
    """
    self.information("Plugins currently in use: %s" % repr(list(self.plugin_manager.plugins.keys())), 'Info')

def command_message(self, arg):
    """
    /message <jid> [message]
    """
    args = common.shell_split(arg)
    if len(args) < 1:
        self.command_help('message')
        return
    jid = safeJID(args[0])
    if not jid.user and not jid.domain and not jid.resource:
        return self.information('Invalid JID.', 'Error')
    tab = self.get_conversation_by_jid(jid.full, False, fallback_barejid=False)
    if not tab:
        tab = self.open_conversation_window(jid.full, focus=True)
    else:
        self.focus_tab_named(tab.get_name())
    if len(args) > 1:
        tab.command_say(args[1])

def command_xml_tab(self, arg=''):
    """/xml_tab"""
    self.xml_tab = True
    xml_tab = self.focus_tab_named('XMLTab', tabs.XMLTab)
    if not xml_tab:
        tab = tabs.XMLTab()
        self.add_tab(tab, True)

def command_self(self, arg=None):
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

def dumb_callback(*args, **kwargs):
    pass
