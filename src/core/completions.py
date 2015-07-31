"""
Completions for the global commands
"""
import logging

log = logging.getLogger(__name__)

import os
from functools import reduce

import common
import pep
import tabs
from common import safeJID
from config import config
from roster import roster

from . structs import possible_show


def completion_help(self, the_input):
    """Completion for /help."""
    commands = sorted(self.commands.keys()) + sorted(self.current_tab().commands.keys())
    return the_input.new_completion(commands, 1, quotify=False)


def completion_status(self, the_input):
    """
    Completion of /status
    """
    if the_input.get_argument_position() == 1:
        return the_input.new_completion([status for status in possible_show], 1, ' ', quotify=False)


def completion_presence(self, the_input):
    """
    Completion of /presence
    """
    arg = the_input.get_argument_position()
    if arg == 1:
        return the_input.auto_completion([jid for jid in roster.jids()], '', quotify=True)
    elif arg == 2:
        return the_input.auto_completion([status for status in possible_show], '', quotify=True)


def completion_theme(self, the_input):
    """ Completion for /theme"""
    themes_dir = config.get('themes_dir')
    themes_dir = themes_dir or\
    os.path.join(os.environ.get('XDG_DATA_HOME') or\
                     os.path.join(os.environ.get('HOME'), '.local', 'share'),
                 'poezio', 'themes')
    themes_dir = os.path.expanduser(themes_dir)
    try:
        names = os.listdir(themes_dir)
    except OSError as e:
        log.error('Completion for /theme failed', exc_info=True)
        return
    theme_files = [name[:-3] for name in names if name.endswith('.py') and name != '__init__.py']
    if not 'default' in theme_files:
        theme_files.append('default')
    return the_input.new_completion(theme_files, 1, '', quotify=False)


def completion_win(self, the_input):
    """Completion for /win"""
    l = []
    for tab in self.tabs:
        l.extend(tab.matching_names())
    l = [i[1] for i in l]
    return the_input.new_completion(l, 1, '', quotify=False)


def completion_join(self, the_input):
    """
    Completion for /join

    Try to complete the MUC JID:
        if only a resource is provided, complete with the default nick
        if only a server is provided, complete with the rooms from the
            disco#items of that server
        if only a nodepart is provided, complete with the servers of the
            current joined rooms
    """
    n = the_input.get_argument_position(quoted=True)
    args = common.shell_split(the_input.text)
    if n != 1:
        # we are not on the 1st argument of the command line
        return False
    if len(args) == 1:
        args.append('')
    jid = safeJID(args[1])
    if args[1].endswith('@') and not jid.user and not jid.server:
        jid.user = args[1][:-1]

    relevant_rooms = []
    relevant_rooms.extend(sorted(self.pending_invites.keys()))
    bookmarks = {str(elem.jid): False for elem in self.bookmarks}
    for tab in self.get_tabs(tabs.MucTab):
        name = tab.name
        if name in bookmarks and not tab.joined:
            bookmarks[name] = True
    relevant_rooms.extend(sorted(room[0] for room in bookmarks.items() if room[1]))

    if the_input.last_completion:
        return the_input.new_completion([], 1, quotify=True)

    if jid.user:
        # we are writing the server: complete the server
        serv_list = []
        for tab in self.get_tabs(tabs.MucTab):
            if tab.joined:
                serv_list.append('%s@%s'% (jid.user, safeJID(tab.name).host))
        serv_list.extend(relevant_rooms)
        return the_input.new_completion(serv_list, 1, quotify=True)
    elif args[1].startswith('/'):
        # we completing only a resource
        return the_input.new_completion(['/%s' % self.own_nick], 1, quotify=True)
    else:
        return the_input.new_completion(relevant_rooms, 1, quotify=True)


def completion_version(self, the_input):
    """Completion for /version"""
    comp = reduce(lambda x, y: x + [i.jid for i in y], (roster[jid].resources for jid in roster.jids() if len(roster[jid])), [])
    return the_input.new_completion(sorted(comp), 1, quotify=False)


def completion_list(self, the_input):
    """Completion for /list"""
    muc_serv_list = []
    for tab in self.get_tabs(tabs.MucTab):   # TODO, also from an history
        if tab.name not in muc_serv_list:
            muc_serv_list.append(safeJID(tab.name).server)
    if muc_serv_list:
        return the_input.new_completion(muc_serv_list, 1, quotify=False)


def completion_move_tab(self, the_input):
    """Completion for /move_tab"""
    n = the_input.get_argument_position(quoted=True)
    if n == 1:
        nodes = [tab.name for tab in self.tabs if tab]
        nodes.remove('Roster')
        return the_input.new_completion(nodes, 1, ' ', quotify=True)


def completion_runkey(self, the_input):
    """
    Completion for /runkey
    """
    list_ = []
    list_.extend(self.key_func.keys())
    list_.extend(self.current_tab().key_func.keys())
    return the_input.new_completion(list_, 1, quotify=False)


def completion_bookmark(self, the_input):
    """Completion for /bookmark"""
    args = common.shell_split(the_input.text)
    n = the_input.get_argument_position(quoted=True)

    if n == 2:
        return the_input.new_completion(['true', 'false'], 2, quotify=True)
    if n >= 3:
        return

    if len(args) == 1:
        args.append('')
    jid = safeJID(args[1])

    if jid.server and (jid.resource or jid.full.endswith('/')):
        tab = self.get_tab_by_name(jid.bare, tabs.MucTab)
        nicks = [tab.own_nick] if tab else []
        default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
        nick = config.get('default_nick')
        if not nick:
            if not default in nicks:
                nicks.append(default)
        else:
            if not nick in nicks:
                nicks.append(nick)
        jids_list = ['%s/%s' % (jid.bare, nick) for nick in nicks]
        return the_input.new_completion(jids_list, 1, quotify=True)
    muc_list = [tab.name for tab in self.get_tabs(tabs.MucTab)]
    muc_list.sort()
    muc_list.append('*')
    return the_input.new_completion(muc_list, 1, quotify=True)


def completion_remove_bookmark(self, the_input):
    """Completion for /remove_bookmark"""
    return the_input.new_completion([bm.jid for bm in self.bookmarks], 1, quotify=False)


def completion_decline(self, the_input):
    """Completion for /decline"""
    n = the_input.get_argument_position(quoted=True)
    if n == 1:
        return the_input.auto_completion(sorted(self.pending_invites.keys()), 1, '', quotify=True)


def completion_bind(self, the_input):
    n = the_input.get_argument_position()
    if n == 1:
        args = [key for key in self.key_func if not key.startswith('_')]
    elif n == 2:
        args = [key for key in self.key_func]
    else:
        return

    return the_input.new_completion(args, n, '', quotify=False)


def completion_message(self, the_input):
    """Completion for /message"""
    n = the_input.get_argument_position(quoted=True)
    if n >= 2:
        return
    l = []
    for jid in roster.jids():
        if len(roster[jid]):
            l.append(jid)
            for resource in roster[jid].resources:
                l.append(resource.jid)
    return the_input.new_completion(l, 1, '', quotify=True)


def completion_invite(self, the_input):
    """Completion for /invite"""
    n = the_input.get_argument_position(quoted=True)
    if n == 1:
        comp = reduce(lambda x, y: x + [i.jid for i in y], (roster[jid].resources for jid in roster.jids() if len(roster[jid])), [])
        comp = sorted(comp)
        bares = sorted(roster[contact].bare_jid for contact in roster.jids() if len(roster[contact]))
        off = sorted(jid for jid in roster.jids() if jid not in bares)
        comp = comp + bares + off
        return the_input.new_completion(comp, n, quotify=True)
    elif n == 2:
        rooms = []
        for tab in self.get_tabs(tabs.MucTab):
            if tab.joined:
                rooms.append(tab.name)
        rooms.sort()
        return the_input.new_completion(rooms, n, '', quotify=True)


def completion_activity(self, the_input):
    """Completion for /activity"""
    n = the_input.get_argument_position(quoted=True)
    args = common.shell_split(the_input.text)
    if n == 1:
        return the_input.new_completion(sorted(pep.ACTIVITIES.keys()), n, quotify=True)
    elif n == 2:
        if args[1] in pep.ACTIVITIES:
            l = list(pep.ACTIVITIES[args[1]])
            l.remove('category')
            l.sort()
            return the_input.new_completion(l, n, quotify=True)


def completion_mood(self, the_input):
    """Completion for /mood"""
    n = the_input.get_argument_position(quoted=True)
    if n == 1:
        return the_input.new_completion(sorted(pep.MOODS.keys()), 1, quotify=True)


def completion_last_activity(self, the_input):
    """
    Completion for /last_activity <jid>
    """
    n = the_input.get_argument_position(quoted=False)
    if n >= 2:
        return
    comp = reduce(lambda x, y: x + [i.jid for i in y], (roster[jid].resources for jid in roster.jids() if len(roster[jid])), [])
    return the_input.new_completion(sorted(comp), 1, '', quotify=False)


def completion_server_cycle(self, the_input):
    """Completion for /server_cycle"""
    serv_list = set()
    for tab in self.get_tabs(tabs.MucTab):
        serv = safeJID(tab.name).server
        serv_list.add(serv)
    return the_input.new_completion(sorted(serv_list), 1, ' ')


def completion_set(self, the_input):
    """Completion for /set"""
    args = common.shell_split(the_input.text)
    n = the_input.get_argument_position(quoted=True)
    if n >= len(args):
        args.append('')
    if n == 1:
        if '|' in args[1]:
            plugin_name, section = args[1].split('|')[:2]
            if not plugin_name in self.plugin_manager.plugins:
                    return the_input.new_completion([], n, quotify=True)
            plugin = self.plugin_manager.plugins[plugin_name]
            end_list = ['%s|%s' % (plugin_name, section) for section in plugin.config.sections()]
        else:
            end_list = set(config.options('Poezio'))
            end_list.update(config.default.get('Poezio', {}))
            end_list = list(end_list)
            end_list.sort()
    elif n == 2:
        if '|' in args[1]:
            plugin_name, section = args[1].split('|')[:2]
            if not plugin_name in self.plugin_manager.plugins:
                    return the_input.new_completion([''], n, quotify=True)
            plugin = self.plugin_manager.plugins[plugin_name]
            end_list = set(plugin.config.options(section or plugin_name))
            if plugin.config.default:
                end_list.update(plugin.config.default.get(section or plugin_name, {}))
            end_list = list(end_list)
            end_list.sort()
        elif not config.has_option('Poezio', args[1]):
            if config.has_section(args[1]):
                end_list = config.options(args[1])
                end_list.append('')
            else:
                end_list = []
        else:
            end_list = [str(config.get(args[1], '')), '']
    elif n == 3:
        if '|' in args[1]:
            plugin_name, section = args[1].split('|')[:2]
            if not plugin_name in self.plugin_manager.plugins:
                    return the_input.new_completion([''], n, quotify=True)
            plugin = self.plugin_manager.plugins[plugin_name]
            end_list = [str(plugin.config.get(args[2], '', section or plugin_name)), '']
        else:
            if not config.has_section(args[1]):
                end_list = ['']
            else:
                end_list = [str(config.get(args[2], '', args[1])), '']
    else:
        return
    return the_input.new_completion(end_list, n, quotify=True)


def completion_set_default(self, the_input):
    """ Completion for /set_default
    """
    args = common.shell_split(the_input.text)
    n = the_input.get_argument_position(quoted=True)
    if n >= len(args):
        args.append('')
    if n == 1 or (n == 2 and config.has_section(args[1])):
        return self.completion_set(the_input)
    return []


def completion_toggle(self, the_input):
    "Completion for /toggle"
    return the_input.new_completion(config.options('Poezio'), 1, quotify=False)


def completion_bookmark_local(self, the_input):
    """Completion for /bookmark_local"""
    n = the_input.get_argument_position(quoted=True)
    args = common.shell_split(the_input.text)

    if n >= 2:
        return
    if len(args) == 1:
        args.append('')
    jid = safeJID(args[1])

    if jid.server and (jid.resource or jid.full.endswith('/')):
        tab = self.get_tab_by_name(jid.bare, tabs.MucTab)
        nicks = [tab.own_nick] if tab else []
        default = os.environ.get('USER') if os.environ.get('USER') else 'poezio'
        nick = config.get('default_nick')
        if not nick:
            if not default in nicks:
                nicks.append(default)
        else:
            if not nick in nicks:
                nicks.append(nick)
        jids_list = ['%s/%s' % (jid.bare, nick) for nick in nicks]
        return the_input.new_completion(jids_list, 1, quotify=True)
    muc_list = [tab.name for tab in self.get_tabs(tabs.MucTab)]
    muc_list.append('*')
    return the_input.new_completion(muc_list, 1, quotify=True)

