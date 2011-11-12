from gpg import gnupg
from xml.etree import cElementTree as ET
import xml.sax.saxutils

from plugin import BasePlugin

import logging
log = logging.getLogger(__name__)

NS_SIGNED = "jabber:x:signed"
NS_ENCRYPTED = "jabber:x:encrypted"

class Plugin(BasePlugin):
    def init(self):
        self.contacts = {}
        # a dict of {full-JID: 'signed'/'valid'/'invalid'}
        # Whenever we receive a signed presence from a JID, we add it to this
        # dict, this way we know if we can encrypt the messages we will send to
        # this JID.
        # If that resource sends a non-signed presence, then we remove it
        # from that dict and stop encrypting our messages.
        self.gpg = gnupg.GPG()
        self.keyid = self.config.get('keyid', '') or None
        self.passphrase = self.config.get('passphrase', '') or None
        if not self.keyid:
            self.core.information('No GPG keyid provided in the configuration', 'Warning')

        self.add_event_handler('send_normal_presence', self.sign_presence)
        self.add_event_handler('normal_presence', self.on_normal_presence)
        self.add_event_handler('conversation_say_after', self.on_conversation_say)
        self.add_event_handler('conversation_msg', self.on_conversation_msg)

    def cleanup(self):
        self.send_unsigned_presence()

    def sign_presence(self, presence):
        """
        Sign every normal presence we send
        """
        signed_element = ET.Element('{%s}x' % (NS_SIGNED,))
        t = self.gpg.sign(presence['status'], keyid=self.keyid, passphrase=self.passphrase)
        if not t:
            self.core.information('Could not sign presence. Disabling GPG module', 'Info')
            self.core.plugin_manager.unload('gpg')
            return
        signed_element.text = xml.sax.saxutils.escape(str(t))
        presence.append(signed_element)

    def send_unsigned_presence(self):
        """
        Send our current presence, to everyone, but unsigned, to indicate
        that we cannot/do not want to encrypt/decrypt messages.
        """
        current_presence = self.core.get_status()
        self.core.command_status('%s %s' % (current_presence.show or 'available', current_presence.message,))

    def on_normal_presence(self, presence, resource):
        """
        Check if it’s signed, if it is and we can verify the signature,
        add 'valid' or 'invalid' into the dict. If it cannot be verified, just add
        'signed'. Otherwise, do nothing.
        """
        signed = presence.find('{%s}x' % (NS_SIGNED,))
        bare = presence['from'].bare
        full = presence['from'].full
        if signed is None:
            log.debug('Not signed')
            if bare in self.contacts.keys():
                del self.contacts[bare]
            return
        if self.config.has_section('keys') and bare in self.config.options('keys'):
            verify = self.gpg.verify(signed.text)
            if verify:
                self.contacts[full] = 'valid'
            else:
                self.contacts[full] = 'invalid'
        else:
            self.contacts[full] = 'signed'

    def on_conversation_say(self, message, tab):
        """
        Check if the contact has a signed AND veryfied signature.
        If yes, encrypt the message with her key.
        """
        to = message['to']
        if not message['body']:
            # there’s nothing to encrypt if this is a chatstate, for example
            return
        log.debug('\n\n\n on_conversation_say: from: (%s). Contacts: %s' %(to, self.contacts,))
        signed = to.full in self.contacts.keys()
        if signed:
            veryfied = self.contacts[to.full] == 'valid'
        else:
            veryfied = False
        if veryfied:
            # remove the xhtm_im body if present, because that
            # cannot be encrypted.
            del message['xhtml_im']
            encrypted_element = ET.Element('{%s}x' % (NS_ENCRYPTED,))
            encrypted_element.text = xml.sax.saxutils.escape(str(self.gpg.encrypt(message['body'], self.config.get(to.bare, '', section='keys'))))
            message.append(encrypted_element)
            message['body'] = 'This message has been encrypted.'

    def on_conversation_msg(self, message, tab):
        """
        Check if the message is encrypted, and decrypt it if we can.
        """
        encrypted = message.find('{%s}x' % (NS_ENCRYPTED,))
        fro = message['from']
        log.debug('\n\n\n--------- for message %s. ENCRYPTED: %s' % (message, encrypted,))
        if encrypted is not None:
            if self.config.has_section('keys') and fro.bare in self.config.options('keys'):
                keyid = self.config.get(fro.bare, '', 'keys')
                decrypted = self.gpg.decrypt(encrypted.text, passphrase=self.passphrase)
                if not decrypted:
                    self.core.information('Could not decrypt message from %s' % (fro.full),)
                    return
                message['body'] = str(decrypted)
