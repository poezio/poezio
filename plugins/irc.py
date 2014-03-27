"""
Plugin destined to be used together with the Biboumi IRC gateway.

For more information about Biboumi, please see the `official website`_.

This plugin is here as a non-default extension of the poezio configuration
made to work with IRC rooms and logins. Therefore, it does not define any
commands or do anything useful except on load.

Configuration
-------------

Global configuration
~~~~~~~~~~~~~~~~~~~~
.. glossary::
    :sorted:

    gateway
        **Default:** ``irc.poez.io``

        The JID of the IRC gateway to use. If empty, irc.poez.io will be
        used. Please try to run your own, though, it’s painless to setup.

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

    rooms
        **Default:** ``[empty]``

        The list of rooms to join on this server (e.g. ``#room1:#room2``).

.. note:: If no login_command or login_nick is set, the authentication phase
        won’t take place and you will join the rooms after a small delay.


Example configuration
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

    [irc]
    gateway = irc.poez.io

    [irc.freenode.net]
    nickname = mynick
    login_nick = nickserv
    login_command = identify mynick mypassword
    rooms = #testroom1:#testroom2

    [irc.geeknode.org]
    nickname = anothernick
    login_nick = C
    login_command = nick identify mypassword
    rooms = #testvroum



.. _official website: http://biboumi.louiz.org/
"""

from plugin import BasePlugin

class Plugin(BasePlugin):
    def init(self):

        def join(server):
            "Join rooms after a small delay"
            nick = self.config.get('nickname', '', server) or self.core.own_nick
            rooms = self.config.get('rooms', '', server).split(':')
            for room in rooms:
                room = '{}%{}@{}/{}'.format(room, server, gateway, nick)
                self.core.command_join(room)

        gateway = self.config.get('gateway', 'irc.poez.io')
        sections = self.config.sections()

        for section in (s for s in sections if s != 'irc'):
            server_suffix = '%{}@{}'.format(section, gateway)

            already_opened = False
            for tab in self.core.tabs:
                if tab.name.endswith(server_suffix):
                    already_opened = True

            login_command = self.config.get('login_command', '', section)
            login_nick = self.config.get('login_nick', '', section)
            nick = self.config.get('nickname', '', section) or self.core.own_nick

            if login_command and login_nick:
                dest = '{}{}/{}'.format(login_nick, server_suffix, nick)
                self.core.xmpp.send_message(mto=dest, mbody=login_command, mtype='chat')

            if not already_opened:
                delayed = self.api.create_delayed_event(5, join, section)
                self.api.add_timed_event(delayed)

