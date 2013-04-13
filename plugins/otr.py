"""

.. warning:: THE OTR LIB IS IN AN EXPERIMENTAL STATE AND SHOULD NOT BE
            CONSIDERED AS ENTIRELY RELIABLE

This plugin implements `Off The Record messaging`_.

This is a plugin used to encrypt one-to-one conversation using the OTR
encryption method. You can use it if you want good privacy, deniability,
authentication, and strong secrecy. Without this
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

To use the OTR plugin, you must first install libopenotr.

If you use Archlinux, there is a `libopenotr-git`_ package on the AUR.

If not, then you will have to install it by hand.

First, clone the repo and go inside the created directory:

.. code-block:: bash

    git clone https://github.com/teisenbe/libopenotr.git
    cd libopenotr

Then run autogen.sh and configure

.. code-block:: bash

    sh autogen.sh
    ./configure --enable-gaping-security-hole

(as of now, you *should* have been warned enough that the library is not finished)

Then compile & install the lib:

.. code-block:: bash

    make
    sudo make install

Finally, install the python module:

.. code-block:: bash

    python3 setup.py build
    sudo python3 setup.py install

Usage
-----

To use OTR, make sure the plugin is loaded (if not, then do ``/load otr``).

Once you are in a private conversation, you have to do a:


.. code-block:: none

    /otr start

The status of the OTR encryption should appear in the bar between the chat and
the input as ``OTR: encrypted``.


Once you’re done, end the OTR session with

.. code-block:: none

    /otr end

Known problems
--------------

Empty messages send when changing status.

.. _Off The Record messaging: http://wiki.xmpp.org/web/OTR
.. _libopenotr-git:  https://aur.archlinux.org/packages.php?ID=57957

"""

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
        self.api.add_event_handler('conversation_say_after', self.on_conversation_say)
        self.api.add_event_handler('conversation_msg', self.on_conversation_msg)

        self.api.add_tab_command(ConversationTab, 'otr', self.command_otr,
                usage='<start|end|fpr>',
                help='Start or stop OTR for the current conversation.',
                short='Manage OTR status',
                completion=self.otr_completion)
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
            return self.api.run_command("/help otr")
        if isinstance(self.api.current_tab(), ConversationTab):
            jid = JID(self.api.current_tab().get_name())
        command = args[0]
        if command == 'start':
            otr_state = self.get_otr(self.api.current_tab())
            self.otr_say(self.api.current_tab(), otr_state.start().decode())
        elif command == 'end':
            otr_state = self.get_otr(self.api.current_tab())
            msg = otr_state.end()
            if msg is not None:
                self.otr_say(self.api.current_tab(), msg.decode())
        elif command == 'fpr':
            otr_state = self.get_otr(self.api.current_tab())
            our = otr_state.our_fpr
            if our:
                our = hex(int.from_bytes(our, 'big'))[2:].ljust(40).upper()
            their = otr_state.their_fpr
            if their:
                their = hex(int.from_bytes(their, 'big'))[2:].ljust(40).upper()
            self.api.current_tab().add_message('Your: %s Their: %s' % (our, their))
        self.core.refresh_window()

    def otr_completion(self, the_input):
        return the_input.auto_completion(['start', 'fpr', 'end'], '', quotify=False)
