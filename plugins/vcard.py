"""
This plugin adds a :term:`/vcard` command to all tabs, allowing you to request
and display the vcard-temp of any given entity.

Command
-------

.. glossary::

    /vcard

        **Usage (globally):** ``/vcard <jid>``

        **Usage (in a chatroom tab):** ``/vcard <jid or nick>``

        **Usage (in a conversation or contact list tab):** ``/vcard [jid]``

        Globally, you can do ``/vcard user@server.example`` to get a vcard.

        In a chatroom , you can either do it on a JID or a nick (``/vcard nick``,
        ``/vcard room@muc.server.example/nick`` or ``/vcard
        user@server.example``).

        In a private or a direct conversation, you can do ``/vcard`` to request
        vcard from the current interlocutor, and in the contact list to do it
        on the currently selected contact.
"""

from poezio.decorators import command_args_parser
from poezio.plugin import BasePlugin
from poezio.roster import roster
from poezio.common import safeJID
from poezio.contact import Contact, Resource
from poezio.core.structs import Completion
from poezio import tabs
from slixmpp.jid import JID, InvalidJID

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('vcard', self.command_vcard,
                usage='<jid>',
                help='Send an XMPP vcard request to jid (see XEP-0054).',
                short='Send a vcard request',
                completion=self.completion_vcard)
        self.api.add_tab_command(tabs.MucTab, 'vcard', self.command_muc_vcard,
                usage='<jid|nick>',
                help='Send an XMPP vcard request to jid or nick (see XEP-0054).',
                short='Send a vcard request.',
                completion=self.completion_muc_vcard)
        self.api.add_tab_command(tabs.RosterInfoTab, 'vcard', self.command_roster_vcard,
                usage='<jid>',
                help='Send an XMPP vcard request to jid (see XEP-0054).',
                short='Send a vcard request.',
                completion=self.completion_vcard)
        for _class in (tabs.PrivateTab, tabs.ConversationTab):
            self.api.add_tab_command(_class, 'vcard', self.command_private_vcard,
                    usage='[jid]',
                    help='Send an XMPP vcard request to the current interlocutor or the given JID.',
                    short='Send a vcard request',
                    completion=self.completion_vcard)

    def _handle_vcard(self, iq):
        '''Retrieves a vCard from vcard-temp and present it as a DataFormsTab.
        '''
        jid = iq['from']

        if iq['type'] == 'error':
            self.api.information('Error retrieving vCard for %s: %s: %s' % (jid, iq['error']['type'], iq['error']['condition']), 'Error')
            return

        vcard = iq['vcard_temp']

        form = self.core.xmpp['xep_0004'].make_form(ftype='result', title='vCard of %s' % jid)

        # TODO: implement the other fields.

        form.add_field(var='FN', ftype='text-single', label='Name', value=vcard['FN'])
        form.add_field(var='NICKNAME', ftype='text-multi', label='Nicknames', value=vcard['NICKNAME'])

        # TODO: find a way to detect whether this is present or not.
        form.add_field(ftype='fixed', value='Full Name')
        form.add_field(var='N/GIVEN', ftype='text-single', label='Given', value=vcard['N']['GIVEN'])
        form.add_field(var='N/MIDDLE', ftype='text-single', label='Middle', value=vcard['N']['MIDDLE'])
        form.add_field(var='N/FAMILY', ftype='text-single', label='Family', value=vcard['N']['FAMILY'])
        form.add_field(var='N/PREFIX', ftype='text-single', label='Prefix', value=vcard['N']['PREFIX'])
        form.add_field(var='N/SUFFIX', ftype='text-single', label='Suffix', value=vcard['N']['SUFFIX'])

        for i, addr in enumerate(vcard['addresses']):
            form.add_field(ftype='fixed', value='Address')
            values = [type_ for type_ in addr.bool_interfaces if addr[type_]]
            addr_type = form.add_field(var='ADR %d/TYPE' % i, ftype='list-multi', label='Type', value=values)
            addr_type.add_option(label='Home', value='HOME')
            for type_ in addr.bool_interfaces:
                addr_type.add_option(label=type_, value=type_)
            form.add_field(var='ADR %d/POBOX' % i, ftype='text-single', label='Pobox', value=addr['POBOX'])
            form.add_field(var='ADR %d/EXTADD' % i, ftype='text-single', label='Extended Address', value=addr['EXTADD'])
            form.add_field(var='ADR %d/STREET' % i, ftype='text-single', label='Street', value=addr['STREET'])
            form.add_field(var='ADR %d/LOCALITY' % i, ftype='text-single', label='Locality', value=addr['LOCALITY'])
            form.add_field(var='ADR %d/REGION' % i, ftype='text-single', label='Region', value=addr['REGION'])
            form.add_field(var='ADR %d/PCODE' % i, ftype='text-single', label='Post Code', value=addr['PCODE'])
            form.add_field(var='ADR %d/CTRY' % i, ftype='text-single', label='Country', value=addr['CTRY'])

        for i, tel in enumerate(vcard['telephone_numbers']):
            form.add_field(ftype='fixed', value='Telephone')
            values = [type_ for type_ in tel.bool_interfaces if tel[type_]]
            tel_type = form.add_field(var='TEL %d/TYPE' % i, ftype='list-multi', label='Type', value=values)
            for type_ in tel.bool_interfaces:
                tel_type.add_option(label=type_, value=type_)
            form.add_field(var='TEL %d/NUMBER' % i, ftype='text-single', label='Number', value=tel['NUMBER'])

        for i, email in enumerate(vcard['emails']):
            form.add_field(ftype='fixed', value='Email address')
            values = [type_ for type_ in email.bool_interfaces if email[type_]]
            email_type = form.add_field(var='EMAIL %d/TYPE' % i, ftype='list-multi', label='Type', value=values)
            for type_ in email.bool_interfaces:
                email_type.add_option(label=type_, value=type_)
            form.add_field(var='EMAIL %d/USERID' % i, ftype='text-single', label='Email Address', value=email['USERID'])

        form.add_field(ftype='fixed', value='Misc')
        form.add_field(var='BDAY', ftype='text-single', label='Birthday', value=str(vcard['BDAY']))

        for i, jabberid in enumerate(vcard['jids']):
            form.add_field(ftype='fixed', value='URL')
            form.add_field(var='JABBERID %d' % i, ftype='jid-single', label='URL', value=jabberid['JABBERID'])

        for i, url in enumerate(vcard['urls']):
            form.add_field(ftype='fixed', value='URL')
            form.add_field(var='URL %d' % i, ftype='text-single', label='URL', value=url['URL'])

        for i, desc in enumerate(vcard['descriptions']):
            form.add_field(ftype='fixed', value='Description')
            form.add_field(var='DESC %d' % i, ftype='text-multi', label='Description', value=desc['DESC'])

        on_validate = lambda form: self.core.close_tab()
        on_cancel = lambda form: self.core.close_tab()
        self.core.open_new_form(form, on_cancel, on_validate)

    def _get_vcard(self, jid):
        '''Send an iq to ask the vCard.'''
        def timeout_cb(iq):
            self.api.information('Timeout while retrieving vCard for %s' % jid, 'Error')
            return

        self.core.xmpp.plugin['xep_0054'].get_vcard(jid=jid, timeout=30,
                                                    callback=self._handle_vcard,
                                                    timeout_callback=timeout_cb)

    @command_args_parser.raw
    def command_vcard(self, arg):
        if not arg:
            self.core.command.help('vcard')
            return

        try:
            jid = JID(arg)
        except InvalidJID:
            self.api.information('Invalid JID: %s' % arg, 'Error')
            return

        self._get_vcard(jid)

    @command_args_parser.raw
    def command_private_vcard(self, arg):
        if arg:
            self.command_vcard(arg)
            return
        self.command_vcard(self.api.current_tab().name)

    @command_args_parser.raw
    def command_muc_vcard(self, arg):
        if not arg:
            self.core.command.help('vcard')
            return
        user = self.api.current_tab().get_user_by_name(arg)
        if user:
            # No need to use safeJID here, we already know the JID is valid.
            jid = JID(self.api.current_tab().name + '/' + user.nick)
        else:
            jid = safeJID(arg)
        self._get_vcard(jid)

    @command_args_parser.raw
    def command_roster_vcard(self, arg):
        if arg:
            self.command_vcard(arg)
            return
        current = self.api.current_tab().selected_row
        if isinstance(current, Resource):
            self._get_vcard(JID(current.jid).bare)
        elif isinstance(current, Contact):
            self._get_vcard(current.bare_jid)

    def completion_vcard(self, the_input):
        contacts = [contact.bare_jid for contact in roster.get_contacts()]
        return Completion(the_input.auto_completion, contacts, '', quotify=False)

    def completion_muc_vcard(self, the_input):
        users = [user.nick for user in self.api.current_tab().users]
        users.extend([resource.jid for contact in roster.get_contacts() for resource in contact.resources])
        return Completion(the_input.auto_completion, users, '', quotify=False)
