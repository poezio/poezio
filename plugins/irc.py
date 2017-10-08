"""
Plugin destined to be used together with the Biboumi IRC gateway.

For more information about Biboumi, please see the `official website`_.

This plugin is here as a non-default extension of the poezio configuration
made to work with IRC rooms and logins. It also defines commands aimed at
reducing the amount of effort needed to navigate smoothly between IRC and
XMPP rooms.

Configuration
-------------

Every feature of this plugin is centered around its :ref:`configuration file <plugin-configuration>`,
so you have to make sure it is filled properly.

Global configuration
~~~~~~~~~~~~~~~~~~~~
.. glossary::
    :sorted:

    gateway
        **Default:** ``irc.poez.io``

        The JID of the IRC gateway to use. If empty, irc.poez.io will be
        used. Please try to run your own, though, it’s painless to setup.

    initial_connect
        **Default:** ``true``

        Set to ``true`` if you want to join all the rooms and try to
        authenticate with nickserv when the plugin gets loaded. If it set to
        ``false``, you will have to use the :term:`/irc_login` command to
        authenticate, and the :term:`/irc_join` command to join
        preconfigured rooms.

.. note:: There is no nickname option because the default from poezio will be used.

Server-specific configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Write a configuration section for each server, with the server address as the
section name, and the following options:


.. glossary::
    :sorted:


    login_command
        **Default:** ``[empty]``

        The command used to identify with the services (e.g. ``IDENTIFY mypassword``).

    login_nick
        **Default:** ``[empty]``

        The nickname to whom the auth command will be sent.

    nickname
        **Default:** ``[empty]``

        Your nickname on this server. If empty, the default configuration will be used.

    rooms [IRC plugin]
        **Default:** ``[empty]``

        The list of rooms to join on this server (e.g. ``#room1:#room2``).

.. note:: If no login_command or login_nick is set, the authentication phase
        won’t take place and you will join the rooms without authentication
        with nickserv or whatever.

Commands
~~~~~~~~

.. glossary::
    :sorted:

    /irc_login
        **Usage:** ``/irc_login [server1] [server2]…``

        Authenticate with the specified servers if they are correctly
        configured. If no servers are provided, the plugin will try
        them all. (You need to set :term:`login_nick` and
        :term:`login_command` as well)

    /irc_join
        **Usage:** ``/irc_join <room or server>``

        Join the specified room on the same server as the current tab (can
        be a private conversation or a chatroom). If a server that appears
        in the conversation is specified instead of a room, the plugin
        will try to join all the rooms configured with autojoin on that
        server.

    /irc_query
        **Usage:** ``/irc_query <nickname> [message]``

        Open a private conversation with the given nickname, on the same IRC
        server as the current tab (can be a private conversation or a
        chatroom).  Doing `/irc_query foo "hello there"` when the current
        tab is #foo%irc.example.com@biboumi.example.com is equivalent to
        ``/message foo%irc.example.com@biboumi.example.com "hello there"``

Example configuration
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

    [irc]
    gateway = irc.poez.io

    [irc.freenode.net]
    nickname = mynick
    login_nick = nickserv
    login_command = identify mypassword
    rooms = #testroom1:#testroom2

    [irc.geeknode.org]
    nickname = anothernick
    login_nick = C
    login_command = nick identify mypassword
    rooms = #testvroum



.. _official website: http://biboumi.louiz.org/

"""

from poezio.plugin import BasePlugin
from poezio.decorators import command_args_parser
from poezio.core.structs import Completion
from poezio import common
from poezio import tabs

class Plugin(BasePlugin):

    def init(self):
        if self.config.get('initial_connect', True):
            self.initial_connect()

        self.api.add_command('irc_login', self.command_irc_login,
                             usage='[server] [server]…',
                             help=('Connect to the specified servers if they '
                                   'exist in the configuration and the login '
                                   'options are set. If not is given, the '
                                   'plugin will try all the sections in the '
                                   'configuration.'),
                             short='Login to irc servers with nickserv',
                             completion=self.completion_irc_login)

        self.api.add_command('irc_join', self.command_irc_join,
                             usage='<room or server>',
                             help=('Join <room> in the same server as the '
                                   'current tab (if it is an IRC tab). Or '
                                   'join all the preconfigured rooms in '
                                   '<server> '),
                             short='Join irc rooms more easily',
                             completion=self.completion_irc_join)

        self.api.add_command('irc_query', self.command_irc_query,
                             usage='<nickname> [message]',
                             help=('Open a private conversation with the '
                                   'given <nickname>, on the current IRC '
                                   'server.  Optionally immediately send '
                                   'the given message. For example, if the '
                                   'current tab is #foo%irc.example.com@'
                                   'biboumi.example.com, doing `/irc_query '
                                   'nick "hi there"` is equivalent to '
                                   '`/message nick%irc.example.com@biboumi.'
                                   'example.com "hi there"`'),
                             short='Open a private conversation with an IRC user')

    def join(self, gateway, server):
        "Join irc rooms on a server"
        nick = self.config.get_by_tabname('nickname', server, default='') or self.core.own_nick
        rooms = self.config.get_by_tabname('rooms', server, default='').split(':')
        for room in rooms:
            room = '{}%{}@{}/{}'.format(room, server, gateway, nick)
            self.core.command.join(room)

    def initial_connect(self):
        gateway = self.config.get('gateway', 'irc.poez.io')
        sections = self.config.sections()

        for section in (s for s in sections if s != 'irc'):

            room_suffix = '%{}@{}'.format(section, gateway)

            already_opened = False
            for tab in self.core.tabs:
                if tab.name.endswith(room_suffix) and tab.joined:
                    already_opened = True
                    break

            login_command = self.config.get_by_tabname('login_command', section, default='')
            login_nick = self.config.get_by_tabname('login_nick', section, default='')
            nick = self.config.get_by_tabname('nickname', section, default='') or self.core.own_nick
            if login_command and login_nick:
                def login(gw, sect, log_nick, log_cmd, room_suff):
                    dest = '{}%{}'.format(log_nick, room_suff)
                    self.core.xmpp.send_message(mto=dest, mbody=log_cmd, mtype='chat')
                    delayed = self.api.create_delayed_event(5, self.join, gw, sect)
                    self.api.add_timed_event(delayed)
                if not already_opened:
                    self.core.command.join(room_suffix + '/' + nick)
                    delayed = self.api.create_delayed_event(5, login, gateway, section,
                                                            login_nick, login_command,
                                                            room_suffix[1:])
                    self.api.add_timed_event(delayed)
                else:
                    login(gateway, section, login_nick, login_command, room_suffix[1:])
            elif not already_opened:
                self.join(gateway, section)

    @command_args_parser.quoted(0, -1)
    def command_irc_login(self, args):
        """
        /irc_login [server] [server]…
        """
        gateway = self.config.get('gateway', 'irc.poez.io')
        if args:
            not_present = []
            sections = self.config.sections()
            for section in args:
                if section not in sections:
                    not_present.append(section)
                    continue
                login_command = self.config.get_by_tabname('login_command', section, default='')
                login_nick = self.config.get_by_tabname('login_nick', section, default='')
                if not login_command and not login_nick:
                    not_present.append(section)
                    continue

                room_suffix = '%{}@{}'.format(section, gateway)
                dest = '{}%{}'.format(login_nick, room_suffix[1:])
                self.core.xmpp.send_message(mto=dest, mbody=login_command, mtype='chat')
            if len(not_present) == 1:
                self.api.information('Section %s does not exist or is not configured' % not_present[0], 'Warning')
            elif len(not_present) > 1:
                self.api.information('Sections %s do not exist or are not configured' % ', '.join(not_present), 'Warning')
        else:
            sections = self.config.sections()

            for section in (s for s in sections if s != 'irc'):
                login_command = self.config.get_by_tabname('login_command', section, default='')
                login_nick = self.config.get_by_tabname('login_nick', section, default='')
                if not login_nick and not login_command:
                    continue

                room_suffix = '%{}@{}'.format(section, gateway)
                dest = '{}%{}'.format(login_nick, room_suffix[1:])
                self.core.xmpp.send_message(mto=dest, mbody=login_command, mtype='chat')


    def completion_irc_login(self, the_input):
        """
        completion for /irc_login
        """
        args = the_input.text.split()
        if '' in args:
            args.remove('')
        pos = the_input.get_argument_position()
        sections = self.config.sections()
        if 'irc' in sections:
            sections.remove('irc')
        for section in args:
            try:
                sections.remove(section)
            except:
                pass
        return Completion(the_input.new_completion, sections, pos)

    @command_args_parser.quoted(1, 1)
    def command_irc_join(self, args):
        """
        /irc_join <room or server>
        """
        if not args:
            return self.core.command.help('irc_join')
        sections = self.config.sections()
        if 'irc' in sections:
            sections.remove('irc')
        if args[0] in sections and self.config.get_by_tabname('rooms', args[0]):
            self.join_server_rooms(args[0])
        else:
            self.join_room(args[0])

    @command_args_parser.quoted(1, 1)
    def command_irc_query(self, args):
        """
        Open a private conversation with the given nickname, on the current IRC
        server.
        """
        if args is None:
            return self.core.command.help('irc_query')
        current_tab_info = self.get_current_tab_irc_info()
        if not current_tab_info:
            return
        server, gateway = current_tab_info
        nickname = args[0]
        message = None
        if len(args) == 2:
            message = args[1]
        jid = '{}%{}@{}'.format(nickname, server, gateway)
        if message:
            self.core.command.message('{} "{}"'.format(jid, message))
        else:
            self.core.command.message('{}'.format(jid))

    def join_server_rooms(self, section):
        """
        Join all the rooms configured for a section
        (section = irc server)
        """
        gateway = self.config.get('gateway', 'irc.poez.io')
        rooms = self.config.get_by_tabname('rooms', section).split(':')
        nick = self.config.get_by_tabname('nickname', section)
        if nick:
            nick = '/' + nick
        else:
            nick = ''
        suffix = '%{}@{}{}'.format(section, gateway, nick)

        for room in rooms:
            self.core.command.join(room + suffix)

    def join_room(self, name):
        """
        Join a room with only its name and the current tab
        """
        current_tab_info = self.get_current_tab_irc_info()
        if not current_tab_info:
            return
        server, gateway = current_tab_info

        room = '{}%{}@{}'.format(name, server, gateway)
        if self.config.get_by_tabname('nickname', server):
            room += '/' + self.config.get_by_tabname('nickname', server)

        self.core.command.join(room)

    def get_current_tab_irc_info(self):
        """
        Return a tuple with the irc server and the gateway hostnames of the
        current tab. If the current tab is not an IRC channel or private
        conversation, a warning is displayed and None is returned
        """
        gateway = self.config.get('gateway', 'irc.poez.io')
        current = self.core.current_tab()
        current_jid = common.safeJID(current.name)
        if not current_jid.server == gateway:
            self.api.information('The current tab does not appear to be an IRC one', 'Warning')
            return None
        if isinstance(current, tabs.OneToOneTab):
            if '%' not in current_jid.node:
                server = current_jid.node
            else:
                ignored, server = current_jid.node.rsplit('%', 1)
        elif isinstance(current, tabs.MucTab):
            if '%' not in current_jid.node:
                server = current_jid.node
            else:
                ignored, server = current_jid.node.rsplit('%', 1)
        else:
            self.api.information('The current tab does not appear to be an IRC one', 'Warning')
            return None
        return server, gateway

    def completion_irc_join(self, the_input):
        """
        completion for /irc_join
        """
        sections = self.config.sections()
        if 'irc' in sections:
            sections.remove('irc')
        return Completion(the_input.new_completion, sections, 1)


