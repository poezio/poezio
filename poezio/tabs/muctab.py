"""
Module for the MucTab

A MucTab is a tab for multi-user chats as defined in XEP-0045.

It keeps track of many things such as part/joins, maintains an
user list, and updates private tabs when necessary.
"""

import logging
log = logging.getLogger(__name__)

import bisect
import curses
import os
import random
import re
from datetime import datetime

from poezio.tabs import ChatTab, Tab, SHOW_NAME

from poezio import common
from poezio import fixes
from poezio import multiuserchat as muc
from poezio import timed_events
from poezio import windows
from poezio import xhtml
from poezio.common import safeJID
from poezio.config import config
from poezio.decorators import refresh_wrapper, command_args_parser
from poezio.logger import logger
from poezio.roster import roster
from poezio.theming import get_theme, dump_tuple
from poezio.user import User
from poezio.core.structs import Completion, Status


NS_MUC_USER = 'http://jabber.org/protocol/muc#user'


class MucTab(ChatTab):
    """
    The tab containing a multi-user-chat room.
    It contains an userlist, an input, a topic, an information and a chat zone
    """
    message_type = 'groupchat'
    plugin_commands = {}
    plugin_keys = {}
    def __init__(self, core, jid, nick, password=None):
        self.joined = False
        ChatTab.__init__(self, core, jid)
        if self.joined == False:
            self._state = 'disconnected'
        self.own_nick = nick
        self.own_user = None
        self.name = jid
        self.password = password
        self.users = []
        self.privates = [] # private conversations
        self.topic = ''
        self.topic_from = ''
        self.remote_wants_chatstates = True
        # Self ping event, so we can cancel it when we leave the room
        self.self_ping_event = None
        # We send active, composing and paused states to the MUC because
        # the chatstate may or may not be filtered by the MUC,
        # that’s not our problem.
        self.topic_win = windows.Topic()
        self.text_win = windows.TextWin()
        self._text_buffer.add_window(self.text_win)
        self.v_separator = windows.VerticalSeparator()
        self.user_win = windows.UserList()
        self.info_header = windows.MucInfoWin()
        self.input = windows.MessageInput()
        self.ignores = []       # set of Users
        # keys
        self.key_func['^I'] = self.completion
        self.key_func['M-u'] = self.scroll_user_list_down
        self.key_func['M-y'] = self.scroll_user_list_up
        self.key_func['M-n'] = self.go_to_next_hl
        self.key_func['M-p'] = self.go_to_prev_hl
        # commands
        self.register_command('ignore', self.command_ignore,
                usage='<nickname>',
                desc='Ignore a specified nickname.',
                shortdesc='Ignore someone',
                completion=self.completion_ignore)
        self.register_command('unignore', self.command_unignore,
                usage='<nickname>',
                desc='Remove the specified nickname from the ignore list.',
                shortdesc='Unignore someone.',
                completion=self.completion_unignore)
        self.register_command('kick', self.command_kick,
                usage='<nick> [reason]',
                desc='Kick the user with the specified nickname.'
                     ' You also can give an optional reason.',
                shortdesc='Kick someone.',
                completion=self.completion_quoted)
        self.register_command('ban', self.command_ban,
                usage='<nick> [reason]',
                desc='Ban the user with the specified nickname.'
                     ' You also can give an optional reason.',
                shortdesc='Ban someone',
                completion=self.completion_quoted)
        self.register_command('role', self.command_role,
                usage='<nick> <role> [reason]',
                desc='Set the role of an user. Roles can be:'
                     ' none, visitor, participant, moderator.'
                     ' You also can give an optional reason.',
                shortdesc='Set the role of an user.',
                completion=self.completion_role)
        self.register_command('affiliation', self.command_affiliation,
                usage='<nick or jid> <affiliation>',
                desc='Set the affiliation of an user. Affiliations can be:'
                     ' outcast, none, member, admin, owner.',
                shortdesc='Set the affiliation of an user.',
                completion=self.completion_affiliation)
        self.register_command('topic', self.command_topic,
                usage='<subject>',
                desc='Change the subject of the room.',
                shortdesc='Change the subject.',
                completion=self.completion_topic)
        self.register_command('query', self.command_query,
                usage='<nick> [message]',
                desc='Open a private conversation with <nick>. This nick'
                     ' has to be present in the room you\'re currently in.'
                     ' If you specified a message after the nickname, it '
                     'will immediately be sent to this user.',
                shortdesc='Query an user.',
                completion=self.completion_quoted)
        self.register_command('part', self.command_part,
                usage='[message]',
                desc='Disconnect from a room. You can'
                     ' specify an optional message.',
                shortdesc='Leave the room.')
        self.register_command('close', self.command_close,
                usage='[message]',
                desc='Disconnect from a room and close the tab.'
                     ' You can specify an optional message if '
                     'you are still connected.',
                shortdesc='Close the tab.')
        self.register_command('nick', self.command_nick,
                usage='<nickname>',
                desc='Change your nickname in the current room.',
                shortdesc='Change your nickname.',
                completion=self.completion_nick)
        self.register_command('recolor', self.command_recolor,
                usage='[random]',
                desc='Re-assign a color to all participants of the'
                     ' current room, based on the last time they talked.'
                     ' Use this if the participants currently talking '
                     'have too many identical colors. Use /recolor random'
                     ' for a non-deterministic result.',
                shortdesc='Change the nicks colors.',
                completion=self.completion_recolor)
        self.register_command('color', self.command_color,
                usage='<nick> <color>',
                desc='Fix a color for a nick. Use "unset" instead of a color'
                     ' to remove the attribution',
                shortdesc='Fix a color for a nick.',
                completion=self.completion_color)
        self.register_command('cycle', self.command_cycle,
                usage='[message]',
                desc='Leave the current room and rejoin it immediately.',
                shortdesc='Leave and re-join the room.')
        self.register_command('info', self.command_info,
                usage='<nickname>',
                desc='Display some information about the user '
                     'in the MUC: its/his/her role, affiliation,'
                     ' status and status message.',
                shortdesc='Show an user\'s infos.',
                completion=self.completion_info)
        self.register_command('configure', self.command_configure,
                desc='Configure the current room, through a form.',
                shortdesc='Configure the room.')
        self.register_command('version', self.command_version,
                usage='<jid or nick>',
                desc='Get the software version of the given JID'
                     ' or nick in room (usually its XMPP client'
                     ' and Operating System).',
                shortdesc='Get the software version of a jid.',
                completion=self.completion_version)
        self.register_command('names', self.command_names,
                desc='Get the users in the room with their roles.',
                shortdesc='List the users.')
        self.register_command('invite', self.command_invite,
                desc='Invite a contact to this room',
                usage='<jid> [reason]',
                shortdesc='Invite a contact to this room',
                completion=self.completion_invite)

        self.resize()
        self.update_commands()
        self.update_keys()

    @property
    def general_jid(self):
        return self.name

    @property
    def is_muc(self):
        return True

    @property
    def last_connection(self):
        last_message = self._text_buffer.last_message
        if last_message:
            return last_message.time
        return None

    @refresh_wrapper.always
    def go_to_next_hl(self):
        """
        Go to the next HL in the room, or the last
        """
        self.text_win.next_highlight()

    @refresh_wrapper.always
    def go_to_prev_hl(self):
        """
        Go to the previous HL in the room, or the first
        """
        self.text_win.previous_highlight()

    def completion_version(self, the_input):
        """Completion for /version"""
        compare_users = lambda x: x.last_talked
        userlist = []
        for user in sorted(self.users, key=compare_users, reverse=True):
            if user.nick != self.own_nick:
                userlist.append(user.nick)
        comp = []
        for jid in (jid for jid in roster.jids() if len(roster[jid])):
            for resource in roster[jid].resources:
                comp.append(resource.jid)
        comp.sort()
        userlist.extend(comp)

        return Completion(the_input.auto_completion, userlist, quotify=False)

    def completion_info(self, the_input):
        """Completion for /info"""
        compare_users = lambda x: x.last_talked
        userlist = []
        for user in sorted(self.users, key=compare_users, reverse=True):
            userlist.append(user.nick)
        return Completion(the_input.auto_completion, userlist, quotify=False)

    def completion_nick(self, the_input):
        """Completion for /nick"""
        nicks = [os.environ.get('USER'),
                 config.get('default_nick'),
                 self.core.get_bookmark_nickname(self.name)]
        nicks = [i for i in nicks if i]
        return Completion(the_input.auto_completion, nicks, '', quotify=False)

    def completion_recolor(self, the_input):
        if the_input.get_argument_position() == 1:
            return Completion(the_input.new_completion, ['random'], 1, '', quotify=False)
        return True

    def completion_color(self, the_input):
        """Completion for /color"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            userlist = [user.nick for user in self.users]
            if self.own_nick in userlist:
                userlist.remove(self.own_nick)
            return Completion(the_input.new_completion, userlist, 1, '', quotify=True)
        elif n == 2:
            colors = [i for i in xhtml.colors if i]
            colors.sort()
            colors.append('unset')
            colors.append('random')
            return Completion(the_input.new_completion, colors, 2, '', quotify=False)

    def completion_ignore(self, the_input):
        """Completion for /ignore"""
        userlist = [user.nick for user in self.users]
        if self.own_nick in userlist:
            userlist.remove(self.own_nick)
        userlist.sort()
        return Completion(the_input.auto_completion, userlist, quotify=False)

    def completion_role(self, the_input):
        """Completion for /role"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            userlist = [user.nick for user in self.users]
            if self.own_nick in userlist:
                userlist.remove(self.own_nick)
            return Completion(the_input.new_completion, userlist, 1, '', quotify=True)
        elif n == 2:
            possible_roles = ['none', 'visitor', 'participant', 'moderator']
            return Completion(the_input.new_completion, possible_roles, 2, '',
                                            quotify=True)

    def completion_affiliation(self, the_input):
        """Completion for /affiliation"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            userlist = [user.nick for user in self.users]
            if self.own_nick in userlist:
                userlist.remove(self.own_nick)
            jidlist = [user.jid.bare for user in self.users]
            if self.core.xmpp.boundjid.bare in jidlist:
                jidlist.remove(self.core.xmpp.boundjid.bare)
            userlist.extend(jidlist)
            return Completion(the_input.new_completion, userlist, 1, '', quotify=True)
        elif n == 2:
            possible_affiliations = ['none', 'member', 'admin',
                                     'owner', 'outcast']
            return Completion(the_input.new_completion, possible_affiliations, 2, '',
                                            quotify=True)

    @command_args_parser.quoted(1, 1, [''])
    def command_invite(self, args):
        """/invite <jid> [reason]"""
        if args is None:
            return self.core.command.help('invite')
        jid, reason = args
        self.core.command.invite('%s %s "%s"' % (jid, self.name, reason))

    def completion_invite(self, the_input):
        """Completion for /invite"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            return Completion(the_input.new_completion, roster.jids(), 1, quotify=True)

    def scroll_user_list_up(self):
        self.user_win.scroll_up()
        self.user_win.refresh(self.users)
        self.input.refresh()

    def scroll_user_list_down(self):
        self.user_win.scroll_down()
        self.user_win.refresh(self.users)
        self.input.refresh()

    @command_args_parser.quoted(1)
    def command_info(self, args):
        """
        /info <nick>
        """
        if args is None:
            return self.core.command.help('info')
        nick = args[0]
        user = self.get_user_by_name(nick)
        if not user:
            return self.core.information("Unknown user: %s" % nick, "Error")
        theme = get_theme()
        inf = '\x19' + dump_tuple(theme.COLOR_INFORMATION_TEXT) + '}'
        if user.jid:
            user_jid = '%s (\x19%s}%s\x19o%s)' % (
                            inf,
                            dump_tuple(theme.COLOR_MUC_JID),
                            user.jid,
                            inf)
        else:
            user_jid = ''
        info = ('\x19%s}%s\x19o%s%s: show: \x19%s}%s\x19o%s, affiliation:'
                ' \x19%s}%s\x19o%s, role: \x19%s}%s\x19o%s') % (
                        dump_tuple(user.color),
                        nick,
                        user_jid,
                        inf,
                        dump_tuple(theme.color_show(user.show)),
                        user.show or 'Available',
                        inf,
                        dump_tuple(theme.color_role(user.role)),
                        user.affiliation or 'None',
                        inf,
                        dump_tuple(theme.color_role(user.role)),
                        user.role or 'None',
                        '\n%s' % user.status if user.status else '')
        self.add_message(info, typ=0)
        self.core.refresh_window()

    @command_args_parser.quoted(0)
    def command_configure(self, ignored):
        """
        /configure
        """
        def on_form_received(form):
            if not form:
                self.core.information(
                    'Could not retrieve the configuration form',
                    'Error')
                return
            self.core.open_new_form(form, self.cancel_config, self.send_config)

        fixes.get_room_form(self.core.xmpp, self.name, on_form_received)

    def cancel_config(self, form):
        """
        The user do not want to send his/her config, send an iq cancel
        """
        muc.cancel_config(self.core.xmpp, self.name)
        self.core.close_tab()

    def send_config(self, form):
        """
        The user sends his/her config to the server
        """
        muc.configure_room(self.core.xmpp, self.name, form)
        self.core.close_tab()

    @command_args_parser.raw
    def command_cycle(self, msg):
        """/cycle [reason]"""
        self.command_part(msg)
        self.disconnect()
        self.user_win.pos = 0
        self.core.disable_private_tabs(self.name)
        self.join()

    def join(self):
        """
        Join the room
        """
        status = self.core.get_status()
        if self.last_connection:
            delta = datetime.now() - self.last_connection
            seconds = delta.seconds + delta.days * 24 * 3600
        else:
            seconds = 0
        muc.join_groupchat(self.core, self.name, self.own_nick,
                           self.password,
                           status=status.message,
                           show=status.show,
                           seconds=seconds)

    @command_args_parser.quoted(0, 1, [''])
    def command_recolor(self, args):
        """
        /recolor [random]
        Re-assign color to the participants of the room
        """
        deterministic = config.get_by_tabname('deterministic_nick_colors', self.name)
        if deterministic:
            for user in self.users:
                if user.nick == self.own_nick:
                    continue
                color = self.search_for_color(user.nick)
                if color != '':
                    continue
                user.set_deterministic_color()
            if args[0] == 'random':
                self.core.information('"random" was provided, but poezio is '
                                      'configured to use deterministic colors',
                                      'Warning')
            self.user_win.refresh(self.users)
            self.input.refresh()
            return
        compare_users = lambda x: x.last_talked
        users = list(self.users)
        sorted_users = sorted(users, key=compare_users, reverse=True)
        full_sorted_users = sorted_users[:]
        # search our own user, to remove it from the list
        # Also remove users whose color is fixed
        for user in full_sorted_users:
            color = self.search_for_color(user.nick)
            if user.nick == self.own_nick:
                sorted_users.remove(user)
                user.color = get_theme().COLOR_OWN_NICK
            elif color != '':
                sorted_users.remove(user)
                user.change_color(color, deterministic)
        colors = list(get_theme().LIST_COLOR_NICKNAMES)
        if args[0] == 'random':
            random.shuffle(colors)
        for i, user in enumerate(sorted_users):
            user.color = colors[i % len(colors)]
        self.text_win.rebuild_everything(self._text_buffer)
        self.user_win.refresh(self.users)
        self.text_win.refresh()
        self.input.refresh()

    @command_args_parser.quoted(2, 2, [''])
    def command_color(self, args):
        """
        /color <nick> <color>
        Fix a color for a nick.
        Use "unset" instead of a color to remove the attribution.
        User "random" to attribute a random color.
        """
        if args is None:
            return self.core.command.help('color')
        nick = args[0]
        color = args[1].lower()
        user = self.get_user_by_name(nick)
        if not color in xhtml.colors and color not in ('unset', 'random'):
            return self.core.information("Unknown color: %s" % color, 'Error')
        if user and user.nick == self.own_nick:
            return self.core.information("You cannot change the color of your"
                                         " own nick.", 'Error')
        if color == 'unset':
            if config.remove_and_save(nick, 'muc_colors'):
                self.core.information('Color for nick %s unset' % (nick))
        else:
            if color == 'random':
                color = random.choice(list(xhtml.colors))
            if user:
                user.change_color(color)
            config.set_and_save(nick, color, 'muc_colors')
            nick_color_aliases = config.get_by_tabname('nick_color_aliases', self.name)
            if nick_color_aliases:
                # if any user in the room has a nick which is an alias of the
                # nick, update its color
                for tab in self.core.get_tabs(MucTab):
                    for u in tab.users:
                        nick_alias = re.sub('^_*', '', u.nick)
                        nick_alias = re.sub('_*$', '', nick_alias)
                        if nick_alias == nick:
                            u.change_color(color)
            self.text_win.rebuild_everything(self._text_buffer)
            self.user_win.refresh(self.users)
            self.text_win.refresh()
            self.input.refresh()

    @command_args_parser.quoted(1)
    def command_version(self, args):
        """
        /version <jid or nick>
        """
        def callback(res):
            if not res:
                return self.core.information('Could not get the software '
                                             'version from %s' % (jid,),
                                             'Warning')
            version = '%s is running %s version %s on %s' % (
                         jid,
                         res.get('name') or 'an unknown software',
                         res.get('version') or 'unknown',
                         res.get('os') or 'an unknown platform')
            self.core.information(version, 'Info')
        if args is None:
            return self.core.command.help('version')
        nick = args[0]
        if nick in [user.nick for user in self.users]:
            jid = safeJID(self.name).bare
            jid = safeJID(jid + '/' + nick)
        else:
            jid = safeJID(nick)
        fixes.get_version(self.core.xmpp, jid,
                          callback=callback)

    @command_args_parser.quoted(1)
    def command_nick(self, args):
        """
        /nick <nickname>
        """
        if args is None:
            return self.core.command.help('nick')
        nick = args[0]
        if not self.joined:
            return self.core.information('/nick only works in joined rooms',
                                         'Info')
        current_status = self.core.get_status()
        if not safeJID(self.name + '/' + nick):
            return self.core.information('Invalid nick', 'Info')
        muc.change_nick(self.core, self.name, nick,
                        current_status.message,
                        current_status.show)

    @command_args_parser.quoted(0, 1, [''])
    def command_part(self, args):
        """
        /part [msg]
        """
        arg = args[0]
        msg = None
        if self.joined:
            info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
            char_quit = get_theme().CHAR_QUIT
            spec_col = dump_tuple(get_theme().COLOR_QUIT_CHAR)

            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(get_theme().COLOR_OWN_NICK)
            else:
                color = 3

            if arg:
                msg = ('\x19%(color_spec)s}%(spec)s\x19%(info_col)s} '
                       'You (\x19%(color)s}%(nick)s\x19%(info_col)s})'
                       ' left the room'
                       ' (\x19o%(reason)s\x19%(info_col)s})') % {
                           'info_col': info_col, 'reason': arg,
                           'spec': char_quit, 'color': color,
                           'color_spec': spec_col,
                           'nick': self.own_nick,
                       }
            else:
                msg = ('\x19%(color_spec)s}%(spec)s\x19%(info_col)s} '
                       'You (\x19%(color)s}%(nick)s\x19%(info_col)s})'
                       ' left the room') % {
                           'info_col': info_col,
                           'spec': char_quit, 'color': color,
                           'color_spec': spec_col,
                           'nick': self.own_nick,
                       }

            self.add_message(msg, typ=2)
            self.disconnect()
            muc.leave_groupchat(self.core.xmpp, self.name, self.own_nick, arg)
            self.core.disable_private_tabs(self.name, reason=msg)
            if self == self.core.current_tab():
                self.refresh()
            self.core.doupdate()
        else:
            muc.leave_groupchat(self.core.xmpp, self.name, self.own_nick, arg)

    @command_args_parser.raw
    def command_close(self, msg):
        """
        /close [msg]
        """
        self.command_part(msg)
        self.core.close_tab(self)

    def on_close(self):
        super().on_close()
        self.command_part('')

    @command_args_parser.quoted(1, 1)
    def command_query(self, args):
        """
        /query <nick> [message]
        """
        if args is None:
            return  self.core.command.help('query')
        nick = args[0]
        r = None
        for user in self.users:
            if user.nick == nick:
                r = self.core.open_private_window(self.name, user.nick)
        if r and len(args) == 2:
            msg = args[1]
            self.core.current_tab().command_say(
                    xhtml.convert_simple_to_full_colors(msg))
        if not r:
            self.core.information("Cannot find user: %s" % nick, 'Error')

    @command_args_parser.raw
    def command_topic(self, subject):
        """
        /topic [new topic]
        """
        if not subject:
            info_text = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
            norm_text = dump_tuple(get_theme().COLOR_NORMAL_TEXT)
            if self.topic_from:
                user = self.get_user_by_name(self.topic_from)
                if user:
                    user_text = dump_tuple(user.color)
                    user_string = '\x19%s}(set by \x19%s}%s\x19%s})' % (
                            info_text, user_text, user.nick, info_text)
                else:
                    user_string = self.topic_from
            else:
                user_string = ''

            self._text_buffer.add_message(
                    "\x19%s}The subject of the room is: \x19%s}%s %s" %
                        (info_text, norm_text, self.topic, user_string))
            self.refresh()
            return

        muc.change_subject(self.core.xmpp, self.name, subject)

    @command_args_parser.quoted(0)
    def command_names(self, args):
        """
        /names
        """
        if not self.joined:
            return

        aff = {
                'owner': get_theme().CHAR_AFFILIATION_OWNER,
                'admin': get_theme().CHAR_AFFILIATION_ADMIN,
                'member': get_theme().CHAR_AFFILIATION_MEMBER,
                'none': get_theme().CHAR_AFFILIATION_NONE,
                }

        colors = {}
        colors["visitor"] = dump_tuple(get_theme().COLOR_USER_VISITOR)
        colors["moderator"] = dump_tuple(get_theme().COLOR_USER_MODERATOR)
        colors["participant"] = dump_tuple(get_theme().COLOR_USER_PARTICIPANT)
        color_other = dump_tuple(get_theme().COLOR_USER_NONE)

        buff = ['Users: %s \n' % len(self.users)]
        for user in self.users:
            affiliation = aff.get(user.affiliation,
                                  get_theme().CHAR_AFFILIATION_NONE)
            color = colors.get(user.role, color_other)
            buff.append('\x19%s}%s\x19o\x19%s}%s\x19o' % (
                color, affiliation, dump_tuple(user.color), user.nick))

        buff.append('\n')
        message = ' '.join(buff)

        self._text_buffer.add_message(message)
        self.text_win.refresh()
        self.input.refresh()

    def completion_topic(self, the_input):
        if the_input.get_argument_position() == 1:
            return Completion(the_input.auto_completion, [self.topic], '', quotify=False)

    def completion_quoted(self, the_input):
        """Nick completion, but with quotes"""
        if the_input.get_argument_position(quoted=True) == 1:
            compare_users = lambda x: x.last_talked
            word_list = []
            for user in sorted(self.users, key=compare_users, reverse=True):
                if user.nick != self.own_nick:
                    word_list.append(user.nick)

            return Completion(the_input.new_completion, word_list, 1, quotify=True)

    @command_args_parser.quoted(1, 1)
    def command_kick(self, args):
        """
        /kick <nick> [reason]
        """
        if args is None:
            return self.core.command.help('kick')
        if len(args) == 2:
            msg = ' "%s"' % args[1]
        else:
            msg = ''
        self.command_role('"'+args[0]+ '" none'+msg)

    @command_args_parser.quoted(1, 1)
    def command_ban(self, args):
        """
        /ban <nick> [reason]
        """
        def callback(iq):
            if iq['type'] == 'error':
                self.core.room_error(iq, self.name)
        if args is None:
            return self.core.command.help('ban')
        if len(args) > 1:
            msg = args[1]
        else:
            msg = ''
        nick = args[0]

        if nick in [user.nick for user in self.users]:
            res = muc.set_user_affiliation(self.core.xmpp, self.name,
                                           'outcast', nick=nick,
                                           callback=callback, reason=msg)
        else:
            res = muc.set_user_affiliation(self.core.xmpp, self.name,
                                           'outcast', jid=safeJID(nick),
                                           callback=callback, reason=msg)
        if not res:
            self.core.information('Could not ban user', 'Error')

    @command_args_parser.quoted(2, 1, [''])
    def command_role(self, args):
        """
        /role <nick> <role> [reason]
        Changes the role of an user
        roles can be: none, visitor, participant, moderator
        """
        def callback(iq):
            if iq['type'] == 'error':
                self.core.room_error(iq, self.name)

        if args is None:
            return self.core.command.help('role')

        nick, role, reason = args[0], args[1].lower(), args[2]

        valid_roles = ('none', 'visitor', 'participant', 'moderator')

        if not self.joined or role not in valid_roles:
            return self.core.information('The role must be one of ' + ', '.join(valid_roles),
                                         'Error')

        if not safeJID(self.name + '/' + nick):
            return self.core.information('Invalid nick', 'Info')
        muc.set_user_role(self.core.xmpp, self.name, nick, reason, role,
                          callback=callback)

    @command_args_parser.quoted(2)
    def command_affiliation(self, args):
        """
        /affiliation <nick> <role>
        Changes the affiliation of an user
        affiliations can be: outcast, none, member, admin, owner
        """
        def callback(iq):
            if iq['type'] == 'error':
                self.core.room_error(iq, self.name)

        if args is None:
            return self.core.command.help('affiliation')

        nick, affiliation = args[0], args[1].lower()

        if not self.joined:
            return

        valid_affiliations = ('outcast', 'none', 'member', 'admin', 'owner')
        if affiliation not in valid_affiliations:
            return self.core.information('The affiliation must be one of ' + ', '.join(valid_affiliations),
                                         'Error')

        if nick in [user.nick for user in self.users]:
            res = muc.set_user_affiliation(self.core.xmpp, self.name,
                                           affiliation, nick=nick,
                                           callback=callback)
        else:
            res = muc.set_user_affiliation(self.core.xmpp, self.name,
                                           affiliation, jid=safeJID(nick),
                                           callback=callback)
        if not res:
            self.core.information('Could not set affiliation', 'Error')

    @command_args_parser.raw
    def command_say(self, line, correct=False):
        """
        /say <message>
        Or normal input + enter
        """
        needed = 'inactive' if self.inactive else 'active'
        msg = self.core.xmpp.make_message(self.name)
        msg['type'] = 'groupchat'
        msg['body'] = line
        # trigger the event BEFORE looking for colors.
        # This lets a plugin insert \x19xxx} colors, that will
        # be converted in xhtml.
        self.core.events.trigger('muc_say', msg, self)
        if not msg['body']:
            self.cancel_paused_delay()
            self.text_win.refresh()
            self.input.refresh()
            return
        if msg['body'].find('\x19') != -1:
            msg.enable('html')
            msg['html']['body'] = xhtml.poezio_colors_to_html(msg['body'])
            msg['body'] = xhtml.clean_text(msg['body'])
        if (config.get_by_tabname('send_chat_states', self.general_jid)
                and self.remote_wants_chatstates is not False):
            msg['chat_state'] = needed
        if correct:
            msg['replace']['id'] = self.last_sent_message['id']
        self.cancel_paused_delay()
        self.core.events.trigger('muc_say_after', msg, self)
        if not msg['body']:
            self.cancel_paused_delay()
            self.text_win.refresh()
            self.input.refresh()
            return
        self.last_sent_message = msg
        msg.send()
        self.chat_state = needed

    @command_args_parser.raw
    def command_xhtml(self, msg):
        message = self.generate_xhtml_message(msg)
        if message:
            message['type'] = 'groupchat'
            message.send()

    @command_args_parser.quoted(1)
    def command_ignore(self, args):
        """
        /ignore <nick>
        """
        if args is None:
            return self.core.command.help('ignore')

        nick = args[0]
        user = self.get_user_by_name(nick)
        if not user:
            self.core.information('%s is not in the room' % nick)
        elif user in self.ignores:
            self.core.information('%s is already ignored' % nick)
        else:
            self.ignores.append(user)
            self.core.information("%s is now ignored" % nick, 'info')

    @command_args_parser.quoted(1)
    def command_unignore(self, args):
        """
        /unignore <nick>
        """
        if args is None:
            return self.core.command.help('unignore')

        nick = args[0]
        user = self.get_user_by_name(nick)
        if not user:
            self.core.information('%s is not in the room' % nick)
        elif user not in self.ignores:
            self.core.information('%s is not ignored' % nick)
        else:
            self.ignores.remove(user)
            self.core.information('%s is now unignored' % nick)

    def completion_unignore(self, the_input):
        if the_input.get_argument_position() == 1:
            users = [user.nick for user in self.ignores]
            return Completion(the_input.auto_completion, users, quotify=False)

    def resize(self):
        """
        Resize the whole window. i.e. all its sub-windows
        """
        self.need_resize = False
        if config.get('hide_user_list') or self.size.tab_degrade_x:
            display_user_list = False
            text_width = self.width
        else:
            display_user_list = True
            text_width = (self.width // 10) * 9

        if self.size.tab_degrade_y:
            display_info_win = False
            tab_win_height = 0
            info_win_height = 0
        else:
            display_info_win = True
            tab_win_height = Tab.tab_win_height()
            info_win_height = self.core.information_win_size


        self.user_win.resize(self.height - 3 - info_win_height
                                - tab_win_height,
                             self.width - (self.width // 10) * 9 - 1,
                             1,
                             (self.width // 10) * 9 + 1)
        self.v_separator.resize(self.height - 3 - info_win_height - tab_win_height,
                                1, 1, 9 * (self.width // 10))

        self.topic_win.resize(1, self.width, 0, 0)

        self.text_win.resize(self.height - 3 - info_win_height
                                - tab_win_height,
                             text_width, 1, 0)
        self.text_win.rebuild_everything(self._text_buffer)
        self.info_header.resize(1, self.width,
                                self.height - 2 - info_win_height
                                    - tab_win_height,
                                0)
        self.input.resize(1, self.width, self.height-1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        if config.get('hide_user_list') or self.size.tab_degrade_x:
            display_user_list = False
        else:
            display_user_list = True
        display_info_win = not self.size.tab_degrade_y

        self.topic_win.refresh(self.get_single_line_topic())
        self.text_win.refresh()
        if display_user_list:
            self.v_separator.refresh()
            self.user_win.refresh(self.users)
        self.info_header.refresh(self, self.text_win, user=self.own_user)
        self.refresh_tab_win()
        if display_info_win:
            self.info_win.refresh()
        self.input.refresh()

    def on_input(self, key, raw):
        if not raw and key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key, raw=raw)
        empty_after = self.input.get_text() == ''
        empty_after = empty_after or (self.input.get_text().startswith('/')
                                      and not
                                      self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)
        return False

    def completion(self):
        """
        Called when Tab is pressed, complete the nickname in the input
        """
        if self.complete_commands(self.input):
            return

        # If we are not completing a command or a command argument,
        # complete a nick
        compare_users = lambda x: x.last_talked
        word_list = []
        for user in sorted(self.users, key=compare_users, reverse=True):
            if user.nick != self.own_nick:
                word_list.append(user.nick)
        after = config.get('after_completion') + ' '
        input_pos = self.input.pos
        if ' ' not in self.input.get_text()[:input_pos] or (
                self.input.last_completion and
                    self.input.get_text()[:input_pos] ==
                    self.input.last_completion + after):
            add_after = after
        else:
            if not config.get('add_space_after_completion'):
                add_after = ''
            else:
                add_after = ' '
        self.input.auto_completion(word_list, add_after, quotify=False)
        empty_after = self.input.get_text() == ''
        empty_after = empty_after or (self.input.get_text().startswith('/')
                                      and not
                                      self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)

    def get_nick(self):
        if not config.get('show_muc_jid'):
            return safeJID(self.name).user
        return self.name

    def get_text_window(self):
        return self.text_win

    def on_lose_focus(self):
        if self.joined:
            if self.input.text:
                self.state = 'nonempty'
            else:
                self.state = 'normal'
        else:
            self.state = 'disconnected'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        if (config.get_by_tabname('send_chat_states', self.general_jid) and
                not self.input.get_text()):
            self.send_chat_state('inactive')
        self.check_scrolled()

    def on_gain_focus(self):
        self.state = 'current'
        if (self.text_win.built_lines and self.text_win.built_lines[-1] is None
                and not config.get('show_useless_separator')):
            self.text_win.remove_line_separator()
        curses.curs_set(1)
        if self.joined and config.get_by_tabname('send_chat_states',
                self.general_jid) and not self.input.get_text():
            self.send_chat_state('active')

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        if config.get("hide_user_list"):
            text_width = self.width
        else:
            text_width = (self.width//10)*9
        self.user_win.resize(self.height - 3 - self.core.information_win_size
                                - Tab.tab_win_height(),
                             self.width - (self.width // 10) * 9 - 1,
                             1,
                             (self.width // 10) * 9 + 1)
        self.v_separator.resize(self.height - 3 - self.core.information_win_size - Tab.tab_win_height(),
                                1, 1, 9 * (self.width // 10))
        self.text_win.resize(self.height - 3 - self.core.information_win_size
                                - Tab.tab_win_height(),
                             text_width, 1, 0)
        self.info_header.resize(1, self.width,
                                self.height-2-self.core.information_win_size
                                    - Tab.tab_win_height(),
                                0)

    def handle_presence(self, presence):
        from_nick = presence['from'].resource
        from_room = presence['from'].bare
        xpath = '{%s}x/{%s}status' % (NS_MUC_USER, NS_MUC_USER)
        status_codes = set()
        for status_code in presence.xml.findall(xpath):
            status_codes.add(status_code.attrib['code'])

        # Check if it's not an error presence.
        if presence['type'] == 'error':
            return self.core.room_error(presence, from_room)
        affiliation = presence['muc']['affiliation']
        show = presence['show']
        status = presence['status']
        role = presence['muc']['role']
        jid = presence['muc']['jid']
        typ = presence['type']
        deterministic = config.get_by_tabname('deterministic_nick_colors', self.name)
        if not self.joined:     # user in the room BEFORE us.
            # ignore redondant presence message, see bug #1509
            if (from_nick not in [user.nick for user in self.users]
                    and typ != "unavailable"):
                user_color = self.search_for_color(from_nick)
                new_user = User(from_nick, affiliation, show,
                                status, role, jid, deterministic, user_color)
                bisect.insort_left(self.users, new_user)
                self.core.events.trigger('muc_join', presence, self)
                if '110' in status_codes or self.own_nick == from_nick:
                    # second part of the condition is a workaround for old
                    # ejabberd or every gateway in the world that just do
                    # not send a 110 status code with the presence
                    self.own_nick = from_nick
                    self.own_user = new_user
                    self.joined = True
                    if self.name in self.core.initial_joins:
                        self.core.initial_joins.remove(self.name)
                        self._state = 'normal'
                    elif self != self.core.current_tab():
                        self._state = 'joined'
                    if (self.core.current_tab() is self
                            and self.core.status.show not in ('xa', 'away')):
                        self.send_chat_state('active')
                    new_user.color = get_theme().COLOR_OWN_NICK

                    if config.get_by_tabname('display_user_color_in_join_part',
                                             self.general_jid):
                        color = dump_tuple(new_user.color)
                    else:
                        color = 3

                    info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
                    warn_col = dump_tuple(get_theme().COLOR_WARNING_TEXT)
                    spec_col = dump_tuple(get_theme().COLOR_JOIN_CHAR)
                    enable_message = (
                        '\x19%(color_spec)s}%(spec)s\x19%(info_col)s} You '
                        '(\x19%(nick_col)s}%(nick)s\x19%(info_col)s}) joined'
                        ' the room') % {
                            'nick': from_nick,
                            'spec': get_theme().CHAR_JOIN,
                            'color_spec': spec_col,
                            'nick_col': color,
                            'info_col': info_col,
                            }
                    self.add_message(enable_message, typ=2)
                    if '201' in status_codes:
                        self.add_message(
                                '\x19%(info_col)s}Info: The room '
                                'has been created' %
                                   {'info_col': info_col},
                            typ=0)
                    if '170' in status_codes:
                        self.add_message(
                                '\x19%(warn_col)s}Warning:\x19%(info_col)s}'
                                ' This room is publicly logged' %
                                    {'info_col': info_col,
                                     'warn_col': warn_col},
                            typ=0)
                    if '100' in status_codes:
                        self.add_message(
                                '\x19%(warn_col)s}Warning:\x19%(info_col)s}'
                                ' This room is not anonymous.' %
                                    {'info_col': info_col,
                                     'warn_col': warn_col},
                            typ=0)
                    if self.core.current_tab() is not self:
                        self.refresh_tab_win()
                        self.core.current_tab().input.refresh()
                        self.core.doupdate()
                    self.core.enable_private_tabs(self.name, enable_message)
                    # Enable the self ping event, to regularly check if we
                    # are still in the room.
                    self.enable_self_ping_event()
        else:
            change_nick = '303' in status_codes
            kick = '307' in status_codes and typ == 'unavailable'
            ban = '301' in status_codes and typ == 'unavailable'
            shutdown = '332' in status_codes and typ == 'unavailable'
            non_member = '322' in status_codes and typ == 'unavailable'
            user = self.get_user_by_name(from_nick)
            # New user
            if not user:
                user_color = self.search_for_color(from_nick)
                self.core.events.trigger('muc_join', presence, self)
                self.on_user_join(from_nick, affiliation, show, status, role,
                                  jid, user_color)
            # nick change
            elif change_nick:
                self.core.events.trigger('muc_nickchange', presence, self)
                self.on_user_nick_change(presence, user, from_nick, from_room)
            elif ban:
                self.core.events.trigger('muc_ban', presence, self)
                self.core.on_user_left_private_conversation(from_room,
                                                            user, status)
                self.on_user_banned(presence, user, from_nick)
            # kick
            elif kick:
                self.core.events.trigger('muc_kick', presence, self)
                self.core.on_user_left_private_conversation(from_room,
                                                            user, status)
                self.on_user_kicked(presence, user, from_nick)
            elif shutdown:
                self.core.events.trigger('muc_shutdown', presence, self)
                self.on_muc_shutdown()
            elif non_member:
                self.core.events.trigger('muc_shutdown', presence, self)
                self.on_non_member_kicked()
            # user quit
            elif typ == 'unavailable':
                self.on_user_leave_groupchat(user, jid, status,
                                             from_nick, from_room)
            # status change
            else:
                self.on_user_change_status(user, from_nick, from_room,
                                           affiliation, role, show, status)
        if self.core.current_tab() is self:
            self.text_win.refresh()
            self.user_win.refresh_if_changed(self.users)
            self.info_header.refresh(self, self.text_win, user=self.own_user)
            self.input.refresh()
            self.core.doupdate()

    def on_non_member_kicked(self):
        """We have been kicked because the MUC is members-only"""
        self.add_message(
                '\x19%(info_col)s}You have been kicked because you '
                'are not a member and the room is now members-only.' % {
            'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
            typ=2)
        self.disconnect()

    def on_muc_shutdown(self):
        """We have been kicked because the MUC service is shutting down"""
        self.add_message(
                '\x19%(info_col)s}You have been kicked because the'
                ' MUC service is shutting down.' % {
            'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
            typ=2)
        self.disconnect()

    def on_user_join(self, from_nick, affiliation, show, status, role, jid, color):
        """
        When a new user joins the groupchat
        """
        deterministic = config.get_by_tabname('deterministic_nick_colors', self.name)
        user = User(from_nick, affiliation,
                    show, status, role, jid, deterministic, color)
        bisect.insort_left(self.users, user)
        hide_exit_join = config.get_by_tabname('hide_exit_join',
                                               self.general_jid)
        if hide_exit_join != 0:
            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(user.color)
            else:
                color = 3
            info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
            spec_col = dump_tuple(get_theme().COLOR_JOIN_CHAR)
            char_join = get_theme().CHAR_JOIN
            if not jid.full:
                msg = ('\x19%(color_spec)s}%(spec)s \x19%(color)s}%(nick)s'
                       '\x19%(info_col)s} joined the room') % {
                            'nick': from_nick, 'spec': char_join,
                            'color': color,
                            'info_col': info_col,
                            'color_spec': spec_col,
                            }
            else:
                msg = ('\x19%(color_spec)s}%(spec)s \x19%(color)s}%(nick)s'
                       '\x19%(info_col)s} (\x19%(jid_color)s}%(jid)s\x19'
                       '%(info_col)s}) joined the room') % {
                            'spec': char_join, 'nick': from_nick,
                            'color':color, 'jid':jid.full,
                            'info_col': info_col,
                            'jid_color': dump_tuple(get_theme().COLOR_MUC_JID),
                            'color_spec': spec_col,
                            }
            self.add_message(msg, typ=2)
        self.core.on_user_rejoined_private_conversation(self.name, from_nick)

    def on_user_nick_change(self, presence, user, from_nick, from_room):
        new_nick = presence.xml.find('{%s}x/{%s}item' % (NS_MUC_USER, NS_MUC_USER)
                                     ).attrib['nick']
        if user.nick == self.own_nick:
            self.own_nick = new_nick
            # also change our nick in all private discussions of this room
            self.core.handler.on_muc_own_nickchange(self)
        else:
            color = config.get_by_tabname(new_nick, 'muc_colors')
            if color != '':
                deterministic = config.get_by_tabname('deterministic_nick_colors',
                                                      self.name)
                user.change_color(color, deterministic)
        user.change_nick(new_nick)
        self.users.remove(user)
        bisect.insort_left(self.users, user)

        if config.get_by_tabname('display_user_color_in_join_part',
                                 self.general_jid):
            color = dump_tuple(user.color)
        else:
            color = 3
        info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        self.add_message('\x19%(color)s}%(old)s\x19%(info_col)s} is'
                         ' now known as \x19%(color)s}%(new)s' % {
                              'old':from_nick, 'new':new_nick,
                              'color':color, 'info_col': info_col},
                         typ=2)
        # rename the private tabs if needed
        self.core.rename_private_tabs(self.name, from_nick, user)

    def on_user_banned(self, presence, user, from_nick):
        """
        When someone is banned from a muc
        """
        self.users.remove(user)
        by = presence.xml.find('{%s}x/{%s}item/{%s}actor' %
                               (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        reason = presence.xml.find('{%s}x/{%s}item/{%s}reason' %
                                   (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        by = by.attrib['jid'] if by is not None else None

        info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        char_kick = get_theme().CHAR_KICK

        if from_nick == self.own_nick: # we are banned
            if by:
                kick_msg = ('\x191}%(spec)s \x193}You\x19%(info_col)s}'
                            ' have been banned by \x194}%(by)s') % {
                                'spec': char_kick, 'by': by,
                                'info_col': info_col}
            else:
                kick_msg = ('\x191}%(spec)s \x193}You\x19'
                            '%(info_col)s} have been banned.') % {
                                'spec': char_kick, 'info_col': info_col}
            self.core.disable_private_tabs(self.name, reason=kick_msg)
            self.disconnect()
            self.refresh_tab_win()
            self.core.current_tab().input.refresh()
            self.core.doupdate()
            if config.get_by_tabname('autorejoin', self.general_jid):
                delay = config.get_by_tabname('autorejoin_delay',
                                              self.general_jid)
                delay = common.parse_str_to_secs(delay)
                if delay <= 0:
                    muc.join_groupchat(self.core, self.name, self.own_nick)
                else:
                    self.core.add_timed_event(timed_events.DelayedEvent(
                                                  delay,
                                                  muc.join_groupchat,
                                                  self.core,
                                                  self.name,
                                                  self.own_nick))

        else:
            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(user.color)
            else:
                color = 3

            if by:
                kick_msg = ('\x191}%(spec)s \x19%(color)s}'
                            '%(nick)s\x19%(info_col)s} '
                            'has been banned by \x194}%(by)s') % {
                                'spec': char_kick, 'nick': from_nick,
                                'color': color, 'by': by,
                                'info_col': info_col}
            else:
                kick_msg = ('\x191}%(spec)s \x19%(color)s}%(nick)s'
                            '\x19%(info_col)s} has been banned') % {
                                'spec': char_kick, 'nick': from_nick,
                                'color': color, 'info_col': info_col}
        if reason is not None and reason.text:
            kick_msg += ('\x19%(info_col)s} Reason: \x196}'
                         '%(reason)s\x19%(info_col)s}') % {
                            'reason': reason.text, 'info_col': info_col}
        self.add_message(kick_msg, typ=2)

    def on_user_kicked(self, presence, user, from_nick):
        """
        When someone is kicked from a muc
        """
        self.users.remove(user)
        actor_elem = presence.xml.find('{%s}x/{%s}item/{%s}actor' %
                                       (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        reason = presence.xml.find('{%s}x/{%s}item/{%s}reason' %
                                   (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        by = None
        info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        char_kick = get_theme().CHAR_KICK
        if actor_elem is not None:
            by = actor_elem.get('nick') or actor_elem.get('jid')
        if from_nick == self.own_nick: # we are kicked
            if by:
                kick_msg = ('\x191}%(spec)s \x193}You\x19'
                            '%(info_col)s} have been kicked'
                            ' by \x193}%(by)s') % {
                                 'spec': char_kick, 'by': by,
                                 'info_col': info_col}
            else:
                kick_msg = ('\x191}%(spec)s \x193}You\x19%(info_col)s}'
                            ' have been kicked.') % {
                                 'spec': char_kick,
                                 'info_col': info_col}
            self.core.disable_private_tabs(self.name, reason=kick_msg)
            self.disconnect()
            self.refresh_tab_win()
            self.core.current_tab().input.refresh()
            self.core.doupdate()
            # try to auto-rejoin
            if config.get_by_tabname('autorejoin', self.general_jid):
                delay = config.get_by_tabname('autorejoin_delay',
                                              self.general_jid)
                delay = common.parse_str_to_secs(delay)
                if delay <= 0:
                    muc.join_groupchat(self.core, self.name, self.own_nick)
                else:
                    self.core.add_timed_event(timed_events.DelayedEvent(
                        delay,
                        muc.join_groupchat,
                        self.core,
                        self.name,
                        self.own_nick))
        else:
            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(user.color)
            else:
                color = 3
            if by:
                kick_msg = ('\x191}%(spec)s \x19%(color)s}%(nick)s'
                            '\x19%(info_col)s} has been kicked by '
                            '\x193}%(by)s') % {
                                'spec': char_kick, 'nick':from_nick,
                                'color':color, 'by':by, 'info_col': info_col}
            else:
                kick_msg = ('\x191}%(spec)s \x19%(color)s}%(nick)s'
                            '\x19%(info_col)s} has been kicked') % {
                                'spec': char_kick, 'nick': from_nick,
                                'color':color, 'info_col': info_col}
        if reason is not None and reason.text:
            kick_msg += ('\x19%(info_col)s} Reason: \x196}'
                         '%(reason)s') % {
                            'reason': reason.text, 'info_col': info_col}
        self.add_message(kick_msg, typ=2)

    def on_user_leave_groupchat(self, user, jid, status, from_nick, from_room):
        """
        When an user leaves a groupchat
        """
        self.users.remove(user)
        if self.own_nick == user.nick:
            # We are now out of the room.
            # Happens with some buggy (? not sure) servers
            self.disconnect()
            self.core.disable_private_tabs(from_room)
            self.refresh_tab_win()

        hide_exit_join = config.get_by_tabname('hide_exit_join',
                                               self.general_jid)

        if hide_exit_join <= -1 or user.has_talked_since(hide_exit_join):
            if config.get_by_tabname('display_user_color_in_join_part',
                                     self.general_jid):
                color = dump_tuple(user.color)
            else:
                color = 3
            info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
            spec_col = dump_tuple(get_theme().COLOR_QUIT_CHAR)

            if not jid.full:
                leave_msg = ('\x19%(color_spec)s}%(spec)s \x19%(color)s}'
                             '%(nick)s\x19%(info_col)s} has left the '
                             'room') % {
                                  'nick':from_nick, 'color':color,
                                  'spec':get_theme().CHAR_QUIT,
                                  'info_col': info_col,
                                  'color_spec': spec_col}
            else:
                jid_col = dump_tuple(get_theme().COLOR_MUC_JID)
                leave_msg = ('\x19%(color_spec)s}%(spec)s \x19%(color)s}'
                             '%(nick)s\x19%(info_col)s} (\x19%(jid_col)s}'
                             '%(jid)s\x19%(info_col)s}) has left the '
                             'room') % {
                                  'spec':get_theme().CHAR_QUIT,
                                  'nick':from_nick, 'color':color,
                                  'jid':jid.full, 'info_col': info_col,
                                  'color_spec': spec_col,
                                  'jid_col': jid_col}
            if status:
                leave_msg += ' (\x19o%s\x19%s})' % (status, info_col)
            self.add_message(leave_msg, typ=2)
        self.core.on_user_left_private_conversation(from_room, user,
                                                    status)

    def on_user_change_status(
            self, user, from_nick, from_room, affiliation, role, show, status):
        """
        When an user changes her status
        """
        # build the message
        display_message = False # flag to know if something significant enough
                                # to be displayed has changed
        if config.get_by_tabname('display_user_color_in_join_part',
                                 self.general_jid):
            color = dump_tuple(user.color)
        else:
            color = 3
        if from_nick == self.own_nick:
            msg = '\x19%(color)s}You\x19%(info_col)s} changed: ' % {
                  'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
                  'color': color}
        else:
            msg = '\x19%(color)s}%(nick)s\x19%(info_col)s} changed: ' % {
                  'nick': from_nick, 'color': color,
                  'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)}
        if affiliation != user.affiliation:
            msg += 'affiliation: %s, ' % affiliation
            display_message = True
        if role != user.role:
            msg += 'role: %s, ' % role
            display_message = True
        if show != user.show and show in SHOW_NAME:
            msg += 'show: %s, ' % SHOW_NAME[show]
            display_message = True
        if status != user.status:
            # if the user sets his status to nothing
            if status:
                msg += 'status: %s, ' % status
                display_message = True
            elif show in SHOW_NAME and show == user.show:
                msg += 'show: %s, ' % SHOW_NAME[show]
                display_message = True
        if not display_message:
            return
        msg = msg[:-2] # remove the last ", "
        hide_status_change = config.get_by_tabname('hide_status_change',
                                                   self.general_jid)
        if hide_status_change < -1:
            hide_status_change = -1
        if ((hide_status_change == -1 or \
                user.has_talked_since(hide_status_change) or\
                user.nick == self.own_nick)\
                and\
                (affiliation != user.affiliation or\
                    role != user.role or\
                    show != user.show or\
                    status != user.status))\
                      or\
                        (affiliation != user.affiliation or\
                          role != user.role):
            # display the message in the room
            self._text_buffer.add_message(msg)
        self.core.on_user_changed_status_in_private('%s/%s' %
                                                      (from_room, from_nick),
                                                    Status(show, status))
        self.users.remove(user)
        # finally, effectively change the user status
        user.update(affiliation, show, status, role)
        bisect.insort_left(self.users, user)

    def disconnect(self):
        """
        Set the state of the room as not joined, so
        we can know if we can join it, send messages to it, etc
        """
        self.users = []
        if self is not self.core.current_tab():
            self.state = 'disconnected'
        self.joined = False
        self.disable_self_ping_event()

    def get_single_line_topic(self):
        """
        Return the topic as a single-line string (for the window header)
        """
        return self.topic.replace('\n', '|')

    def log_message(self, txt, nickname, time=None, typ=1):
        """
        Log the messages in the archives, if it needs
        to be
        """
        if time is None and self.joined:    # don't log the history messages
            if not logger.log_message(self.name, nickname, txt, typ=typ):
                self.core.information('Unable to write in the log file',
                                      'Error')

    def do_highlight(self, txt, time, nickname, corrected=False):
        """
        Set the tab color and returns the nick color
        """
        highlighted = False
        if (not time or corrected) and nickname and nickname != self.own_nick and self.joined:

            if re.search(r'\b' + self.own_nick.lower() + r'\b', txt.lower()):
                if self.state != 'current':
                    self.state = 'highlight'
                highlighted = True
            else:
                highlight_words = config.get_by_tabname('highlight_on',
                                                        self.general_jid)
                highlight_words = highlight_words.split(':')
                for word in highlight_words:
                    if word and word.lower() in txt.lower():
                        if self.state != 'current':
                            self.state = 'highlight'
                        highlighted = True
                        break
        if highlighted:
            beep_on = config.get('beep_on').split()
            if 'highlight' in beep_on and 'message' not in beep_on:
                if not config.get_by_tabname('disable_beep', self.name):
                    curses.beep()
        return highlighted

    def get_user_by_name(self, nick):
        """
        Gets the user associated with the given nick, or None if not found
        """
        for user in self.users:
            if user.nick == nick:
                return user
        return None

    def add_message(self, txt, time=None, nickname=None, **kwargs):
        """
        Note that user can be None even if nickname is not None. It happens
        when we receive an history message said by someone who is not
        in the room anymore
        Return True if the message highlighted us. False otherwise.
        """

        # reset self-ping interval
        if self.self_ping_event:
            self.enable_self_ping_event()

        self.log_message(txt, nickname, time=time, typ=kwargs.get('typ', 1))
        args = dict()
        for key, value in kwargs.items():
            if key not in ('typ', 'forced_user'):
                args[key] = value
        if nickname is not None:
            user = self.get_user_by_name(nickname)
        else:
            user = None

        if user:
            user.set_last_talked(datetime.now())
            args['user'] = user
        if not user and kwargs.get('forced_user'):
            args['user'] = kwargs['forced_user']

        if (not time and nickname and nickname != self.own_nick
                    and self.state != 'current'):
            if (self.state != 'highlight' and
                    config.get_by_tabname('notify_messages', self.name)):
                self.state = 'message'
        if time and not txt.startswith('/me'):
            txt = '\x19%(info_col)s}%(txt)s' % {
                    'txt': txt,
                    'info_col': dump_tuple(get_theme().COLOR_LOG_MSG)}
        elif not nickname:
            txt = '\x19%(info_col)s}%(txt)s' % {
                    'txt': txt,
                    'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)}
        elif not kwargs.get('highlight'):                   # TODO
            args['highlight'] = self.do_highlight(txt, time, nickname)
        time = time or datetime.now()
        self._text_buffer.add_message(txt, time, nickname, **args)
        return args.get('highlight', False)

    def modify_message(self, txt, old_id, new_id,
                       time=None, nickname=None, user=None, jid=None):
        self.log_message(txt, nickname, time=time, typ=1)
        highlight = self.do_highlight(txt, time, nickname, corrected=True)
        message = self._text_buffer.modify_message(txt, old_id, new_id,
                                                   highlight=highlight,
                                                   time=time, user=user,
                                                   jid=jid)
        if message:
            self.text_win.modify_message(old_id, message)
            return highlight
        return False

    def matching_names(self):
        return [(1, safeJID(self.name).user), (3, self.name)]

    def enable_self_ping_event(self):
        delay = config.get_by_tabname("self_ping_delay", self.general_jid, default=0)
        if delay <= 0:          # use 0 or some negative value to disable it
            return
        self.disable_self_ping_event()
        self.self_ping_event = timed_events.DelayedEvent(delay, self.send_self_ping)
        self.core.add_timed_event(self.self_ping_event)

    def disable_self_ping_event(self):
        if self.self_ping_event is not None:
            self.core.remove_timed_event(self.self_ping_event)
            self.self_ping_event = None

    def send_self_ping(self):
        to = self.name + "/" + self.own_nick
        self.core.xmpp.plugin['xep_0199'].send_ping(jid=to,
                                                    callback=self.on_self_ping_result,
                                                    timeout_callback=self.on_self_ping_failed,
                                                    timeout=60)

    def on_self_ping_result(self, iq):
        if iq["type"] == "error":
            self.command_cycle(iq["error"]["text"] or "not in this room")
            self.core.refresh_window()
        else:                   # Re-send a self-ping in a few seconds
            self.enable_self_ping_event()

    def search_for_color(self, nick):
        """
        Search for the color of a nick in the config file.
        Also, look at the colors of its possible aliases if nick_color_aliases
        is set.
        """
        color = config.get_by_tabname(nick, 'muc_colors')
        if color != '':
            return color
        nick_color_aliases = config.get_by_tabname('nick_color_aliases', self.name)
        if nick_color_aliases:
            nick_alias = re.sub('^_*(.*?)_*$', '\\1', nick)
            color = config.get_by_tabname(nick_alias, 'muc_colors')
        return color

    def on_self_ping_failed(self, iq):
        self.command_cycle("the MUC server is not responding")
        self.core.refresh_window()
