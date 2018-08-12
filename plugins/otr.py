"""

This plugin implements `Off The Record messaging`_.

This is a plugin used to encrypt a one-to-one conversation using the OTR
encryption method. You can use it if you want good privacy, deniability,
authentication, and strong secrecy. Without this encryption, your messages
are encrypted **at least** from your client (poezio) to your server. The
message is decrypted by your server and you cannot control the encryption
method of your messages from your server to your contact’s server (unless
you are your own server’s administrator), nor from your contact’s server
to your contact’s client.

This plugin does end-to-end encryption. This means that **only** your contact can
decrypt your messages, and it is fully encrypted during **all** its travel
through the internet.

Note that if you are having an encrypted conversation with a contact, you can
**not** send XHTML-IM messages to them (or correct messages, or anything more than
raw text). All formatting will be removed and be replaced by plain text messages.

This is a limitation of the OTR protocol, and it will never be fixed. Some clients
like Pidgin-OTR try do do magic stuff with html unescaping inside the OTR body, and
it is not pretty.

Installation
------------

To use the OTR plugin, you must first install pure-python-otr and pycrypto
(for python3).

You have to install it from the git because a few issues were
found with the python3 compatibility while writing this plugin,
and the fixes did not make it into a stable release yet.

Install the python module:

.. code-block:: bash

    git clone https://github.com/afflux/pure-python-otr.git
    cd pure-python-otr
    python3 setup.py install --user

You can also use pip in a virtualenv (built-in as pyvenv_ with python since 3.3)
with the requirements.txt at the root of the poezio directory.

Important details
-----------------

The OTR session is considered for a full JID (e.g. toto@example/**client1**),
but the trust is set with a bare JID (e.g. toto@example). This is important
in the case of Private Chats (in a chatroom), since you cannot always get the
real JID of your contact (or check if the same nick is used by different people).

.. note::

    This also means that you cannot have an OTR session in the "common"
    conversation tab, which is not locked to a specific JID. After activating
    the plugin, you need to open a session with a full JID to be able to use
    OTR.

Usage
-----

Command added to Static Conversation Tabs (opened with ``/message foo@bar/baz`` or
by expanding a contact in the roster) and Private Tabs:

.. glossary::

    /otr
        **Usage:** ``/otr [start|refresh|end|fpr|ourfpr|trust|untrust]``

        This command is used to manage an OTR private session.

        - The ``start`` (or ``refresh``) command starts or refreshs a private OTR session
        - The ``end`` command ends a private OTR session
        - The ``fpr`` command gives you the fingerprint of the key of the remote entity
        - The ``ourfpr`` command gives you the fingerprint of your own key
        - The ``trust`` command marks the current remote key as trusted for the current remote JID
        - The ``untrust`` command removes that trust
        - Finally, the ``drop`` command is used if you want to delete your private key (not recoverable).

        .. warning::

            With ``drop``, the private key is only removed from the filesystem,
            *NOT* with multiple rewrites in a secure manner, you should do that
            yourself if you want to be sure.

    /otrsmp
        **Usage:** ``/otrsmp <ask|answer|abort> [question] [secret]``

        Verify the identify of your contact by using a pre-defined secret.

        - The ``abort`` command aborts an ongoing verification
        - The ``ask`` command start a verification, with a question or not
        - The ``answer`` command sends back the answer and finishes the verification

Managing trust
--------------

An OTR conversation can be started with a simple ``/otr start`` and the
conversation will be encrypted. However it is very often useful to check
that your are talking to the right person.

To this end, two actions are available, and a message explaining both
will be prompted each time an **untrusted** conversation is started:

- Checking the knowledge of a shared secret through the use of :term:`/otrsmp`
- Exchanging fingerprints (``/otr fpr`` and ``/otr ourfpr``) out of band (in a secure channel) to check that both match,
  then use ``/otr trust`` to add then to the list of trusted fingerprints for this JID.

Files
-----

This plugin creates trust files complatible with libotr and the files produced by gajim.


The files are located in :file:`$XDG_DATA_HOME/poezio/otr/` by default (so
:file:`~/.local/share/poezio/otr` in most cases).

Two files are created:

- An account_jid.key3 (:file:`example@example.com.key3`) file, which contains the private key
- An account_jid.fpr (:file:`example@example.com.fpr`) file, which contains the list of trusted
  (or untrusted) JIDs and keys.

Configuration
-------------

.. glossary::
    :sorted:

    decode_xhtml
        **Default:** ``true``

        Decode embedded XHTML.

    decode_entities
        **Default:** ``true``

        Decode XML and HTML entities (like ``&amp;``) even when the
        document isn't valid (if it is valid, it will be decoded even
        without this option).

    decode_newlines
        **Default:** ``true``

        Decode ``<br/>`` and ``<br>`` tags even when the document
        isn't valid (if it is valid, it will be decoded even
        without this option for ``<br/>``, and ``<br>`` will make
        the document invalid anyway).

    keys_dir
        **Default:** ``$XDG_DATA_HOME/poezio/otr``

        The directory in which you want keys and fpr to be stored.

    require_encryption
        **Default:** ``false``

        If ``true``, prevents you from sending unencrypted messages, and tries
        to establish OTR sessions when receiving unencrypted messages.

    timeout
        **Default:** ``3``

        The number of seconds poezio will wait until notifying you
        that the OTR session was not established. A negative or null
        value will disable this notification.

    log
        **Default:** ``false``

        Log conversations (OTR start/end marker, and messages).

The :term:`require_encryption`, :term:`decode_xhtml`, :term:`decode_entities`
and :term:`log` configuration parameters are tab-specific.

.. _Off The Record messaging: http://wiki.xmpp.org/web/OTR
.. _pyvenv: https://docs.python.org/3/using/scripts.html#pyvenv-creating-virtual-environments

"""

from gettext import gettext as _
import logging

log = logging.getLogger(__name__)
import os
import html
import curses
from pathlib import Path

import potr
from potr.context import NotEncryptedError, UnencryptedMessage, ErrorReceived, NotOTRMessage,\
        STATE_ENCRYPTED, STATE_PLAINTEXT, STATE_FINISHED, Context, Account, crypt

from poezio import common
from poezio import xdg
from poezio import xhtml
from poezio.common import safeJID
from poezio.config import config
from poezio.plugin import BasePlugin
from poezio.roster import roster
from poezio.tabs import StaticConversationTab, PrivateTab
from poezio.theming import get_theme, dump_tuple
from poezio.decorators import command_args_parser
from poezio.core.structs import Completion

POLICY_FLAGS = {
    'ALLOW_V1':False,
    'ALLOW_V2':True,
    'REQUIRE_ENCRYPTION': False,
    'SEND_TAG': True,
    'WHITESPACE_START_AKE': True,
    'ERROR_START_AKE': True
}

log = logging.getLogger(__name__)


OTR_TUTORIAL = _(
"""%(info)sThis contact has not yet been verified.
You have several methods of authentication available:

1) Verify each other's fingerprints using a secure (and different) channel:
Your fingerprint: %(normal)s%(our_fpr)s%(info)s
%(jid_c)s%(jid)s%(info)s's fingerprint: %(normal)s%(remote_fpr)s%(info)s
Then use the command: /otr trust

2) SMP pre-shared secret you both know:
/otrsmp ask <secret>

3) SMP pre-shared secret you both know with a question:
/otrsmp ask <question> <secret>
""")

OTR_NOT_ENABLED = _('%(jid_c)s%(jid)s%(info)s did not enable '
                    'OTR after %(secs)s seconds.')

MESSAGE_NOT_SENT = _('%(info)sYour message to %(jid_c)s%(jid)s%(info)s was'
                     ' not sent because your configuration requires an '
                     'encrypted session.\nWait until it is established or '
                     'change your configuration.')

INCOMPATIBLE_TAB = _('%(info)sYour message to %(jid_c)s%(jid)s%(info)s was'
                     ' not sent because your configuration requires an '
                     'encrypted session and the current tab is a bare-jid '
                     'one, with which you cannot open or use an OTR session.'
                     ' You need to open a fulljid tab with /message if you '
                     'want to use OTR.%(help)s')

TAB_HELP_RESOURCE = _('\nChoose the relevant one among the following:%s')

OTR_REQUEST = _('%(info)sOTR request to %(jid_c)s%(jid)s%(info)s sent.')

OTR_OWN_FPR = _('%(info)sYour OTR key fingerprint is '
                '%(normal)s%(fpr)s%(info)s.')

OTR_REMOTE_FPR = _('%(info)sThe key fingerprint for %(jid_c)s'
                   '%(jid)s%(info)s is %(normal)s%(fpr)s%(info)s.')

OTR_NO_FPR = _('%(jid_c)s%(jid)s%(info)s has no'
               ' key currently in use.')

OTR_START_TRUSTED = _('%(info)sStarted a \x19btrusted\x19o%(info)s '
                      'OTR conversation with %(jid_c)s%(jid)s')

OTR_REFRESH_TRUSTED = _('%(info)sRefreshed \x19btrusted\x19o%(info)s'
                        ' OTR conversation with %(jid_c)s%(jid)s')

OTR_START_UNTRUSTED = _('%(info)sStarted an \x19buntrusted\x19o%(info)s'
                        ' OTR conversation with %(jid_c)s%(jid)s')

OTR_REFRESH_UNTRUSTED = _('%(info)sRefreshed \x19buntrusted\x19o%(info)s'
                          ' OTR conversation with %(jid_c)s%(jid)s')

OTR_END = _('%(info)sEnded OTR conversation with %(jid_c)s%(jid)s')

SMP_REQUESTED = _('%(jid_c)s%(jid)s%(info)s has requested SMP verification'
                  '%(q)s%(info)s.\nAnswer with: /otrsmp answer <secret>')

SMP_INITIATED = _('%(info)sInitiated SMP request with '
                  '%(jid_c)s%(jid)s%(info)s.')

SMP_PROGRESS = _('%(info)sSMP progressing.')

SMP_RECIPROCATE = _('%(info)sYou may want to authenticate your peer by asking'
                    ' your own question: /otrsmp ask [question] <secret>')

SMP_SUCCESS = _('%(info)sSMP Verification \x19bsucceeded\x19o%(info)s.')

SMP_FAIL = _('%(info)sSMP Verification \x19bfailed\x19o%(info)s.')

SMP_ABORTED_PEER = _('%(info)sSMP aborted by peer.')

SMP_ABORTED = _('%(info)sSMP aborted.')

MESSAGE_UNENCRYPTED = _('%(info)sThe following message from %(jid_c)s%(jid)s'
                        '%(info)s was \x19bnot\x19o%(info)s encrypted:\x19o\n'
                        '%(msg)s')

MESSAGE_UNREADABLE = _('%(info)sAn encrypted message from %(jid_c)s%(jid)s'
                       '%(info)s was received but is unreadable, as you are'
                       ' not currently communicating privately.')

MESSAGE_INVALID = _('%(info)sThe message from %(jid_c)s%(jid)s%(info)s'
                    ' could not be decrypted.')

OTR_ERROR = _('%(info)sReceived the following error from '
              '%(jid_c)s%(jid)s%(info)s:\x19o %(err)s')

POTR_ERROR = _('%(info)sAn unspecified error in the OTR plugin occured:\n'
               '%(exc)s')

TRUST_ADDED = _('%(info)sYou added %(jid_c)s%(bare_jid)s%(info)s with key '
                '\x19o%(key)s%(info)s to your trusted list.')


TRUST_REMOVED = _('%(info)sYou removed %(jid_c)s%(bare_jid)s%(info)s with '
                  'key \x19o%(key)s%(info)s from your trusted list.')

KEY_DROPPED = _('%(info)sPrivate key dropped.')


def hl(tab):
    """
    Make a tab beep and change its status.
    """
    if tab.state != 'current':
        tab.state = 'private'

    conv_jid = safeJID(tab.name)
    if 'private' in config.get('beep_on', 'highlight private').split():
        if not config.get_by_tabname('disable_beep', conv_jid.bare, default=False):
            curses.beep()

class PoezioContext(Context):
    """
    OTR context, specific to a conversation with a contact

    Overrides methods from potr.context.Context
    """
    def __init__(self, account, peer, xmpp, core):
        super(PoezioContext, self).__init__(account, peer)
        self.xmpp = xmpp
        self.core = core
        self.flags = {}
        self.trustName = safeJID(peer).bare
        self.in_smp = False
        self.smp_own = False
        self.log = 0

    def getPolicy(self, key):
        if key in self.flags:
            return self.flags[key]
        else:
            return False

    def reset_smp(self):
        self.in_smp = False
        self.smp_own = False

    def inject(self, msg, appdata=None):
        message = self.xmpp.make_message(mto=self.peer,
                                         mbody=msg.decode('ascii'),
                                         mtype='chat')
        message['eme']['namespace'] = 'urn:xmpp:otr:0'
        message.enable('carbon_private')
        message.enable('no-copy')
        message.enable('no-permanent-store')
        message.send()

    def setState(self, newstate):
        format_dict = {
            'jid_c': '\x19%s}' % dump_tuple(get_theme().COLOR_MUC_JID),
            'info': '\x19%s}' % dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
            'normal': '\x19%s}' % dump_tuple(get_theme().COLOR_NORMAL_TEXT),
            'jid': self.peer,
            'bare_jid': safeJID(self.peer).bare
        }

        tab = self.core.tabs.by_name(self.peer)
        if not tab:
            tab = None
        if self.state == STATE_ENCRYPTED:
            if newstate == STATE_ENCRYPTED and tab:
                log.debug('OTR conversation with %s refreshed', self.peer)
                if self.getCurrentTrust():
                    msg = OTR_REFRESH_TRUSTED % format_dict
                    tab.add_message(msg, typ=self.log)
                else:
                    msg = OTR_REFRESH_UNTRUSTED % format_dict
                    tab.add_message(msg, typ=self.log)
                hl(tab)
            elif newstate == STATE_FINISHED or newstate == STATE_PLAINTEXT:
                log.debug('OTR conversation with %s finished', self.peer)
                if tab:
                    tab.add_message(OTR_END % format_dict, typ=self.log)
                    hl(tab)
        elif newstate == STATE_ENCRYPTED and tab:
            if self.getCurrentTrust():
                tab.add_message(OTR_START_TRUSTED % format_dict, typ=self.log)
            else:
                format_dict['our_fpr'] = self.user.getPrivkey()
                format_dict['remote_fpr'] = self.getCurrentKey()
                tab.add_message(OTR_TUTORIAL % format_dict, typ=0)
                tab.add_message(OTR_START_UNTRUSTED % format_dict, typ=self.log)
            hl(tab)

        log.debug('Set encryption state of %s to %s', self.peer, states[newstate])
        super(PoezioContext, self).setState(newstate)
        if tab:
            self.core.refresh_window()
            self.core.doupdate()

class PoezioAccount(Account):
    """
    OTR Account, keeps track of a specific account (ours)

    Redefines the load/save methods from potr.context.Account
    """

    def __init__(self, jid, key_dir):
        super(PoezioAccount, self).__init__(jid, 'xmpp', 0)
        self.key_dir = os.path.join(key_dir, jid)

    def load_privkey(self):
        try:
            with open(self.key_dir + '.key3', 'rb') as keyfile:
                return potr.crypt.PK.parsePrivateKey(keyfile.read())[0]
        except:
            log.error('Error in load_privkey', exc_info=True)

    def drop_privkey(self):
        try:
            os.remove(self.key_dir + '.key3')
        except:
            log.exception('Error in drop_privkey (removing %s)', self.key_dir + '.key3')
        self.privkey = None

    def save_privkey(self):
        try:
            with open(self.key_dir + '.key3', 'xb') as keyfile:
                keyfile.write(self.getPrivkey().serializePrivateKey())
        except:
            log.error('Error in save_privkey', exc_info=True)

    def load_trusts(self):
        try:
            with open(self.key_dir + '.fpr', 'r') as fpr_fd:
                for line in fpr_fd:
                    ctx, acc, proto, fpr, trust = line[:-1].split('\t')

                    if acc != self.name or proto != 'xmpp':
                        continue
                    jid = safeJID(ctx).bare
                    if not jid:
                        continue
                    self.setTrust(jid, fpr, trust)
        except:
            log.error('Error in load_trusts', exc_info=True)

    def save_trusts(self):
        try:
            with open(self.key_dir + '.fpr', 'w') as fpr_fd:
                for uid, trusts in self.trusts.items():
                    for fpr, trustVal in trusts.items():
                        fpr_fd.write('\t'.join((uid, self.name, 'xmpp', fpr, trustVal)))
                        fpr_fd.write('\n')
        except:
            log.exception('Error in save_trusts', exc_info=True)

    saveTrusts = save_trusts
    loadTrusts = load_trusts
    loadPrivkey = load_privkey
    savePrivkey = save_privkey

states = {
    STATE_PLAINTEXT: 'plaintext',
    STATE_ENCRYPTED: 'encrypted',
    STATE_FINISHED: 'finished',
}

class Plugin(BasePlugin):

    def init(self):
        # set the default values from the config
        keys_dir = self.config.get('keys_dir', '')
        otr_dir = Path(keys_dir).expanduser() if keys_dir else xdg.DATA_HOME / 'otr'
        try:
            otr_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.api.information('The OTR-specific folder could not '
                                 'be created: %s. Poezio will be unable '
                                 'to save keys and trusts' % e, 'OTR')

        except Exception as e:
            self.api.information('The OTR-specific folder could not '
                                 'be created. Poezio will be unable '
                                 'to save keys and trusts', 'OTR')

        self.api.add_event_handler('conversation_msg', self.on_conversation_msg)
        self.api.add_event_handler('private_msg', self.on_conversation_msg)
        self.api.add_event_handler('conversation_say_after', self.on_conversation_say)
        self.api.add_event_handler('private_say_after', self.on_conversation_say)

        StaticConversationTab.add_information_element('otr', self.display_encryption_status)
        PrivateTab.add_information_element('otr', self.display_encryption_status)

        self.core.xmpp.plugin['xep_0030'].add_feature('urn:xmpp:otr:0')

        self.account = PoezioAccount(self.core.xmpp.boundjid.bare, otr_dir)
        self.account.load_trusts()
        self.contexts = {}
        usage = '<start|refresh|end|fpr|ourfpr|drop|trust|untrust>'
        shortdesc = 'Manage an OTR conversation'
        desc = ('Manage an OTR conversation.\n'
                'start/refresh: Start or refresh a conversation\n'
                'end: End a conversation\n'
                'fpr: Show the fingerprint of the key of the remote user\n'
                'ourfpr: Show the fingerprint of your own key\n'
                'drop: Remove the current key (FOREVER)\n'
                'trust: Set this key for this contact as trusted\n'
                'untrust: Remove the trust for the key of this contact\n')
        smp_usage = '<abort|ask|answer> [question] [answer]'
        smp_short = 'Identify a contact'
        smp_desc = ('Verify the identify of your contact by using a pre-defined secret.\n'
                    'abort: Abort an ongoing verification\n'
                    'ask: Start a verification, with a question or not\n'
                    'answer: Finish a verification\n')

        self.api.add_tab_command(StaticConversationTab, 'otrsmp', self.command_smp,
                                 help=smp_desc, usage=smp_usage, short=smp_short,
                                 completion=self.completion_smp)
        self.api.add_tab_command(PrivateTab, 'otrsmp', self.command_smp,
                                 help=smp_desc, usage=smp_usage, short=smp_short,
                                 completion=self.completion_smp)

        self.api.add_tab_command(StaticConversationTab, 'otr', self.command_otr,
                                 help=desc, usage=usage, short=shortdesc,
                                 completion=self.completion_otr)
        self.api.add_tab_command(PrivateTab, 'otr', self.command_otr,
                                 help=desc, usage=usage, short=shortdesc,
                                 completion=self.completion_otr)

    def cleanup(self):
        for context in self.contexts.values():
            context.disconnect()

        self.core.xmpp.plugin['xep_0030'].del_feature(feature='urn:xmpp:otr:0')

        StaticConversationTab.remove_information_element('otr')
        PrivateTab.remove_information_element('otr')

    def get_context(self, jid):
        """
        Retrieve or create an OTR context
        """
        jid = safeJID(jid)
        if jid.full not in self.contexts:
            flags = POLICY_FLAGS.copy()
            require = self.config.get_by_tabname('require_encryption',
                                                 jid.bare, default=False)
            flags['REQUIRE_ENCRYPTION'] = require
            logging_policy = self.config.get_by_tabname('log', jid.bare , default=False)
            self.contexts[jid.full] = PoezioContext(self.account, jid.full, self.core.xmpp, self.core)
            self.contexts[jid.full].log = 1 if logging_policy else 0
            self.contexts[jid.full].flags = flags
        return self.contexts[jid.full]

    def on_conversation_msg(self, msg, tab):
        """
        Message received
        """
        format_dict = {
            'jid_c': '\x19%s}' % dump_tuple(get_theme().COLOR_MUC_JID),
            'info':  '\x19%s}' % dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
            'jid': msg['from']
        }
        try:
            ctx = self.get_context(msg['from'])
            txt, tlvs = ctx.receiveMessage(msg["body"].encode('utf-8'))

            # SMP
            if tlvs:
                self.handle_tlvs(tlvs, ctx, tab, format_dict)
        except UnencryptedMessage as err:
            # received an unencrypted message inside an OTR session
            self.unencrypted_message_received(err, ctx, msg, tab, format_dict)
            self.otr_start(tab, tab.name, format_dict)
            return
        except NotOTRMessage as err:
            # ignore non-otr messages
            # if we expected an OTR message, we would have
            # got an UnencryptedMesssage
            # but do an additional check because of a bug with potr and py3k
            if ctx.state != STATE_PLAINTEXT or ctx.getPolicy('REQUIRE_ENCRYPTION'):
                self.unencrypted_message_received(err, ctx, msg, tab, format_dict)
                self.otr_start(tab, tab.name, format_dict)
            return
        except ErrorReceived as err:
            # Received an OTR error
            format_dict['err'] = err.args[0].error.decode('utf-8', errors='replace')
            tab.add_message(OTR_ERROR % format_dict, typ=0)
            del msg['body']
            del msg['html']
            hl(tab)
            self.core.refresh_window()
            return
        except NotEncryptedError as err:
            # Encrypted message received, but unreadable as we do not have
            # an OTR session in place.
            text = MESSAGE_UNREADABLE % format_dict
            tab.add_message(text, jid=msg['from'], typ=0)
            hl(tab)
            del msg['body']
            del msg['html']
            self.core.refresh_window()
            return
        except crypt.InvalidParameterError:
            # Malformed OTR payload and stuff
            text = MESSAGE_INVALID % format_dict
            tab.add_message(text, jid=msg['from'], typ=0)
            hl(tab)
            del msg['body']
            del msg['html']
            self.core.refresh_window()
            return
        except Exception:
            # Unexpected error
            import traceback
            exc = traceback.format_exc()
            format_dict['exc'] = exc
            tab.add_message(POTR_ERROR % format_dict, typ=0)
            log.error('Unspecified error in the OTR plugin', exc_info=True)
            return
        # No error, proceed with the message
        self.encrypted_message_received(msg, ctx, tab, txt)

    def handle_tlvs(self, tlvs, ctx, tab, format_dict):
        """
        If the message had a TLV, it means we received part of an SMP
        exchange.
        """
        smp1q = get_tlv(tlvs, potr.proto.SMP1QTLV)
        smp1 = get_tlv(tlvs, potr.proto.SMP1TLV)
        smp2 = get_tlv(tlvs, potr.proto.SMP2TLV)
        smp3 = get_tlv(tlvs, potr.proto.SMP3TLV)
        smp4 = get_tlv(tlvs, potr.proto.SMP4TLV)
        abort = get_tlv(tlvs, potr.proto.SMPABORTTLV)
        if abort:
            ctx.reset_smp()
            tab.add_message(SMP_ABORTED_PEER % format_dict, typ=0)
        elif ctx.in_smp and not ctx.smpIsValid():
            ctx.reset_smp()
            tab.add_message(SMP_ABORTED % format_dict, typ=0)
        elif smp1 or smp1q:
            # Received an SMP request (with a question or not)
            if smp1q:
                try:
                    question = ' with question: \x19o' + smp1q.msg.decode('utf-8')
                except UnicodeDecodeError:
                    self.api.information('The peer sent a question but it had a wrong encoding', 'Error')
                    question = ''
            else:
                question = ''
            ctx.in_smp = True
            # we did not initiate it
            ctx.smp_own = False
            format_dict['q'] = question
            tab.add_message(SMP_REQUESTED % format_dict, typ=0)
        elif smp2:
            # SMP reply received
            if not ctx.in_smp:
                ctx.reset_smp()
            else:
                tab.add_message(SMP_PROGRESS % format_dict, typ=0)
        elif smp3 or smp4:
            # Type 4 (SMP message 3) or 5 (SMP message 4) TLVs received
            # in both cases it is the final message of the SMP exchange
            if ctx.smpIsSuccess():
                tab.add_message(SMP_SUCCESS % format_dict, typ=0)
                if not ctx.getCurrentTrust():
                    tab.add_message(SMP_RECIPROCATE % format_dict, typ=0)
            else:
                tab.add_message(SMP_FAIL % format_dict, typ=0)
            ctx.reset_smp()
        hl(tab)
        self.core.refresh_window()

    def unencrypted_message_received(self, err, ctx, msg, tab, format_dict):
        """
        An unencrypted message was received while we expected it to be
        encrypted. Display it with a warning.
        """
        format_dict['msg'] = err.args[0].decode('utf-8')
        text = MESSAGE_UNENCRYPTED % format_dict
        tab.add_message(text, jid=msg['from'], typ=ctx.log)
        del msg['body']
        del msg['html']
        hl(tab)
        self.core.refresh_window()

    def encrypted_message_received(self, msg, ctx, tab, txt):
        """
        A properly encrypted message was received, so we add it to the
        buffer, and try to format it according to the configuration.
        """
        # remove xhtml
        del msg['html']
        del msg['body']

        if not txt:
            return
        if isinstance(tab, PrivateTab):
            user = tab.parent_muc.get_user_by_name(msg['from'].resource)
            nick_color = None
        else:
            user = None
            nick_color = get_theme().COLOR_REMOTE_USER

        body = txt.decode()
        decode_entities = self.config.get_by_tabname('decode_entities',
                                                     msg['from'].bare,
                                                     default=True)
        decode_newlines = self.config.get_by_tabname('decode_newlines',
                                                     msg['from'].bare,
                                                     default=True)
        if self.config.get_by_tabname('decode_xhtml', msg['from'].bare, default=True):
            try:
                body = xhtml.xhtml_to_poezio_colors(body, force=True)
            except Exception:
                if decode_entities:
                    body = html.unescape(body)
                if decode_newlines:
                    body = body.replace('<br/>', '\n').replace('<br>', '\n')
        else:
            if decode_entities:
                body = html.unescape(body)
            if decode_newlines:
                body = body.replace('<br/>', '\n').replace('<br>', '\n')
        tab.add_message(body, nickname=tab.nick, jid=msg['from'],
                        forced_user=user, typ=ctx.log,
                        nick_color=nick_color)
        hl(tab)
        self.core.refresh_window()
        del msg['body']

    def find_encrypted_context_with_matching(self, bare_jid):
        """
        Find an OTR session from a bare JID.
        """
        for ctx in self.contexts:
            if safeJID(ctx).bare == bare_jid and self.contexts[ctx].state == STATE_ENCRYPTED:
                return self.contexts[ctx]
        return None

    def on_conversation_say(self, msg, tab):
        """
        On message sent
        """
        name = tab.name
        jid = safeJID(tab.name)

        format_dict = {
            'jid_c': '\x19%s}' % dump_tuple(get_theme().COLOR_MUC_JID),
            'info': '\x19%s}' % dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
            'jid': name,
        }

        ctx = self.find_encrypted_context_with_matching(jid)
        default_ctx = self.get_context(name)

        if ctx is None:
            ctx = default_ctx

        if is_relevant(tab) and ctx and ctx.state == STATE_ENCRYPTED:
            ctx.sendMessage(0, msg['body'].encode('utf-8'))
            if not tab.send_chat_state('active'):
                tab.send_chat_state('inactive', always_send=True)

            tab.add_message(msg['body'],
                            nickname=self.core.own_nick or tab.own_nick,
                            nick_color=get_theme().COLOR_OWN_NICK,
                            identifier=msg['id'],
                            jid=self.core.xmpp.boundjid,
                            typ=ctx.log)
            # remove everything from the message so that it doesn’t get sent
            del msg['body']
            del msg['replace']
            del msg['html']
        elif is_relevant(tab) and ctx and ctx.getPolicy('REQUIRE_ENCRYPTION'):
            warning_msg = MESSAGE_NOT_SENT % format_dict
            tab.add_message(warning_msg, typ=0)
            del msg['body']
            del msg['replace']
            del msg['html']
            self.otr_start(tab, name, format_dict)
        elif not is_relevant(tab) and ctx and (
                ctx.state == STATE_ENCRYPTED or ctx.getPolicy('REQUIRE_ENCRYPTION')):
            contact = roster[tab.name]
            res = []
            if contact:
                res = [resource.jid for resource in contact.resources]
            help_msg = ''
            if res:
                help_msg = TAB_HELP_RESOURCE % ''.join(('\n - /message %s' % jid) for jid in res)
            format_dict['help'] = help_msg
            warning_msg = INCOMPATIBLE_TAB % format_dict
            tab.add_message(warning_msg, typ=0)
            del msg['body']
            del msg['replace']
            del msg['html']

    def display_encryption_status(self, jid):
        """
        Returns the text to display in the infobar (the OTR status)
        """
        context = self.get_context(jid)
        if safeJID(jid).bare == jid and context.state != STATE_ENCRYPTED:
            ctx = self.find_encrypted_context_with_matching(jid)
            if ctx:
                context = ctx
        state = states[context.state]
        trust = 'trusted' if context.getCurrentTrust() else 'untrusted'

        return ' OTR: %s (%s)' % (state, trust)

    def command_otr(self, arg):
        """
        /otr [start|refresh|end|fpr|ourfpr]
        """
        args = common.shell_split(arg)
        if not args:
            return self.core.command.help('otr')
        action = args.pop(0)
        tab = self.api.current_tab()
        name = tab.name
        format_dict = {
            'jid_c': '\x19%s}' % dump_tuple(get_theme().COLOR_MUC_JID),
            'info': '\x19%s}' % dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
            'normal': '\x19%s}' % dump_tuple(get_theme().COLOR_NORMAL_TEXT),
            'jid': name,
            'bare_jid': safeJID(name).bare
        }

        if action == 'end': # close the session
            context = self.get_context(name)
            context.disconnect()
        elif action == 'start' or action == 'refresh':
            self.otr_start(tab, name, format_dict)
        elif action == 'ourfpr':
            format_dict['fpr'] = self.account.getPrivkey()
            tab.add_message(OTR_OWN_FPR % format_dict, typ=0)
        elif action == 'fpr':
            if name in self.contexts:
                ctx = self.contexts[name]
                if ctx.getCurrentKey() is not None:
                    format_dict['fpr'] = ctx.getCurrentKey()
                    tab.add_message(OTR_REMOTE_FPR % format_dict, typ=0)
                else:
                    tab.add_message(OTR_NO_FPR % format_dict, typ=0)
        elif action == 'drop':
            # drop the privkey (and obviously, end the current conversations before that)
            for context in self.contexts.values():
                if context.state not in (STATE_FINISHED, STATE_PLAINTEXT):
                    context.disconnect()
            self.account.drop_privkey()
            tab.add_message(KEY_DROPPED % format_dict, typ=0)
        elif action == 'trust':
            ctx = self.get_context(name)
            key = ctx.getCurrentKey()
            if key:
                fpr = key.cfingerprint()
            else:
                return
            if not ctx.getCurrentTrust():
                format_dict['key'] = key
                ctx.setTrust(fpr, 'verified')
                self.account.saveTrusts()
                tab.add_message(TRUST_ADDED % format_dict, typ=0)
        elif action == 'untrust':
            ctx = self.get_context(name)
            key = ctx.getCurrentKey()
            if key:
                fpr = key.cfingerprint()
            else:
                return
            if ctx.getCurrentTrust():
                format_dict['key'] = key
                ctx.setTrust(fpr, '')
                self.account.saveTrusts()
                tab.add_message(TRUST_REMOVED % format_dict, typ=0)
        self.core.refresh_window()

    def otr_start(self, tab, name, format_dict):
        """
        Start an otr conversation with a contact
        """
        secs = self.config.get('timeout', 3)
        def notify_otr_timeout():
            tab_name = tab.name
            otr = self.find_encrypted_context_with_matching(tab_name)
            if otr.state != STATE_ENCRYPTED:
                format_dict['secs'] = secs
                text = OTR_NOT_ENABLED % format_dict
                tab.add_message(text, typ=0)
                self.core.refresh_window()
        if secs > 0:
            event = self.api.create_delayed_event(secs, notify_otr_timeout)
            self.api.add_timed_event(event)
        body = self.get_context(name).sendMessage(0, b'?OTRv?').decode()
        self.core.xmpp.send_message(mto=name, mtype='chat', mbody=body)
        tab.add_message(OTR_REQUEST % format_dict, typ=0)

    @staticmethod
    def completion_otr(the_input):
        """
        Completion for /otr
        """
        comp = ['start', 'fpr', 'ourfpr', 'refresh', 'end', 'trust', 'untrust']
        return Completion(the_input.new_completion, comp, 1, quotify=False)

    @command_args_parser.quoted(1, 2)
    def command_smp(self, args):
        """
        /otrsmp <ask|answer|abort> [question] [secret]
        """
        if args is None or not args:
            return self.core.command.help('otrsmp')
        length = len(args)
        action = args.pop(0)
        if length == 2:
            question = None
            secret = args.pop(0).encode('utf-8')
        elif length == 3:
            question = args.pop(0).encode('utf-8')
            secret = args.pop(0).encode('utf-8')
        else:
            question = secret = None

        tab = self.api.current_tab()
        name = tab.name
        format_dict = {
            'jid_c': '\x19%s}' % dump_tuple(get_theme().COLOR_MUC_JID),
            'info': '\x19%s}' % dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
            'jid': name,
            'bare_jid': safeJID(name).bare
        }

        ctx = self.get_context(name)
        if ctx.state != STATE_ENCRYPTED:
            self.api.information('The current conversation is not encrypted',
                                 'Error')
            return

        if action == 'ask':
            ctx.in_smp = True
            ctx.smp_own = True
            if question:
                ctx.smpInit(secret, question)
            else:
                ctx.smpInit(secret)
            tab.add_message(SMP_INITIATED % format_dict, typ=0)
        elif action == 'answer':
            ctx.smpGotSecret(secret)
        elif action == 'abort':
            if ctx.in_smp:
                ctx.smpAbort()
                tab.add_message(SMP_ABORTED % format_dict, typ=0)
        self.core.refresh_window()

    @staticmethod
    def completion_smp(the_input):
        """Completion for /otrsmp"""
        if the_input.get_argument_position() == 1:
            return Completion(the_input.new_completion, ['ask', 'answer', 'abort'], 1, quotify=False)

def get_tlv(tlvs, cls):
    """Find the instance of a class in a list"""
    for tlv in tlvs:
        if isinstance(tlv, cls):
            return tlv

def is_relevant(tab):
    """Check if a tab should be concerned with OTR"""
    return isinstance(tab, (StaticConversationTab, PrivateTab))
