from gpg import gnupg
from sleekxmpp.xmlstream.stanzabase import JID

from xml.etree import cElementTree as ET
import xml.sax.saxutils

import logging
log = logging.getLogger(__name__)

from plugin import BasePlugin

from tabs import ConversationTab

NS_SIGNED = "jabber:x:signed"
NS_ENCRYPTED = "jabber:x:encrypted"


SIGNED_ATTACHED_MESSAGE = """-----BEGIN PGP SIGNED MESSAGE-----
Hash: %(hash)s

%(clear)s
-----BEGIN PGP SIGNATURE-----
Version: GnuPG

%(data)s
-----END PGP SIGNATURE-----
"""


ENCRYPTED_MESSAGE = """-----BEGIN PGP MESSAGE-----
Version: GnuPG

%(data)s
-----END PGP MESSAGE-----"""


class Plugin(BasePlugin):
    def init(self):
        self.contacts = {}
        # a dict of {full-JID: 'signed'/'valid'/'invalid'/'disabled'}
        # Whenever we receive a signed presence from a JID, we add it to this
        # dict, this way we know if we can encrypt the messages we will send to
        # this JID.
        # If that resource sends a non-signed presence, then we remove it
        # from that dict and stop encrypting our messages.
        # 'disabled' means that the user do NOT want to encrypt its messages
        # even if the key is valid.
        self.gpg = gnupg.GPG()
        self.keyid = self.config.get('keyid', '') or None
        self.passphrase = self.config.get('passphrase', '') or None
        if not self.keyid:
            self.core.information('No GPG keyid provided in the configuration', 'Warning')

        self.add_event_handler('send_normal_presence', self.sign_presence)
        self.add_event_handler('normal_presence', self.on_normal_presence)
        self.add_event_handler('conversation_say_after', self.on_conversation_say)
        self.add_event_handler('conversation_msg', self.on_conversation_msg)

        self.add_command('gpg', self.command_gpg, "Usage: /gpg <force|disable>\nGpg: Force or disable gpg encryption with this fulljid.", self.gpg_completion)
        ConversationTab.add_information_element('gpg', self.display_encryption_status)

    def cleanup(self):
        self.send_unsigned_presence()
        ConversationTab.remove_information_element('gpg')
        self.del_tab_command(ConversationTab, 'gpg')

    def sign_presence(self, presence):
        """
        Sign every normal presence we send
        """
        signed_element = ET.Element('{%s}x' % (NS_SIGNED,))
        t = self.gpg.sign(presence['status'], keyid=self.keyid, passphrase=self.passphrase, detach=True)
        if not t:
            self.core.information('Could not sign presence. Disabling GPG module', 'Info')
            self.core.plugin_manager.unload('gpg')
            return
        text = xml.sax.saxutils.escape(str(t))
        signed_element.text = self.remove_gpg_headers(text)
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
            if bare in self.contacts.keys():
                del self.contacts[bare]
            return
        if self.config.has_section('keys') and bare in self.config.options('keys'):
            self.contacts[full] = 'invalid'
            for hash_ in ('SHA1', 'SHA256'):
                to_verify = SIGNED_ATTACHED_MESSAGE % {'clear': presence['status'],
                                                       'data': signed.text,
                                                       'hash': hash_}
                verify = self.gpg.verify(to_verify)
                if verify:
                    self.contacts[full] = 'valid'
                    break
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
        signed = to.full in self.contacts.keys()
        if signed:
            veryfied = self.contacts[to.full] in ('valid', 'forced')
        else:
            veryfied = False
        if veryfied:
            # remove the xhtm_im body if present, because that
            # cannot be encrypted.
            del message['xhtml_im']
            encrypted_element = ET.Element('{%s}x' % (NS_ENCRYPTED,))
            encrypted_element.text = self.remove_gpg_headers(xml.sax.saxutils.escape(str(self.gpg.encrypt(message['body'], self.config.get(to.bare, '', section='keys'), always_trust=True))))
            message.append(encrypted_element)
            message['body'] = 'This message has been encrypted.'

    def on_conversation_msg(self, message, tab):
        """
        Check if the message is encrypted, and decrypt it if we can.
        """
        encrypted = message.find('{%s}x' % (NS_ENCRYPTED,))
        fro = message['from']
        if encrypted is not None:
            if self.config.has_section('keys') and fro.bare in self.config.options('keys'):
                keyid = self.config.get(fro.bare, '', 'keys')
                decrypted = self.gpg.decrypt(ENCRYPTED_MESSAGE % {'data': str(encrypted.text)}, passphrase=self.passphrase)
                if not decrypted:
                    self.core.information('Could not decrypt message from %s' % (fro.full),)
                    return
                message['body'] = str(decrypted)

    def display_encryption_status(self, jid):
        """
        Returns the status of encryption for the associated jid. This is to be used
        in the ConversationTab’s InfoWin.
        """
        if jid.full not in self.contacts.keys():
            return ''
        status = self.contacts[jid.full]
        self.core.information('%s' % (status,))
        if status in ('valid', 'invalid'):
            return ' GPG Key: %s (%s)' % (status, 'encrypted' if status == 'valid' else 'NOT encrypted',)
        else:
            return ' GPG:  Encryption %s' % (status,)

    def command_gpg(self, args):
        """
        A command to force or disable the encryption, or to assign a keyid to a JID
        """
        args = args.split()
        if not args:
            return self.core.command_help("gpg")
        if len(args) >= 2:
            jid = JID(args[1])
        else:
            if isinstance(self.core.current_tab(), ConversationTab):
                jid = JID(self.core.current_tab().get_name())
        command = args[0]
        if command == 'force':
            # we can force encryption only with contact having an associated
            # key, otherwise we cannot encrypt at all
            if self.config.has_section('keys') and jid.bare in self.config.options('keys'):
                self.contacts[JID(jid).full] = 'forced'
            else:
                self.core.information('Cannot force encryption: no key associated with %s' % (jid.bare), 'Info')
        elif command == 'disable':
            self.contacts[JID(jid).full] = 'disabled'
        self.core.refresh_window()

    def gpg_completion(self, args):
        pass

    def remove_gpg_headers(self, text):
        lines = text.splitlines()
        while lines[0].strip() != '':
            lines.pop(0)
        while lines[0].strip() == '':
            lines.pop(0)
        res = []
        for line in lines:
            if not line.startswith('---'):
                res.append(line)
        return '\n'.join(res)
