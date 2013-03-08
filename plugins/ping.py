from plugin import BasePlugin
from roster import roster
from common import safeJID
import common
import tabs


class Plugin(BasePlugin):
    def init(self):
        self.core.xmpp.register_plugin('xep_0199')
        self.api.add_command('ping', self.command_ping,
                usage='<jid>',
                help='Send a XMPP ping to jid (see XEP-0199).',
                short='Send a ping',
                completion=self.completion_ping)
        self.api.add_tab_command(tabs.MucTab, 'ping', self.command_muc_ping,
                usage='<jid|nick>',
                help='Send a XMPP ping to jid or nick (see XEP-0199).',
                short='Send a ping.',
                completion=self.completion_muc_ping)
        for _class in (tabs.PrivateTab, tabs.ConversationTab):
            self.api.add_tab_command(_class, 'ping', self.command_private_ping,
                    usage='[jid]',
                    help='Send a XMPP ping to the current interlocutor or the given JID.',
                    short='Send a ping',
                    completion=self.completion_ping)

    def command_ping(self, arg):
        if not arg:
            return
        jid = safeJID(arg)
        try:
            delay = self.core.xmpp.plugin['xep_0199'].ping(jid=jid, timeout=5)
        except:
            delay = None
        if delay is not None:
            self.api.information('%s responded to ping after %s s' % (jid, round(delay, 4)), 'Info')
        else:
            self.api.information('%s did not respond to ping' % jid, 'Info')

    def completion_muc_ping(self, the_input):
        users = [user.nick for user in self.api.current_tab().users]
        l = [contact.bare_jid for contact in roster.get_contacts()]
        users.extend(l)
        return the_input.auto_completion(users, '', quotify=False)

    def command_private_ping(self, arg):
        if arg:
            return self.command_ping(arg)
        self.command_ping(self.api.current_tab().get_name())

    def command_muc_ping(self, arg):
        if not arg.strip():
            return
        user = self.api.current_tab().get_user_by_name(arg)
        if user:
            jid = safeJID(self.api.current_tab().get_name())
            jid.resource = user.nick
        else:
            jid = safeJID(arg)
        self.command_ping(jid.full)

    def completion_ping(self, the_input):
        l = [contact.bare_jid for contact in roster.get_contacts()]
        return the_input.auto_completion(l, '', quotify=False)

