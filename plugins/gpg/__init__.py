"""
This plugin implements the `XEP-0027`_ “Current Jabber OpenPGP Usage”.

This is a plugin used to encrypt one-to-one conversation using the PGP
encryption method. You can use it if you want really good privacy. Without this
encryption, your messages are encrypted **at least** from your client (poezio) to
your server. The message is decrypted by your server and you cannot control the
encryption method of your messages from your server to your contact’s server
(unless you are your own server’s administrator), nor from your contact’s
server to your contact’s client.

This plugin does end-to-end encryption. This means that **only** your contact can
decrypt your messages, and it is fully encrypted during **all** its travel
through the internet.

Note that if you are having an encrypted conversation with a contact, you can
**not** send XHTML-IM messages to him. They will be removed and be replaced by
plain text messages.

Installation and configuration
------------------------------

You should autoload this plugin, as it will send your signed presence directly
on login, making it easier for your contact’s clients to know that you are
supporting GPG encryption. To do that, use the :term:`plugins_autoload` configuration
option.

You need to create a plugin configuration file. Create a file named :file:`gpg.cfg`
into your plugins configuration directory (:file:`~/.config/poezio/plugins` by
default), and fill it like this:

.. code-block:: ini

    [gpg]
    keyid = 091F9C78
    passphrase = your OPTIONAL passphrase

    [keys]
    example@jabber.org = E3CFCDE2
    juliet@xmpp.org = EF27ABCD

The ``gpg`` section is about your key. You need to specify the keyid, for the
key you want to use. You can as well provide a passphrase. If you don’t, you
should use a gpg agent or something like that that will ask your passphrase
whenever you need it.

The ``keys`` section contains your contact’s id keys. For each contact you want
to have encrypted conversations with, add her/his JID associated with the keyid
of his/her key. You can autogenerate a keys section based on the ones already
in your trust chain by running the script ``poezio_gpg_export`` provided with
poezio (in the :file:`scripts/` directory). Please double-check the section
created this way.

And that’s it, now you need to talk directly to the **full** jid of your
contacts. Poezio doesn’t let you encrypt messages whom recipients is a bare
JID.

Additionnal information on GnuPG
--------------------------------

Create a key
~~~~~~~~~~~~

To create a personal key, use

.. code-block:: bash

    gpg --gen-key

and follow the instructions.

Keyid
~~~~~
The keyid (required in the gpg.cfg configuration file) is a 8 character-long
key. You can get the ones you created or imported by using the command

.. code-block:: bash

    gpg --list-keys

You will get something like

.. code-block:: none

    pub   4096R/01234567 2011-11-11
    uid                  Your Name Here (comment) <email@example.org>
    sub   4096R/AAFFBBCC 2011-11-11

    pub   2048R/12345678 2011-11-12 [expire: 2011-11-22]
    uid                  A contact’s name (comment) <fake@fake.fr>
    sub   2048R/FFBBAACC 2011-11-12 [expire: 2011-11-22]

In this example, the keyids are ``01234567`` and  ``12345678``.

Share your key
~~~~~~~~~~~~~~
Use:

.. code-block:: bash

    gpg --send-keys --keyserver pgp.mit.edu <keyid>

to upload you public key on a public server.

.. _XEP-0027: http://xmpp.org/extensions/xep-0027.html

"""
from gpg import gnupg
from slixmpp.xmlstream.stanzabase import JID

from xml.etree import cElementTree as ET
import xml.sax.saxutils

import logging
log = logging.getLogger(__name__)

from poezio.plugin import BasePlugin

from poezio.tabs import ConversationTab
from poezio.theming import get_theme

NS_SIGNED = "jabber:x:signed"
NS_ENCRYPTED = "jabber:x:encrypted"


SIGNED_ATTACHED_MESSAGE = """-----BEGIN PGP SIGNED MESSAGE-----
Hash: %(hash)s

%(clear)s
-----BEGIN PGP SIGNATURE-----

%(data)s
-----END PGP SIGNATURE-----
"""


ENCRYPTED_MESSAGE = """-----BEGIN PGP MESSAGE-----

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
            self.api.information('No GPG keyid provided in the configuration', 'Warning')

        self.api.add_event_handler('send_normal_presence', self.sign_presence)
        self.api.add_slix_event_handler('presence', self.on_normal_presence)
        self.api.add_event_handler('conversation_say_after', self.on_conversation_say)
        self.api.add_event_handler('conversation_msg', self.on_conversation_msg)

        self.api.add_tab_command(ConversationTab, 'gpg', self.command_gpg,
                usage='<force|disable|setkey> [jid] [keyid]',
                help='Force or disable gpg encryption with the fulljid of the current conversation. The setkey argument lets you associate a keyid with the given bare JID.',
                short='Manage the GPG status',
                completion=self.gpg_completion)
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
        self.core.command.status('%s %s' % (current_presence.show or 'available', current_presence.message or '',))

    def on_normal_presence(self, presence):
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
            for hash_ in ('SHA1', 'SHA256', 'SHA512'):
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
        Check if the contact has a signed AND verified signature.
        If yes, encrypt the message with her key.
        """
        to = message['to']
        if not message['body']:
            # there’s nothing to encrypt if this is a chatstate, for example
            return
        signed = to.full in self.contacts.keys()
        if signed:
            verified = self.contacts[to.full] in ('valid', 'forced')
        else:
            verified = False
        if verified:
            # remove the xhtm_im body if present, because that
            # cannot be encrypted.
            body = message['body']
            del message['html']
            encrypted_element = ET.Element('{%s}x' % (NS_ENCRYPTED,))
            text = self.gpg.encrypt(message['body'], self.config.get(to.bare, '', section='keys'), always_trust=True)
            if not text:
                self.core.information('Could not encrypt message to %s' % (to.full),)
                # If we could not encrypt the message, don't send anything
                message['body'] = ''
                return
            encrypted_element.text = self.remove_gpg_headers(xml.sax.saxutils.escape(str(text)))
            message.append(encrypted_element)
            message['body'] = 'This message has been encrypted using the GPG key with id: %s' % self.keyid
            message.send()
            del message['body']
            tab.add_message(body, nickname=self.core.own_nick,
                            nick_color=get_theme().COLOR_OWN_NICK,
                            identifier=message['id'],
                            jid=self.core.xmpp.boundjid,
                            typ=0)

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
        if status in ('valid', 'invalid', 'signed'):
            return ' GPG Key: %s (%s)' % (status, 'encrypted' if status == 'valid' else 'NOT encrypted',)
        else:
            return ' GPG: Encryption %s' % (status,)

    def command_gpg(self, args):
        """
        A command to force or disable the encryption, or to assign a keyid to a JID
        """
        args = args.split()
        if not args:
            return self.core.command.help("gpg")
        if len(args) >= 2:
            jid = JID(args[1])
        else:
            if isinstance(self.core.current_tab(), ConversationTab):
                jid = JID(self.core.current_tab().name)
            else:
                return
        command = args[0]
        if command == 'force' or command == 'enable':
            # we can force encryption only with contact having an associated
            # key, otherwise we cannot encrypt at all
            if self.config.has_section('keys') and jid.bare in self.config.options('keys'):
                self.contacts[JID(jid).full] = 'forced'
            else:
                self.core.information('Cannot force encryption: no key associated with %s' % (jid.bare), 'Info')
        elif command == 'disable':
            self.contacts[JID(jid).full] = 'disabled'
        elif command == 'setkey':
            if len(args) != 3:
                return self.core.command.help("gpg")
            if not self.config.has_section('keys'):
                self.config.add_section('keys')
            self.config.set(jid.bare, args[2], 'keys')
            self.config.write()
        self.core.refresh_window()

    def gpg_completion(self, the_input):
        if the_input.get_argument_position() == 1:
            return the_input.new_completion(['force', 'disable', 'setkey'], 1, quotify=False)

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
