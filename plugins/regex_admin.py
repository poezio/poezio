"""
This plugins adds a :term:`/rkick` and a :term:`/rban` command,
in order to kick/ban according to a regex on a nick.

Commands
--------

Those commands take a regular expression (as defined in the
`re module documentation`_) as a parameter.

.. glossary::
    :sorted:

    /rkick
        **Usage:** ``/rkick <regex>``

        Kick a participant using a regex.


    /rban
        **Usage:** ``/rban <regex>``

        Ban a participant using a regex.

.. _re module documentation: http://docs.python.org/3/library/re.html
"""


from poezio.plugin import BasePlugin
from poezio.tabs import MucTab

import re

class Plugin(BasePlugin):
    def init(self):
        self.api.add_tab_command(MucTab, 'rkick',
                self.command_rkick,
                usage='<regex>',
                help='Kick occupants of a room according to a regex',
                short='Regex Kick')

        self.api.add_tab_command(MucTab, 'rban',
                self.command_rban,
                usage='<regex>',
                help='Ban occupants of a room according to a regex',
                short='Regex Ban')

    def return_users(self, users, regex):
        try:
            reg = re.compile(regex)
        except:
            return []

        ret = []
        for user in users:
            if reg.match(user.nick):
                ret.append(user)

        return ret

    def command_rban(self, regex):
        tab = self.api.current_tab()
        users = self.return_users(tab.users, regex)
        for user in users:
            tab.command_ban(user.nick)

    def command_rkick(self, regex):
        tab = self.api.current_tab()
        users = self.return_users(tab.users, regex)
        for user in users:
            tab.command_kick(user.nick)

