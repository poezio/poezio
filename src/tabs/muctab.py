"""
Module for the MucTab

A MucTab is a tab for multi-user chats as defined in XEP-0045.

It keeps track of many things such as part/joins, maintains an
user list, and updates private tabs when necessary.
"""

from gettext import gettext as _

import logging
log = logging.getLogger(__name__)

import curses
import os
import random
import re
from datetime import datetime
from functools import reduce

from . import ChatTab, Tab

import common
import fixes
import multiuserchat as muc
import timed_events
import windows
import xhtml
from common import safeJID
from config import config
from decorators import refresh_wrapper
from logger import logger
from roster import roster
from theming import get_theme, dump_tuple
from user import User


SHOW_NAME = {
    'dnd': _('busy'),
    'away': _('away'),
    'xa': _('not available'),
    'chat': _('chatty'),
    '': _('available')
    }

NS_MUC_USER = 'http://jabber.org/protocol/muc#user'


class MucTab(ChatTab):
    """
    The tab containing a multi-user-chat room.
    It contains an userlist, an input, a topic, an information and a chat zone
    """
    message_type = 'groupchat'
    plugin_commands = {}
    plugin_keys = {}
    def __init__(self, jid, nick):
        self.joined = False
        ChatTab.__init__(self, jid)
        if self.joined == False:
            self._state = 'disconnected'
        self.own_nick = nick
        self.name = jid
        self.users = []
        self.privates = [] # private conversations
        self.topic = ''
        self.remote_wants_chatstates = True
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
                usage=_('<nickname>'),
                desc=_('Ignore a specified nickname.'),
                shortdesc=_('Ignore someone'),
                completion=self.completion_ignore)
        self.register_command('unignore', self.command_unignore,
                usage=_('<nickname>'),
                desc=_('Remove the specified nickname from the ignore list.'),
                shortdesc=_('Unignore someone.'),
                completion=self.completion_unignore)
        self.register_command('kick', self.command_kick,
                usage=_('<nick> [reason]'),
                desc=_('Kick the user with the specified nickname.'
                       ' You also can give an optional reason.'),
                shortdesc=_('Kick someone.'),
                completion=self.completion_quoted)
        self.register_command('ban', self.command_ban,
                usage=_('<nick> [reason]'),
                desc=_('Ban the user with the specified nickname.'
                       ' You also can give an optional reason.'),
                shortdesc='Ban someone',
                completion=self.completion_quoted)
        self.register_command('role', self.command_role,
                usage=_('<nick> <role> [reason]'),
                desc=_('Set the role of an user. Roles can be:'
                       ' none, visitor, participant, moderator.'
                       ' You also can give an optional reason.'),
                shortdesc=_('Set the role of an user.'),
                completion=self.completion_role)
        self.register_command('affiliation', self.command_affiliation,
                usage=_('<nick or jid> <affiliation>'),
                desc=_('Set the affiliation of an user. Affiliations can be:'
                       ' outcast, none, member, admin, owner.'),
                shortdesc=_('Set the affiliation of an user.'),
                completion=self.completion_affiliation)
        self.register_command('topic', self.command_topic,
                usage=_('<subject>'),
                desc=_('Change the subject of the room.'),
                shortdesc=_('Change the subject.'),
                completion=self.completion_topic)
        self.register_command('query', self.command_query,
                usage=_('<nick> [message]'),
                desc=_('Open a private conversation with <nick>. This nick'
                       ' has to be present in the room you\'re currently in.'
                       ' If you specified a message after the nickname, it '
                       'will immediately be sent to this user.'),
                shortdesc=_('Query an user.'),
                completion=self.completion_quoted)
        self.register_command('part', self.command_part,
                usage=_('[message]'),
                desc=_('Disconnect from a room. You can'
                       ' specify an optional message.'),
                shortdesc=_('Leave the room.'))
        self.register_command('close', self.command_close,
                usage=_('[message]'),
                desc=_('Disconnect from a room and close the tab.'
                       ' You can specify an optional message if '
                       'you are still connected.'),
                shortdesc=_('Close the tab.'))
        self.register_command('nick', self.command_nick,
                usage=_('<nickname>'),
                desc=_('Change your nickname in the current room.'),
                shortdesc=_('Change your nickname.'),
                completion=self.completion_nick)
        self.register_command('recolor', self.command_recolor,
                usage=_('[random]'),
                desc=_('Re-assign a color to all participants of the'
                       ' current room, based on the last time they talked.'
                       ' Use this if the participants currently talking '
                       'have too many identical colors. Use /recolor random'
                       ' for a non-deterministic result.'),
                shortdesc=_('Change the nicks colors.'),
                completion=self.completion_recolor)
        self.register_command('cycle', self.command_cycle,
                usage=_('[message]'),
                desc=_('Leave the current room and rejoin it immediately.'),
                shortdesc=_('Leave and re-join the room.'))
        self.register_command('info', self.command_info,
                usage=_('<nickname>'),
                desc=_('Display some information about the user '
                       'in the MUC: its/his/her role, affiliation,'
                       ' status and status message.'),
                shortdesc=_('Show an user\'s infos.'),
                completion=self.completion_info)
        self.register_command('configure', self.command_configure,
                desc=_('Configure the current room, through a form.'),
                shortdesc=_('Configure the room.'))
        self.register_command('version', self.command_version,
                usage=_('<jid or nick>'),
                desc=_('Get the software version of the given JID'
                       ' or nick in room (usually its XMPP client'
                       ' and Operating System).'),
                shortdesc=_('Get the software version of a jid.'),
                completion=self.completion_version)
        self.register_command('names', self.command_names,
                desc=_('Get the users in the room with their roles.'),
                shortdesc=_('List the users.'))
        self.register_command('invite', self.command_invite,
                desc=_('Invite a contact to this room'),
                usage=_('<jid> [reason]'),
                shortdesc=_('Invite a contact to this room'),
                completion=self.completion_invite)

        if self.core.xmpp.boundjid.server == "gmail.com": #gmail sucks
            del self.commands["nick"]

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

        return the_input.auto_completion(userlist, quotify=False)

    def completion_info(self, the_input):
        """Completion for /info"""
        compare_users = lambda x: x.last_talked
        userlist = []
        for user in sorted(self.users, key=compare_users, reverse=True):
            userlist.append(user.nick)
        return the_input.auto_completion(userlist, quotify=False)

    def completion_nick(self, the_input):
        """Completion for /nick"""
        nicks = [os.environ.get('USER'),
                 config.get('default_nick', ''),
                 self.core.get_bookmark_nickname(self.name)]
        nicks = [i for i in nicks if i]
        return the_input.auto_completion(nicks, '', quotify=False)

    def completion_recolor(self, the_input):
        if the_input.get_argument_position() == 1:
            return the_input.new_completion(['random'], 1, '', quotify=False)
        return True

    def completion_ignore(self, the_input):
        """Completion for /ignore"""
        userlist = [user.nick for user in self.users]
        if self.own_nick in userlist:
            userlist.remove(self.own_nick)
        userlist.sort()
        return the_input.auto_completion(userlist, quotify=False)

    def completion_role(self, the_input):
        """Completion for /role"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            userlist = [user.nick for user in self.users]
            if self.own_nick in userlist:
                userlist.remove(self.own_nick)
            return the_input.new_completion(userlist, 1, '', quotify=True)
        elif n == 2:
            possible_roles = ['none', 'visitor', 'participant', 'moderator']
            return the_input.new_completion(possible_roles, 2, '',
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
            return the_input.new_completion(userlist, 1, '', quotify=True)
        elif n == 2:
            possible_affiliations = ['none', 'member', 'admin',
                                     'owner', 'outcast']
            return the_input.new_completion(possible_affiliations, 2, '',
                                            quotify=True)

    def command_invite(self, args):
        """/invite <jid> [reason]"""
        args = common.shell_split(args)
        if len(args) == 1:
            jid, reason = args[0], ''
        elif len(args) == 2:
            jid, reason = args
        else:
            return self.core.command_help('invite')
        self.core.command_invite('%s %s "%s"' % (jid, self.name, reason))

    def completion_invite(self, the_input):
        """Completion for /invite"""
        n = the_input.get_argument_position(quoted=True)
        if n == 1:
            return the_input.new_completion(roster.jids(), 1, quotify=True)

    def scroll_user_list_up(self):
        self.user_win.scroll_up()
        self.user_win.refresh(self.users)
        self.input.refresh()

    def scroll_user_list_down(self):
        self.user_win.scroll_down()
        self.user_win.refresh(self.users)
        self.input.refresh()

    def command_info(self, arg):
        """
        /info <nick>
        """
        if not arg:
            return self.core.command_help('info')
        user = self.get_user_by_name(arg)
        if not user:
            return self.core.information(_("Unknown user: %s") % arg)
        theme = get_theme()
        if user.jid:
            user_jid = ' (\x19%s}%s\x19o)' % (
                            dump_tuple(theme.COLOR_MUC_JID),
                            user.jid)
        else:
            user_jid = ''
        info = _('\x19%s}%s\x19o%s: show: \x19%s}%s\x19o, affiliation:'
                 ' \x19%s}%s\x19o, role: \x19%s}%s\x19o%s') % (
                        dump_tuple(user.color),
                        arg,
                        user_jid,
                        dump_tuple(theme.color_show(user.show)),
                        user.show or 'Available',
                        dump_tuple(theme.color_role(user.role)),
                        user.affiliation or 'None',
                        dump_tuple(theme.color_role(user.role)),
                        user.role or 'None',
                        '\n%s' % user.status if user.status else '')
        self.core.information(info, 'Info')

    def command_configure(self, arg):
        """
        /configure
        """
        form = fixes.get_room_form(self.core.xmpp, self.name)
        if not form:
            self.core.information(
                    _('Could not retrieve the configuration form'),
                    _('Error'))
            return
        self.core.open_new_form(form, self.cancel_config, self.send_config)

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

    def command_cycle(self, arg):
        """/cycle [reason]"""
        self.command_part(arg)
        self.disconnect()
        self.user_win.pos = 0
        self.core.disable_private_tabs(self.name)
        self.core.command_join('"/%s"' % self.own_nick)

    def command_recolor(self, arg):
        """
        /recolor [random]
        Re-assign color to the participants of the room
        """
        arg = arg.strip()
        compare_users = lambda x: x.last_talked
        users = list(self.users)
        sorted_users = sorted(users, key=compare_users, reverse=True)
        # search our own user, to remove it from the list
        for user in sorted_users:
            if user.nick == self.own_nick:
                sorted_users.remove(user)
                user.color = get_theme().COLOR_OWN_NICK
        colors = list(get_theme().LIST_COLOR_NICKNAMES)
        if arg and arg == 'random':
            random.shuffle(colors)
        for i, user in enumerate(sorted_users):
            user.color = colors[i % len(colors)]
        self.text_win.rebuild_everything(self._text_buffer)
        self.user_win.refresh(self.users)
        self.text_win.refresh()
        self.input.refresh()

    def command_version(self, arg):
        """
        /version <jid or nick>
        """
        def callback(res):
            if not res:
                return self.core.information(_('Could not get the software '
                                               'version from %s') % (jid,),
                                             _('Warning'))
            version = _('%s is running %s version %s on %s') % (
                         jid,
                         res.get('name') or _('an unknown software'),
                         res.get('version') or _('unknown'),
                         res.get('os') or _('an unknown platform'))
            self.core.information(version, 'Info')
        if not arg:
            return self.core.command_help('version')
        if arg in [user.nick for user in self.users]:
            jid = safeJID(self.name).bare
            jid = safeJID(jid + '/' + arg)
        else:
            jid = safeJID(arg)
        fixes.get_version(self.core.xmpp, jid,
                callback=callback)

    def command_nick(self, arg):
        """
        /nick <nickname>
        """
        if not arg:
            return self.core.command_help('nick')
        nick = arg
        if not self.joined:
            return self.core.information(_('/nick only works in joined rooms'),
                                         _('Info'))
        current_status = self.core.get_status()
        if not safeJID(self.name + '/' + nick):
            return self.core.information('Invalid nick', 'Info')
        muc.change_nick(self.core, self.name, nick,
                        current_status.message,
                        current_status.show)

    def command_part(self, arg):
        """
        /part [msg]
        """
        arg = arg.strip()
        msg = None
        if self.joined:
            info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
            char_quit = get_theme().CHAR_QUIT
            spec_col = dump_tuple(get_theme().COLOR_QUIT_CHAR)

            if config.get_by_tabname('display_user_color_in_join_part', True,
                                     self.general_jid, True):
                color = dump_tuple(get_theme().COLOR_OWN_NICK)
            else:
                color = 3

            if arg:
                msg = _('\x19%(color_spec)s}%(spec)s\x19%(info_col)s} '
                        'You (\x19%(color)s}%(nick)s\x19%(info_col)s})'
                        ' left the chatroom'
                        ' (\x19o%(reason)s\x19%(info_col)s})') % {
                            'info_col': info_col, 'reason': arg,
                            'spec': char_quit, 'color': color,
                            'color_spec': spec_col,
                            'nick': self.own_nick,
                        }
            else:
                msg = _('\x19%(color_spec)s}%(spec)s\x19%(info_col)s} '
                        'You (\x19%(color)s}%(nick)s\x19%(info_col)s})'
                        ' left the chatroom') % {
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

    def command_close(self, arg):
        """
        /close [msg]
        """
        self.command_part(arg)
        self.core.close_tab()

    def command_query(self, arg):
        """
        /query <nick> [message]
        """
        args = common.shell_split(arg)
        if len(args) < 1:
            return
        nick = args[0]
        r = None
        for user in self.users:
            if user.nick == nick:
                r = self.core.open_private_window(self.name, user.nick)
        if r and len(args) > 1:
            msg = args[1]
            self.core.current_tab().command_say(
                    xhtml.convert_simple_to_full_colors(msg))
        if not r:
            self.core.information(_("Cannot find user: %s" % nick), 'Error')

    def command_topic(self, arg):
        """
        /topic [new topic]
        """
        if not arg.strip():
            self._text_buffer.add_message(
                    _("\x19%s}The subject of the room is: %s") %
                        (dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
                         self.topic))
            self.refresh()
            return
        subject = arg
        muc.change_subject(self.core.xmpp, self.name, subject)

    def command_names(self, arg=None):
        """
        /names
        """
        if not self.joined:
            return
        color_visitor = dump_tuple(get_theme().COLOR_USER_VISITOR)
        color_other = dump_tuple(get_theme().COLOR_USER_NONE)
        color_moderator = dump_tuple(get_theme().COLOR_USER_MODERATOR)
        color_participant = dump_tuple(get_theme().COLOR_USER_PARTICIPANT)
        visitors, moderators, participants, others = [], [], [], []
        aff = {
                'owner': get_theme().CHAR_AFFILIATION_OWNER,
                'admin': get_theme().CHAR_AFFILIATION_ADMIN,
                'member': get_theme().CHAR_AFFILIATION_MEMBER,
                'none': get_theme().CHAR_AFFILIATION_NONE,
                }

        users = self.users[:]
        users.sort(key=lambda x: x.nick.lower())
        for user in users:
            color = aff.get(user.affiliation,
                            get_theme().CHAR_AFFILIATION_NONE)
            if user.role == 'visitor':
                visitors.append((user, color))
            elif user.role == 'participant':
                participants.append((user, color))
            elif user.role == 'moderator':
                moderators.append((user, color))
            else:
                others.append((user, color))

        buff = ['Users: %s \n' % len(self.users)]
        for moderator in moderators:
            buff.append('\x19%s}%s\x19o\x19%s}%s\x19o' % (
                    color_moderator, moderator[1],
                    dump_tuple(moderator[0].color), moderator[0].nick))
        for participant in participants:
            buff.append('\x19%s}%s\x19o\x19%s}%s\x19o' % (
                    color_participant, participant[1],
                    dump_tuple(participant[0].color), participant[0].nick))
        for visitor in visitors:
            buff.append('\x19%s}%s\x19o\x19%s}%s\x19o' % (
                    color_visitor, visitor[1],
                    dump_tuple(visitor[0].color), visitor[0].nick))
        for other in others:
            buff.append('\x19%s}%s\x19o\x19%s}%s\x19o' % (
                    color_other, other[1],
                    dump_tuple(other[0].color), other[0].nick))
        buff.append('\n')
        message = ' '.join(buff)

        self._text_buffer.add_message(message)
        self.text_win.refresh()
        self.input.refresh()

    def completion_topic(self, the_input):
        if the_input.get_argument_position() == 1:
            return the_input.auto_completion([self.topic], '', quotify=False)

    def completion_quoted(self, the_input):
        """Nick completion, but with quotes"""
        if the_input.get_argument_position(quoted=True) == 1:
            compare_users = lambda x: x.last_talked
            word_list = []
            for user in sorted(self.users, key=compare_users, reverse=True):
                if user.nick != self.own_nick:
                    word_list.append(user.nick)

            return the_input.new_completion(word_list, 1, quotify=True)

    def command_kick(self, arg):
        """
        /kick <nick> [reason]
        """
        args = common.shell_split(arg)
        if not args:
            self.core.command_help('kick')
        else:
            if len(args) > 1:
                msg = ' "%s"' % args[1]
            else:
                msg = ''
            self.command_role('"'+args[0]+ '" none'+msg)

    def command_ban(self, arg):
        """
        /ban <nick> [reason]
        """
        def callback(iq):
            if iq['type'] == 'error':
                self.core.room_error(iq, self.name)
        args = common.shell_split(arg)
        if not args:
            return self.core.command_help('ban')
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

    def command_role(self, arg):
        """
        /role <nick> <role> [reason]
        Changes the role of an user
        roles can be: none, visitor, participant, moderator
        """
        def callback(iq):
            if iq['type'] == 'error':
                self.core.room_error(iq, self.name)
        args = common.shell_split(arg)
        if len(args) < 2:
            self.core.command_help('role')
            return
        nick, role = args[0], args[1]
        if len(args) > 2:
            reason = ' '.join(args[2:])
        else:
            reason = ''
        if not self.joined or \
                not role in ('none', 'visitor', 'participant', 'moderator'):
            return
        if not safeJID(self.name + '/' + nick):
            return self.core('Invalid nick', 'Info')
        muc.set_user_role(self.core.xmpp, self.name, nick, reason, role,
                          callback=callback)

    def command_affiliation(self, arg):
        """
        /affiliation <nick> <role>
        Changes the affiliation of an user
        affiliations can be: outcast, none, member, admin, owner
        """
        def callback(iq):
            if iq['type'] == 'error':
                self.core.room_error(iq, self.name)
        args = common.shell_split(arg)
        if len(args) < 2:
            self.core.command_help('affiliation')
            return
        nick, affiliation = args[0], args[1].lower()
        if not self.joined:
            return
        if affiliation not in ('outcast', 'none', 'member', 'admin', 'owner'):
            self.core.command_help('affiliation')
            return
        if nick in [user.nick for user in self.users]:
            res = muc.set_user_affiliation(self.core.xmpp, self.name,
                                           affiliation, nick=nick,
                                           callback=callback)
        else:
            res = muc.set_user_affiliation(self.core.xmpp, self.name,
                                           affiliation, jid=safeJID(nick),
                                           callback=callback)
        if not res:
            self.core.information(_('Could not set affiliation'), _('Error'))

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
        if (config.get_by_tabname('send_chat_states', True, self.general_jid,
                True) and self.remote_wants_chatstates is not False):
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

    def command_xhtml(self, arg):
        message = self.generate_xhtml_message(arg)
        if message:
            message['type'] = 'groupchat'
            message.send()

    def command_ignore(self, arg):
        """
        /ignore <nick>
        """
        if not arg:
            self.core.command_help('ignore')
            return
        nick = arg
        user = self.get_user_by_name(nick)
        if not user:
            self.core.information(_('%s is not in the room') % nick)
        elif user in self.ignores:
            self.core.information(_('%s is already ignored') % nick)
        else:
            self.ignores.append(user)
            self.core.information(_("%s is now ignored") % nick, 'info')

    def command_unignore(self, arg):
        """
        /unignore <nick>
        """
        if not arg:
            self.core.command_help('unignore')
            return
        nick = arg
        user = self.get_user_by_name(nick)
        if not user:
            self.core.information(_('%s is not in the room') % nick)
        elif user not in self.ignores:
            self.core.information(_('%s is not ignored') % nick)
        else:
            self.ignores.remove(user)
            self.core.information(_('%s is now unignored') % nick)

    def completion_unignore(self, the_input):
        if the_input.get_argument_position() == 1:
            users = [user.nick for user in self.ignores]
            return the_input.auto_completion(users, quotify=False)

    def resize(self):
        """
        Resize the whole window. i.e. all its sub-windows
        """
        self.need_resize = False
        if config.get("hide_user_list", False) or self.size.tab_degrade_x:
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
        if config.get("hide_user_list", False) or self.size.tab_degrade_x:
            display_user_list = False
        else:
            display_user_list = True
        display_info_win = not self.size.tab_degrade_y

        self.topic_win.refresh(self.get_single_line_topic())
        self.text_win.refresh()
        if display_user_list:
            self.v_separator.refresh()
            self.user_win.refresh(self.users)
        self.info_header.refresh(self, self.text_win)
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
        after = config.get('after_completion', ',') + ' '
        input_pos = self.input.pos
        if ' ' not in self.input.get_text()[:input_pos] or (
                self.input.last_completion and
                    self.input.get_text()[:input_pos] ==
                    self.input.last_completion + after):
            add_after = after
        else:
            if not config.get('add_space_after_completion', True):
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
        if not config.get('show_muc_jid', True):
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
        if config.get_by_tabname('send_chat_states', True,
                self.general_jid, True) and not self.input.get_text():
            self.send_chat_state('inactive')
        self.check_scrolled()

    def on_gain_focus(self):
        self.state = 'current'
        if (self.text_win.built_lines and self.text_win.built_lines[-1] is None
                and not config.get('show_useless_separator', False)):
            self.text_win.remove_line_separator()
        curses.curs_set(1)
        if self.joined and config.get_by_tabname('send_chat_states', True,
                self.general_jid, True) and not self.input.get_text():
            self.send_chat_state('active')

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height-3:
            return
        if config.get("hide_user_list", False):
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
        for status_code in presence.findall(xpath):
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
        if not self.joined:     # user in the room BEFORE us.
            # ignore redondant presence message, see bug #1509
            if (from_nick not in [user.nick for user in self.users]
                    and typ != "unavailable"):
                new_user = User(from_nick, affiliation, show,
                                status, role, jid)
                self.users.append(new_user)
                self.core.events.trigger('muc_join', presence, self)
                if '110' in status_codes or self.own_nick == from_nick:
                    # second part of the condition is a workaround for old
                    # ejabberd or every gateway in the world that just do
                    # not send a 110 status code with the presence
                    self.own_nick = from_nick
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
                                             True, self.general_jid, True):
                        color = dump_tuple(new_user.color)
                    else:
                        color = 3

                    info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
                    warn_col = dump_tuple(get_theme().COLOR_WARNING_TEXT)
                    spec_col = dump_tuple(get_theme().COLOR_JOIN_CHAR)

                    self.add_message(
                        _('\x19%(color_spec)s}%(spec)s\x19%(info_col)s} You '
                          '(\x19%(nick_col)s}%(nick)s\x19%(info_col)s}) joined'
                          ' the chatroom') %
                            {
                            'nick': from_nick,
                            'spec': get_theme().CHAR_JOIN,
                            'color_spec': spec_col,
                            'nick_col': color,
                            'info_col': info_col,
                            },
                        typ=2)
                    if '201' in status_codes:
                        self.add_message(
                                _('\x19%(info_col)s}Info: The room '
                                  'has been created') %
                                   {'info_col': info_col},
                            typ=0)
                    if '170' in status_codes:
                        self.add_message(
                                _('\x19%(warn_col)s}Warning:\x19%(info_col)s}'
                                  ' This room is publicly logged') %
                                    {'info_col': info_col,
                                     'warn_col': warn_col},
                            typ=0)
                    if '100' in status_codes:
                        self.add_message(
                                _('\x19%(warn_col)s}Warning:\x19%(info_col)s}'
                                  ' This room is not anonymous.') %
                                    {'info_col': info_col,
                                     'warn_col': warn_col},
                            typ=0)
                    if self.core.current_tab() is not self:
                        self.refresh_tab_win()
                        self.core.current_tab().input.refresh()
                        self.core.doupdate()
                    self.core.enable_private_tabs(self.name)
        else:
            change_nick = '303' in status_codes
            kick = '307' in status_codes and typ == 'unavailable'
            ban = '301' in status_codes and typ == 'unavailable'
            shutdown = '332' in status_codes and typ == 'unavailable'
            non_member = '322' in status_codes and typ == 'unavailable'
            user = self.get_user_by_name(from_nick)
            # New user
            if not user:
                self.core.events.trigger('muc_join', presence, self)
                self.on_user_join(from_nick, affiliation, show, status, role,
                                  jid)
            # nick change
            elif change_nick:
                self.core.events.trigger('muc_nickchange', presence, self)
                self.on_user_nick_change(presence, user, from_nick, from_room)
            elif ban:
                self.core.events.trigger('muc_ban', presence, self)
                self.core.on_user_left_private_conversation(from_room,
                                                            from_nick, status)
                self.on_user_banned(presence, user, from_nick)
            # kick
            elif kick:
                self.core.events.trigger('muc_kick', presence, self)
                self.core.on_user_left_private_conversation(from_room,
                                                            from_nick, status)
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
            self.user_win.refresh(self.users)
            self.info_header.refresh(self, self.text_win)
            self.input.refresh()
            self.core.doupdate()

    def on_non_member_kicked(self):
        """We have been kicked because the MUC is members-only"""
        self.add_message(
                _('\x19%(info_col)s}You have been kicked because you '
                  'are not a member and the room is now members-only.') % {
            'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
            typ=2)
        self.disconnect()

    def on_muc_shutdown(self):
        """We have been kicked because the MUC service is shutting down"""
        self.add_message(
                _('\x19%(info_col)s}You have been kicked because the'
                  ' MUC service is shutting down.') % {
            'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)},
            typ=2)
        self.disconnect()

    def on_user_join(self, from_nick, affiliation, show, status, role, jid):
        """
        When a new user joins the groupchat
        """
        user = User(from_nick, affiliation,
                    show, status, role, jid)
        self.users.append(user)
        hide_exit_join = config.get_by_tabname('hide_exit_join', -1,
                                               self.general_jid, True)
        if hide_exit_join != 0:
            if config.get_by_tabname('display_user_color_in_join_part', True,
                    self.general_jid, True):
                color = dump_tuple(user.color)
            else:
                color = 3
            info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
            spec_col = dump_tuple(get_theme().COLOR_JOIN_CHAR)
            char_join = get_theme().CHAR_JOIN
            if not jid.full:
                msg = _('\x19%(color_spec)s}%(spec)s \x19%(color)s}%(nick)s'
                        '\x19%(info_col)s} joined the chatroom') % {
                            'nick': from_nick, 'spec': char_join,
                            'color': color,
                            'info_col': info_col,
                            'color_spec': spec_col,
                            }
            else:
                msg = _('\x19%(color_spec)s}%(spec)s \x19%(color)s}%(nick)s '
                        '\x19%(info_col)s}(\x19%(jid_color)s}%(jid)s\x19'
                        '%(info_col)s}) joined the chatroom') % {
                            'spec': char_join, 'nick': from_nick,
                            'color':color, 'jid':jid.full,
                            'info_col': info_col,
                            'jid_color': dump_tuple(get_theme().COLOR_MUC_JID),
                            'color_spec': spec_col,
                            }
            self.add_message(msg, typ=2)
        self.core.on_user_rejoined_private_conversation(self.name, from_nick)

    def on_user_nick_change(self, presence, user, from_nick, from_room):
        new_nick = presence.find('{%s}x/{%s}item' % (NS_MUC_USER, NS_MUC_USER)
                                ).attrib['nick']
        if user.nick == self.own_nick:
            self.own_nick = new_nick
            # also change our nick in all private discussions of this room
            self.core.on_muc_own_nickchange(self)
        user.change_nick(new_nick)

        if config.get_by_tabname('display_user_color_in_join_part', True,
                                 self.general_jid, True):
            color = dump_tuple(user.color)
        else:
            color = 3
        info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        self.add_message(_('\x19%(color)s}%(old)s\x19%(info_col)s} is'
                           ' now known as \x19%(color)s}%(new)s') % {
                              'old':from_nick, 'new':new_nick,
                              'color':color, 'info_col': info_col},
                         typ=2)
        # rename the private tabs if needed
        self.core.rename_private_tabs(self.name, from_nick, new_nick)

    def on_user_banned(self, presence, user, from_nick):
        """
        When someone is banned from a muc
        """
        self.users.remove(user)
        by = presence.find('{%s}x/{%s}item/{%s}actor' %
                            (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        reason = presence.find('{%s}x/{%s}item/{%s}reason' %
                                (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        by = by.attrib['jid'] if by is not None else None

        info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        char_kick = get_theme().CHAR_KICK

        if from_nick == self.own_nick: # we are banned
            if by:
                kick_msg = _('\x191}%(spec)s \x193}You\x19%(info_col)s}'
                             ' have been banned by \x194}%(by)s') % {
                                'spec': char_kick, 'by': by,
                                'info_col': info_col}
            else:
                kick_msg = _('\x191}%(spec)s \x193}You\x19'
                             '%(info_col)s} have been banned.') % {
                                'spec': char_kick, 'info_col': info_col}
            self.core.disable_private_tabs(self.name, reason=kick_msg)
            self.disconnect()
            self.refresh_tab_win()
            self.core.current_tab().input.refresh()
            self.core.doupdate()
            if config.get_by_tabname('autorejoin', False,
                                     self.general_jid, True):
                delay = config.get_by_tabname('autorejoin_delay', '5',
                                              self.general_jid, True)
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
                                     True, self.general_jid, True):
                color = dump_tuple(user.color)
            else:
                color = 3

            if by:
                kick_msg = _('\x191}%(spec)s \x19%(color)s}'
                             '%(nick)s\x19%(info_col)s} '
                             'has been banned by \x194}%(by)s') % {
                                'spec': char_kick, 'nick': from_nick,
                                'color': color, 'by': by,
                                'info_col': info_col}
            else:
                kick_msg = _('\x191}%(spec)s \x19%(color)s}%(nick)s'
                             '\x19%(info_col)s} has been banned') % {
                                'spec': char_kick, 'nick': from_nick,
                                'color': color, 'info_col': info_col}
        if reason is not None and reason.text:
            kick_msg += _('\x19%(info_col)s} Reason: \x196}'
                          '%(reason)s\x19%(info_col)s}') % {
                            'reason': reason.text, 'info_col': info_col}
        self.add_message(kick_msg, typ=2)

    def on_user_kicked(self, presence, user, from_nick):
        """
        When someone is kicked from a muc
        """
        self.users.remove(user)
        actor_elem = presence.find('{%s}x/{%s}item/{%s}actor' %
                                     (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        reason = presence.find('{%s}x/{%s}item/{%s}reason' %
                                (NS_MUC_USER, NS_MUC_USER, NS_MUC_USER))
        by = None
        info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        char_kick = get_theme().CHAR_KICK
        if actor_elem is not None:
            by = actor_elem.get('nick') or actor_elem.get('jid')
        if from_nick == self.own_nick: # we are kicked
            if by:
                kick_msg = _('\x191}%(spec)s \x193}You\x19'
                             '%(info_col)s} have been kicked'
                             ' by \x193}%(by)s') % {
                                 'spec': char_kick, 'by': by,
                                 'info_col': info_col}
            else:
                kick_msg = _('\x191}%(spec)s \x193}You\x19%(info_col)s}'
                             ' have been kicked.') % {
                                 'spec': char_kick,
                                 'info_col': info_col}
            self.core.disable_private_tabs(self.name, reason=kick_msg)
            self.disconnect()
            self.refresh_tab_win()
            self.core.current_tab().input.refresh()
            self.core.doupdate()
            # try to auto-rejoin
            if config.get_by_tabname('autorejoin', False,
                                     self.general_jid, True):
                delay = config.get_by_tabname('autorejoin_delay', "5",
                                              self.general_jid, True)
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
            if config.get_by_tabname('display_user_color_in_join_part', True,
                                     self.general_jid, True):
                color = dump_tuple(user.color)
            else:
                color = 3
            if by:
                kick_msg = _('\x191}%(spec)s \x19%(color)s}%(nick)s'
                             '\x19%(info_col)s} has been kicked by '
                             '\x193}%(by)s') % {
                                'spec': char_kick, 'nick':from_nick,
                                'color':color, 'by':by, 'info_col': info_col}
            else:
                kick_msg = _('\x191}%(spec)s \x19%(color)s}%(nick)s'
                             '\x19%(info_col)s} has been kicked') % {
                                'spec': char_kick, 'nick': from_nick,
                                'color':color, 'info_col': info_col}
        if reason is not None and reason.text:
            kick_msg += _('\x19%(info_col)s} Reason: \x196}'
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

        hide_exit_join = max(config.get_by_tabname('hide_exit_join', -1,
                                                   self.general_jid, True),
                             -1)

        if hide_exit_join == -1 or user.has_talked_since(hide_exit_join):
            if config.get_by_tabname('display_user_color_in_join_part', True,
                    self.general_jid, True):
                color = dump_tuple(user.color)
            else:
                color = 3
            info_col = dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
            spec_col = dump_tuple(get_theme().COLOR_QUIT_CHAR)

            if not jid.full:
                leave_msg = _('\x19%(color_spec)s}%(spec)s \x19%(color)s}'
                              '%(nick)s\x19%(info_col)s} has left the '
                              'chatroom') % {
                                  'nick':from_nick, 'color':color,
                                  'spec':get_theme().CHAR_QUIT,
                                  'info_col': info_col,
                                  'color_spec': spec_col}
            else:
                jid_col = dump_tuple(get_theme().COLOR_MUC_JID)
                leave_msg = _('\x19%(color_spec)s}%(spec)s \x19%(color)s}'
                              '%(nick)s\x19%(info_col)s} (\x19%(jid_col)s}'
                              '%(jid)s\x19%(info_col)s}) has left the '
                              'chatroom') % {
                                  'spec':get_theme().CHAR_QUIT,
                                  'nick':from_nick, 'color':color,
                                  'jid':jid.full, 'info_col': info_col,
                                  'color_spec': spec_col,
                                  'jid_col': jid_col}
            if status:
                leave_msg += ' (\x19o%s\x19%s})' % (status, info_col)
            self.add_message(leave_msg, typ=2)
        self.core.on_user_left_private_conversation(from_room, from_nick,
                                                    status)

    def on_user_change_status(
            self, user, from_nick, from_room, affiliation, role, show, status):
        """
        When an user changes her status
        """
        # build the message
        display_message = False # flag to know if something significant enough
                                # to be displayed has changed
        if config.get_by_tabname('display_user_color_in_join_part', True,
                self.general_jid, True):
            color = dump_tuple(user.color)
        else:
            color = 3
        if from_nick == self.own_nick:
            msg = _('\x19%(color)s}You\x19%(info_col)s} changed: ') % {
                    'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
                    'color': color}
        else:
            msg = _('\x19%(color)s}%(nick)s\x19%(info_col)s} changed: ') % {
                    'nick': from_nick, 'color': color,
                    'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)}
        if show not in SHOW_NAME:
            self.core.information(_("%s from room %s sent an invalid show: %s")
                                    % (from_nick, from_room, show),
                                  _("Warning"))
        if affiliation != user.affiliation:
            msg += _('affiliation: %s, ') % affiliation
            display_message = True
        if role != user.role:
            msg += _('role: %s, ') % role
            display_message = True
        if show != user.show and show in SHOW_NAME:
            msg += _('show: %s, ') % SHOW_NAME[show]
            display_message = True
        if status != user.status:
            # if the user sets his status to nothing
            if status:
                msg += _('status: %s, ') % status
                display_message = True
            elif show in SHOW_NAME and show == user.show:
                msg += _('show: %s, ') % SHOW_NAME[show]
                display_message = True
        if not display_message:
            return
        msg = msg[:-2] # remove the last ", "
        hide_status_change = config.get_by_tabname('hide_status_change', -1,
                                                   self.general_jid, True)
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
                                                    msg)
        # finally, effectively change the user status
        user.update(affiliation, show, status, role)

    def disconnect(self):
        """
        Set the state of the room as not joined, so
        we can know if we can join it, send messages to it, etc
        """
        self.users = []
        if self is not self.core.current_tab():
            self.state = 'disconnected'
        self.joined = False

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
                self.core.information(_('Unable to write in the log file'),
                                      _('Error'))

    def do_highlight(self, txt, time, nickname):
        """
        Set the tab color and returns the nick color
        """
        highlighted = False
        if not time and nickname and nickname != self.own_nick and self.joined:

            if re.search(r'\b' + self.own_nick.lower() + r'\b', txt.lower()):
                if self.state != 'current':
                    self.state = 'highlight'
                highlighted = True
            else:
                highlight_words = config.get_by_tabname('highlight_on', '',
                                                        self.general_jid,
                                                        True).split(':')
                for word in highlight_words:
                    if word and word.lower() in txt.lower():
                        if self.state != 'current':
                            self.state = 'highlight'
                        highlighted = True
                        break
        if highlighted:
            beep_on = config.get('beep_on', 'highlight private').split()
            if 'highlight' in beep_on and 'message' not in beep_on:
                if not config.get_by_tabname('disable_beep', False,
                                             self.name, False):
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
                    config.get_by_tabname('notify_messages',
                                          True, self.name)):
                self.state = 'message'
        if time:
            txt = '\x19%(info_col)s}%(txt)s' % {
                    'txt': txt,
                    'info_col': dump_tuple(get_theme().COLOR_LOG_MSG)}
        elif (not nickname or time) and not txt.startswith('/me '):
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
        highlight = self.do_highlight(txt, time, nickname)
        message = self._text_buffer.modify_message(txt, old_id, new_id,
                                                   highlight=highlight,
                                                   time=time, user=user,
                                                   jid=jid)
        if message:
            self.text_win.modify_message(old_id, message)
            self.core.refresh_window()
            return highlight
        return False

    def matching_names(self):
        return [(1, safeJID(self.name).user), (3, self.name)]


