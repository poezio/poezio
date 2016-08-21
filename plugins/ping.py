"""
This plugin allows you to ping an entity.

Command
-------

.. glossary::

    /ping
        **Usage (globally):** ``/ping <jid>``

        **Usage (in a MUC tab):** ``/ping <jid or nick>``

        **Usage (in a conversation tab):** ``/ping [jid]``

        Globally, you can do ``/ping jid@example.com`` to get a ping.

        In a MUC, you can either do it to a JID or a nick (``/ping nick`` or ``/ping
        jid@example.com``).

        In a private or a direct conversation, you can do ``/ping`` to ping
        the current interlocutor.
"""

from poezio.decorators import command_args_parser
from poezio.plugin import BasePlugin
from poezio.roster import roster
from poezio.common import safeJID
from poezio.contact import Contact, Resource
from poezio.core.structs import Completion
from poezio import tabs
import time


class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('ping', self.command_ping,
                usage='<jid>',
                help='Send an XMPP ping to jid (see XEP-0199).',
                short='Send a ping',
                completion=self.completion_ping)
        self.api.add_tab_command(tabs.MucTab, 'ping', self.command_muc_ping,
                usage='<jid|nick>',
                help='Send an XMPP ping to jid or nick (see XEP-0199).',
                short='Send a ping.',
                completion=self.completion_muc_ping)
        self.api.add_tab_command(tabs.RosterInfoTab, 'ping', self.command_roster_ping,
                usage='<jid>',
                help='Send an XMPP ping to jid (see XEP-0199).',
                short='Send a ping.',
                completion=self.completion_ping)
        for _class in (tabs.PrivateTab, tabs.ConversationTab):
            self.api.add_tab_command(_class, 'ping', self.command_private_ping,
                    usage='[jid]',
                    help='Send an XMPP ping to the current interlocutor or the given JID.',
                    short='Send a ping',
                    completion=self.completion_ping)

    @command_args_parser.raw
    def command_ping(self, arg):
        if not arg:
            return self.core.command.help('ping')
        jid = safeJID(arg)
        start = time.time()
        def callback(iq):
            delay = time.time() - start
            if iq['type'] == 'error' and iq['error']['condition'] in ('remote-server-timeout', 'remote-server-not-found'):
                self.api.information('%s did not respond to ping' % jid, 'Info')
            else:
                self.api.information('%s responded to ping after %s s' % (jid, round(delay, 4)), 'Info')

        self.core.xmpp.plugin['xep_0199'].send_ping(jid=jid, callback=callback)

    def completion_muc_ping(self, the_input):
        users = [user.nick for user in self.api.current_tab().users]
        l = self.resources()
        users.extend(l)
        return Completion(the_input.auto_completion, users, '', quotify=False)

    @command_args_parser.raw
    def command_private_ping(self, arg):
        if arg:
            return self.command_ping(arg)
        self.command_ping(self.api.current_tab().name)

    @command_args_parser.raw
    def command_muc_ping(self, arg):
        if not arg:
            return
        user = self.api.current_tab().get_user_by_name(arg)
        if user:
            jid = safeJID(self.api.current_tab().name)
            jid.resource = user.nick
        else:
            jid = safeJID(arg)
        self.command_ping(jid.full)

    @command_args_parser.raw
    def command_roster_ping(self, arg):
        if arg:
            self.command_ping(arg)
        else:
            current = self.api.current_tab().selected_row
            if isinstance(current, Resource):
                self.command_ping(current.jid)
            elif isinstance(current, Contact):
                res = current.get_highest_priority_resource()
                if res is not None:
                    self.command_ping(res.jid)

    def resources(self):
        l = []
        for contact in roster.get_contacts():
            for resource in contact.resources:
                l.append(resource.jid)
        return l

    def completion_ping(self, the_input):
        return Completion(the_input.auto_completion, self.resources(), '', quotify=False)

