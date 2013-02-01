from plugin import BasePlugin
from roster import roster
from common import safeJID
import common
import tabs


class Plugin(BasePlugin):
    def init(self):
        self.core.xmpp.register_plugin('xep_0199')
        self.add_command('ping', self.command_ping, '/ping <jid>\nPing: Send a XMPP ping to jid (see XEP-0199).', self.completion_ping)
        self.add_tab_command(tabs.MucTab, 'ping', self.command_muc_ping, '/ping <jid or nick>\nPing: Send a XMPP ping to jid or nick (see XEP-0199)', self.completion_muc_ping)
        self.add_tab_command(tabs.PrivateTab, 'ping', self.command_private_ping, '/ping\nPing: Send a XMPP ping to the current interlocutor (see XEP-0199)')
        self.add_tab_command(tabs.ConversationTab, 'ping', self.command_private_ping, '/ping\nPing: Send a XMPP ping to the current interlocutor (see XEP-0199)')

    def command_ping(self, arg):
        if not arg:
            return
        jid = safeJID(arg)
        try:
            delay = self.core.xmpp.plugin['xep_0199'].ping(jid=jid)
        except:
            delay = None
        if delay is not None:
            self.core.information('%s responded to ping after %s s' % (jid, round(delay, 4)), 'Info')
        else:
            self.core.information('%s did not respond to ping' % jid, 'Info')

    def completion_muc_ping(self, the_input):
        users = [user.nick for user in self.core.current_tab().users]
        l = [contact.bare_jid for contact in roster.get_contacts()]
        users.extend(l)
        return the_input.auto_completion(users, '')

    def command_private_ping(self, arg):
        self.command_ping(self.core.current_tab().get_name())

    def command_muc_ping(self, arg):
        args = common.shell_split(arg)
        if not args:
            return
        user = self.core.current_tab().get_user_by_name(args[0])
        if user:
            jid = JID(self.core.current_tab().get_name())
            jid.resource = user.nick
        else:
            jid = JID(args[0])
        self.command_ping(jid.full)

    def completion_ping(self, the_input):
        l = [contact.bare_jid for contact in roster.get_contacts()]
        return the_input.auto_completion(l, '')

