import pyotr
from sleekxmpp.xmlstream.stanzabase import JID

import logging
log = logging.getLogger(__name__)

from plugin import BasePlugin

import tabs
from tabs import ConversationTab

class Plugin(BasePlugin):
    def init(self):
        self.contacts = {}
        # a dict of {full-JID: OTR object}
        self.add_event_handler('conversation_say_after', self.on_conversation_say)
        self.add_event_handler('conversation_msg', self.on_conversation_msg)

        self.add_command('otr', self.command_otr, "Usage: /otr <start|end>\notr: Start or stop OTR for the current conversation", self.otr_completion)
        ConversationTab.add_information_element('otr', self.display_encryption_status)

    def cleanup(self):
        ConversationTab.remove_information_element('otr')
        self.del_tab_command(ConversationTab, 'otr')

    def otr_special(self, tab, typ):
        def helper(msg):
            tab.add_message('%s: %s' % (typ, msg.decode()))
        return helper

    def otr_on_state_change(self, tab):
        def helper(old, new):
            old = self.otr_state(old)
            new = self.otr_state(new)
            tab.add_message('OTR state has changed from %s to %s' % (old, new))
        return helper

    def get_otr(self, tab):
        if tab not in self.contacts:
            self.contacts[tab] = pyotr.OTR(on_error=self.otr_special(tab, 'Error'), on_warn=self.otr_special(tab, 'Warn'), on_state_change=self.otr_on_state_change(tab))
        return self.contacts[tab]

    def on_conversation_say(self, message, tab):
        """
        Feed the message through the OTR filter
        """
        to = message['to']
        if not message['body']:
            # there’s nothing to encrypt if this is a chatstate, for example
            return
        otr_state = self.get_otr(tab)
        # Not sure what to do with xhtml bodies, and I don't like them anyway ;)
        del message['xhtml_im']
        say = otr_state.transform_msg(message['body'].encode())
        if say is not None:
            message['body'] = say.decode()
        else:
            del message['body']

    def on_conversation_msg(self, message, tab):
        """
        Feed the message through the OTR filter
        """
        fro = message['from']
        if not message['body']:
            # there’s nothing to decrypt if this is a chatstate, for example
            return
        otr_state = self.get_otr(tab)
        # Not sure what to do with xhtml bodies, and I don't like them anyway ;)
        del message['xhtml_im']
        display, reply = otr_state.handle_msg(message['body'].encode())
        #self.core.information('D: {!r}, R: {!r}'.format(display, reply))
        if display is not None:
            message['body'] = display.decode()
        else:
            del message['body']
        if reply is not None:
            self.otr_say(tab, reply.decode())

    @staticmethod
    def otr_state(state):
        if state == pyotr.MSG_STATE_PLAINTEXT:
            return 'plaintext'
        elif state == pyotr.MSG_STATE_ENCRYPTED:
            return 'encrypted'
        elif state == pyotr.MSG_STATE_FINISHED:
            return 'finished'

    def display_encryption_status(self, jid):
        """
        Returns the status of encryption for the associated jid. This is to be used
        in the ConversationTab’s InfoWin.
        """
        tab = self.core.get_tab_by_name(jid, tabs.ConversationTab)
        if tab not in self.contacts:
            return ''
        state = self.otr_state(self.contacts[tab].state)
        return ' OTR: %s' % (state,)

    def otr_say(self, tab, line):
        msg = self.core.xmpp.make_message(tab.get_name())
        msg['type'] = 'chat'
        msg['body'] = line
        msg.send()

    def command_otr(self, args):
        """
        A command to start or end OTR encryption
        """
        args = args.split()
        if not args:
            return self.core.command_help("otr")
        if isinstance(self.core.current_tab(), ConversationTab):
            jid = JID(self.core.current_tab().get_name())
        command = args[0]
        if command == 'start':
            otr_state = self.get_otr(self.core.current_tab())
            self.otr_say(self.core.current_tab(), otr_state.start().decode())
        elif command == 'end':
            otr_state = self.get_otr(self.core.current_tab())
            msg = otr_state.end()
            if msg is not None:
                self.otr_say(self.core.current_tab(), msg.decode())
        elif command == 'fpr':
            otr_state = self.get_otr(self.core.current_tab())
            our = otr_state.our_fpr
            if our:
                our = hex(int.from_bytes(our, 'big'))[2:].ljust(40).upper()
            their = otr_state.their_fpr
            if their:
                their = hex(int.from_bytes(their, 'big'))[2:].ljust(40).upper()
            self.core.current_tab().add_message('Your: %s Their: %s' % (our, their))
        self.core.refresh_window()

    def otr_completion(self, the_input):
        return the_input.auto_completion(['start', 'end'], ' ')
