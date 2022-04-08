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
        **Default:** ``irc.jabberfr.org``

        The JID of the IRC gateway to use. If empty, irc.jabberfr.org will be
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
    gateway = irc.jabberfr.org

    [irc.libera.chat]
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

import asyncio

from typing import Optional, Tuple, List, Any
from slixmpp.jid import JID, InvalidJID

from poezio.plugin import BasePlugin
from poezio.decorators import command_args_parser
from poezio.core.structs import Completion
from poezio import tabs


class Plugin(BasePlugin):
    default_config = {
        'irc': {
            "initial_connect": True,
            "gateway": "irc.jabberfr.org",
        }
    }

    def init(self) -> None:
        if self.config.getbool('initial_connect'):
            asyncio.create_task(
                self.initial_connect()
            )
        self.api.add_command(
            'irc_join',
            self.command_irc_join,
            usage='<room or server>',
            help=('Join <room> in the same server as the '
                  'current tab (if it is an IRC tab). Or '
                  'join all the preconfigured rooms in '
                  '<server> '),
            short='Join irc rooms more easily',
            completion=self.completion_irc_join)

        self.api.add_command(
            'irc_query',
            self.command_irc_query,
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

    async def join(self, gateway: str, server: JID) -> None:
        "Join irc rooms on a server"
        nick: str = self.config.get_by_tabname(
            'nickname', server, default='') or self.core.own_nick
        rooms: List[str] = self.config.get_by_tabname(
            'rooms', server, default='').split(':')
        joins = []
        for room in rooms:
            room = '{}%{}@{}/{}'.format(room, server, gateway, nick)
            joins.append(self.core.command.join(room))

        await asyncio.gather(*joins)

    async def initial_connect(self) -> None:
        gateway: str = self.config.getstr('gateway')
        sections: List[str] = self.config.sections()

        sections_jid = []
        for sect in sections:
            if sect == 'irc':
                continue
            try:
                sect_jid = JID(sect)
                if sect_jid != sect_jid.server:
                    self.api.information(f'Invalid server: {sect}', 'Warning')
                    continue
            except InvalidJID:
                self.api.information(f'Invalid server: {sect}', 'Warning')
                continue
            sections_jid.append(sect_jid)

        for section in sections_jid:
            room_suffix = '%{}@{}'.format(section, gateway)

            already_opened = False
            for tab in self.core.tabs:
                if tab.name.endswith(room_suffix) and tab.joined:
                    already_opened = True
                    break

            if not already_opened:
                await self.join(gateway, section)

    @command_args_parser.quoted(1, 1)
    async def command_irc_join(self, args: Optional[List[str]]) -> None:
        """
        /irc_join <room or server>
        """
        if not args:
            self.core.command.help('irc_join')
            return
        sections: List[str] = self.config.sections()
        if 'irc' in sections:
            sections.remove('irc')
        if args[0] in sections:
            try:
                section_jid = JID(args[0])
            except InvalidJID:
                self.api.information(f'Invalid address: {args[0]}', 'Error')
                return
            #self.config.get_by_tabname('rooms', section_jid)
            await self.join_server_rooms(section_jid)
        else:
            await self.join_room(args[0])

    @command_args_parser.quoted(1, 1)
    def command_irc_query(self, args: Optional[List[str]]) -> None:
        """
        Open a private conversation with the given nickname, on the current IRC
        server.
        """
        if args is None:
            self.core.command.help('irc_query')
            return
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

    async def join_server_rooms(self, section: JID) -> None:
        """
        Join all the rooms configured for a section
        (section = irc server)
        """
        gateway: str = self.config.getstr('gateway')
        rooms: List[str] = self.config.get_by_tabname('rooms', section).split(':')
        nick: str = self.config.get_by_tabname('nickname', section)
        if nick:
            nick = '/' + nick
        else:
            nick = ''
        suffix = '%{}@{}{}'.format(section, gateway, nick)

        for room in rooms:
            await self.core.command.join(room + suffix)

    async def join_room(self, name: str) -> None:
        """
        Join a room with only its name and the current tab
        """
        current_tab_info = self.get_current_tab_irc_info()
        if not current_tab_info:
            return
        server, gateway = current_tab_info
        try:
            server_jid = JID(server)
        except InvalidJID:
            return

        room = '{}%{}@{}'.format(name, server, gateway)
        if self.config.get_by_tabname('nickname', server_jid.bare):
            room += '/' + self.config.get_by_tabname('nickname', server_jid.bare)

        await self.core.command.join(room)

    def get_current_tab_irc_info(self) -> Optional[Tuple[str, str]]:
        """
        Return a tuple with the irc server and the gateway hostnames of the
        current tab. If the current tab is not an IRC channel or private
        conversation, a warning is displayed and None is returned
        """
        gateway: str = self.config.getstr('gateway')
        current = self.api.current_tab()
        current_jid = current.jid
        if not current_jid.server == gateway:
            self.api.information(
                'The current tab does not appear to be an IRC one', 'Warning')
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
            self.api.information(
                'The current tab does not appear to be an IRC one', 'Warning')
            return None
        return server, gateway

    def completion_irc_join(self, the_input: Any) -> Completion:
        """
        completion for /irc_join
        """
        sections: List[str] = self.config.sections()
        if 'irc' in sections:
            sections.remove('irc')
        return Completion(the_input.new_completion, sections, 1)
