"""
Completions for the global commands
"""
import logging

log = logging.getLogger(__name__)

import os
from pathlib import Path
from functools import reduce

from poezio import common
from poezio import pep
from poezio import tabs
from poezio import xdg
from poezio.common import safeJID
from poezio.config import config
from poezio.roster import roster

from poezio.core.structs import POSSIBLE_SHOW, Completion


class CompletionCore:
    def __init__(self, core):
        self.core = core

    def help(self, the_input):
        """Completion for /help."""
        commands = sorted(self.core.commands.keys()) + sorted(
            self.core.tabs.current_tab.commands.keys())
        return Completion(the_input.new_completion, commands, 1, quotify=False)

    def status(self, the_input):
        """
        Completion of /status
        """
        if the_input.get_argument_position() == 1:
            return Completion(
                the_input.new_completion, [status for status in POSSIBLE_SHOW],
                1,
                ' ',
                quotify=False)

    def presence(self, the_input):
        """
        Completion of /presence
        """
        arg = the_input.get_argument_position()
        if arg == 1:
            to_suggest = []
            for bookmark in self.core.bookmarks:
                tab = self.core.tabs.by_name_and_class(bookmark.jid,
                                                       tabs.MucTab)
                if tab is not None and tab.joined:
                    to_suggest.append(bookmark.jid)
            return Completion(
                the_input.auto_completion,
                roster.jids() + to_suggest,
                '',
                quotify=True)
        elif arg == 2:
            return Completion(
                the_input.auto_completion,
                [status for status in POSSIBLE_SHOW],
                '',
                quotify=True)

    def theme(self, the_input):
        """ Completion for /theme"""
        themes_dir = config.get('themes_dir')
        themes_dir = Path(themes_dir).expanduser(
        ) if themes_dir else xdg.DATA_HOME / 'themes'
        try:
            theme_files = [
                name.stem for name in themes_dir.iterdir()
                if name.suffix == '.py' and name.name != '__init__.py'
            ]
        except OSError:
            log.error('Completion for /theme failed', exc_info=True)
            return False
        if 'default' not in theme_files:
            theme_files.append('default')
        return Completion(
            the_input.new_completion, theme_files, 1, '', quotify=False)

    def win(self, the_input):
        """Completion for /win"""
        l = []
        for tab in self.core.tabs:
            l.extend(tab.matching_names())
        l = [i[1] for i in l]
        return Completion(the_input.new_completion, l, 1, '', quotify=False)

    def join(self, the_input):
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
        relevant_rooms.extend(sorted(self.core.pending_invites.keys()))
        bookmarks = [(str(elem.jid)
                      if not elem.nick else '%s/%s' % (elem.jid, elem.nick))
                     for elem in self.core.bookmarks]
        to_suggest = []
        for bookmark in bookmarks:
            tab = self.core.tabs.by_name_and_class(bookmark, tabs.MucTab)
            if not tab or (tab and not tab.joined):
                to_suggest.append(bookmark)
        relevant_rooms.extend(sorted(to_suggest))

        if the_input.last_completion:
            return Completion(the_input.new_completion, [], 1, quotify=True)

        if jid.user:
            # we are writing the server: complete the server
            serv_list = []
            for tab in self.core.get_tabs(tabs.MucTab):
                if tab.joined:
                    serv_list.append(
                        '%s@%s' % (jid.user, safeJID(tab.name).host))
            serv_list.extend(relevant_rooms)
            return Completion(
                the_input.new_completion, serv_list, 1, quotify=True)
        elif args[1].startswith('/'):
            # we completing only a resource
            return Completion(
                the_input.new_completion, ['/%s' % self.core.own_nick],
                1,
                quotify=True)
        else:
            return Completion(
                the_input.new_completion, relevant_rooms, 1, quotify=True)

    def version(self, the_input):
        """Completion for /version"""
        comp = reduce(lambda x, y: x + [i.jid for i in y],
                      (roster[jid].resources for jid in roster.jids()
                       if len(roster[jid])), [])
        return Completion(
            the_input.new_completion, sorted(comp), 1, quotify=False)

    def list(self, the_input):
        """Completion for /list"""
        muc_serv_list = []
        for tab in self.core.get_tabs(
                tabs.MucTab):  # TODO, also from an history
            if tab.name not in muc_serv_list:
                muc_serv_list.append(safeJID(tab.name).server)
        if muc_serv_list:
            return Completion(
                the_input.new_completion, muc_serv_list, 1, quotify=False)

    def move_tab(self, the_input):
        """Completion for /move_tab"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            nodes = [tab.name for tab in self.core.tabs if tab]
            nodes.remove('Roster')
            return Completion(
                the_input.new_completion, nodes, 1, ' ', quotify=True)

    def runkey(self, the_input):
        """
        Completion for /runkey
        """
        list_ = []
        list_.extend(self.core.key_func.keys())
        list_.extend(self.core.tabs.current_tab.key_func.keys())
        return Completion(the_input.new_completion, list_, 1, quotify=False)

    def bookmark(self, the_input):
        """Completion for /bookmark"""
        args = common.shell_split(the_input.text)
        n = the_input.get_argument_position(quoted=True)

        if n == 2:
            return Completion(
                the_input.new_completion, ['true', 'false'], 2, quotify=True)
        if n >= 3:
            return False

        if len(args) == 1:
            args.append('')
        jid = safeJID(args[1])

        if jid.server and (jid.resource or jid.full.endswith('/')):
            tab = self.core.tabs.by_name_and_class(jid.bare, tabs.MucTab)
            nicks = [tab.own_nick] if tab else []
            default = os.environ.get('USER') if os.environ.get(
                'USER') else 'poezio'
            nick = config.get('default_nick')
            if not nick:
                if default not in nicks:
                    nicks.append(default)
            else:
                if nick not in nicks:
                    nicks.append(nick)
            jids_list = ['%s/%s' % (jid.bare, nick) for nick in nicks]
            return Completion(
                the_input.new_completion, jids_list, 1, quotify=True)
        muc_list = [tab.name for tab in self.core.get_tabs(tabs.MucTab)]
        muc_list.sort()
        muc_list.append('*')
        return Completion(the_input.new_completion, muc_list, 1, quotify=True)

    def remove_bookmark(self, the_input):
        """Completion for /remove_bookmark"""
        return Completion(
            the_input.new_completion, [bm.jid for bm in self.core.bookmarks],
            1,
            quotify=False)

    def decline(self, the_input):
        """Completion for /decline"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            return Completion(
                the_input.auto_completion,
                sorted(self.core.pending_invites.keys()),
                1,
                '',
                quotify=True)

    def bind(self, the_input):
        n = the_input.get_argument_position()
        if n == 1:
            args = [
                key for key in self.core.key_func if not key.startswith('_')
            ]
        elif n == 2:
            args = [key for key in self.core.key_func]
        else:
            return False

        return Completion(the_input.new_completion, args, n, '', quotify=False)

    def message(self, the_input):
        """Completion for /message"""
        n = the_input.get_argument_position(quoted=True)
        if n >= 2:
            return False
        online = []
        offline = []
        for jid in sorted(roster.jids()):
            if len(roster[jid]) > 0:
                online.append(jid)
            else:
                offline.append(jid)
        return Completion(
            the_input.new_completion, online + offline, 1, '', quotify=True)

    def invite(self, the_input):
        """Completion for /invite"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            comp = reduce(lambda x, y: x + [i.jid for i in y],
                          (roster[jid].resources for jid in roster.jids()
                           if len(roster[jid])), [])
            comp = sorted(comp)
            bares = sorted(roster[contact].bare_jid
                           for contact in roster.jids()
                           if len(roster[contact]))
            off = sorted(jid for jid in roster.jids() if jid not in bares)
            comp = comp + bares + off
            return Completion(the_input.new_completion, comp, n, quotify=True)
        elif n == 2:
            rooms = []
            for tab in self.core.get_tabs(tabs.MucTab):
                if tab.joined:
                    rooms.append(tab.name)
            rooms.sort()
            return Completion(
                the_input.new_completion, rooms, n, '', quotify=True)

    def activity(self, the_input):
        """Completion for /activity"""
        n = the_input.get_argument_position(quoted=True)
        args = common.shell_split(the_input.text)
        if n == 1:
            return Completion(
                the_input.new_completion,
                sorted(pep.ACTIVITIES.keys()),
                n,
                quotify=True)
        elif n == 2:
            if args[1] in pep.ACTIVITIES:
                l = list(pep.ACTIVITIES[args[1]])
                l.remove('category')
                l.sort()
                return Completion(the_input.new_completion, l, n, quotify=True)

    def mood(self, the_input):
        """Completion for /mood"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            return Completion(
                the_input.new_completion,
                sorted(pep.MOODS.keys()),
                1,
                quotify=True)

    def last_activity(self, the_input):
        """
        Completion for /last_activity <jid>
        """
        n = the_input.get_argument_position(quoted=False)
        if n >= 2:
            return False
        comp = reduce(lambda x, y: x + [i.jid for i in y],
                      (roster[jid].resources for jid in roster.jids()
                       if len(roster[jid])), [])
        return Completion(
            the_input.new_completion, sorted(comp), 1, '', quotify=False)

    def server_cycle(self, the_input):
        """Completion for /server_cycle"""
        serv_list = set()
        for tab in self.core.get_tabs(tabs.MucTab):
            serv = safeJID(tab.name).server
            serv_list.add(serv)
        return Completion(the_input.new_completion, sorted(serv_list), 1, ' ')

    def set(self, the_input):
        """Completion for /set"""
        args = common.shell_split(the_input.text)
        n = the_input.get_argument_position(quoted=True)
        if n >= len(args):
            args.append('')
        if n == 1:
            if '|' in args[1]:
                plugin_name, section = args[1].split('|')[:2]
                if plugin_name not in self.core.plugin_manager.plugins:
                    return Completion(
                        the_input.new_completion, [], n, quotify=True)
                plugin = self.core.plugin_manager.plugins[plugin_name]
                end_list = [
                    '%s|%s' % (plugin_name, section)
                    for section in plugin.config.sections()
                ]
            else:
                end_list = set(config.options('Poezio'))
                end_list.update(config.default.get('Poezio', {}))
                end_list = list(end_list)
                end_list.sort()
        elif n == 2:
            if '|' in args[1]:
                plugin_name, section = args[1].split('|')[:2]
                if plugin_name not in self.core.plugin_manager.plugins:
                    return Completion(
                        the_input.new_completion, [''], n, quotify=True)
                plugin = self.core.plugin_manager.plugins[plugin_name]
                end_list = set(plugin.config.options(section or plugin_name))
                if plugin.config.default:
                    end_list.update(
                        plugin.config.default.get(section or plugin_name, {}))
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
                if plugin_name not in self.core.plugin_manager.plugins:
                    return Completion(
                        the_input.new_completion, [''], n, quotify=True)
                plugin = self.core.plugin_manager.plugins[plugin_name]
                end_list = [
                    str(
                        plugin.config.get(args[2], '', section
                                          or plugin_name)), ''
                ]
            else:
                if not config.has_section(args[1]):
                    end_list = ['']
                else:
                    end_list = [str(config.get(args[2], '', args[1])), '']
        else:
            return False
        return Completion(the_input.new_completion, end_list, n, quotify=True)

    def set_default(self, the_input):
        """ Completion for /set_default
        """
        args = common.shell_split(the_input.text)
        n = the_input.get_argument_position(quoted=True)
        if n >= len(args):
            args.append('')
        if n == 1 or (n == 2 and config.has_section(args[1])):
            return Completion(self.set, the_input)
        return False

    def toggle(self, the_input):
        "Completion for /toggle"
        return Completion(
            the_input.new_completion,
            config.options('Poezio'),
            1,
            quotify=False)

    def bookmark_local(self, the_input):
        """Completion for /bookmark_local"""
        n = the_input.get_argument_position(quoted=True)
        args = common.shell_split(the_input.text)

        if n >= 2:
            return False
        if len(args) == 1:
            args.append('')
        jid = safeJID(args[1])

        if jid.server and (jid.resource or jid.full.endswith('/')):
            tab = self.core.tabs.by_name_and_class(jid.bare, tabs.MucTab)
            nicks = [tab.own_nick] if tab else []
            default = os.environ.get('USER') if os.environ.get(
                'USER') else 'poezio'
            nick = config.get('default_nick')
            if not nick:
                if default not in nicks:
                    nicks.append(default)
            else:
                if nick not in nicks:
                    nicks.append(nick)
            jids_list = ['%s/%s' % (jid.bare, nick) for nick in nicks]
            return Completion(
                the_input.new_completion, jids_list, 1, quotify=True)
        muc_list = [tab.name for tab in self.core.get_tabs(tabs.MucTab)]
        muc_list.append('*')
        return Completion(the_input.new_completion, muc_list, 1, quotify=True)
