"""
The command added by this plugin sends a message to someone when he next joins.

Usage
-----
This plugin defines two new commands for chatroom tabs:
:term:`/tell`, :term:`/untell`, and :term:`/list_tell`.

.. glossary::
    :sorted:

    /tell
         **Usage:** ``/tell <nick> <message>``

         Send *message* to *nick* at his next join.

    /untell
        **Usage:** ``/untell <nick>``

        Cancel all scheduled messages to *nick*.

    /list_tell
        **Usage:** ``/list_tell``

        List all queued messages for the current chatroom.

"""
from poezio.plugin import BasePlugin
from poezio.core.structs import Completion
from poezio.decorators import command_args_parser
from poezio import tabs

class Plugin(BasePlugin):
    def init(self):
        self.api.add_tab_command(tabs.MucTab, 'tell', self.command_tell,
                usage='<nick> <message>',
                help='Will tell <nick> of <message> when he next joins.',
                short='Send a message when someone joins')
        self.api.add_tab_command(tabs.MucTab, 'untell', self.command_untell,
                usage='<nick>',
                help='Remove the planned messages from /tell.',
                short='Cancel a /tell message',
                completion=self.completion_untell)
        self.api.add_tab_command(tabs.MucTab, 'list_tell', self.command_list_tell,
                usage='',
                help='List currently queued messages')
        self.api.add_event_handler('muc_join', self.on_join)
        self.api.add_event_handler('muc_nickchange', self.on_join)
        # {tab -> {nick -> [messages]}
        self.tabs = {}

    def on_join(self, presence, tab):
        if tab not in self.tabs:
            return
        nick = presence['from'].resource
        if nick not in self.tabs[tab]:
            return
        for i in self.tabs[tab][nick]:
            tab.command_say("%s: %s" % (nick, i))
        del self.tabs[tab][nick]

    @command_args_parser.ignored
    def command_list_tell(self):
        tab = self.api.current_tab()
        if not self.tabs.get(tab):
            self.api.information('No message queued.', 'Info')
            return
        build = ['Messages queued for %s:' % tab.name]
        for nick, messages in self.tabs[tab].items():
            build.append(' for %s:' % nick)
            for message in messages:
                build.append(' - %s' % message)
        self.api.information('\n'.join(build), 'Info')

    @command_args_parser.quoted(2)
    def command_tell(self, args):
        """/tell <nick> <message>"""
        if args is None:
            self.core.command.help('tell')
            return
        nick, msg = args
        tab = self.api.current_tab()
        if tab not in self.tabs:
            self.tabs[tab] = {}
        if nick not in self.tabs[tab]:
            self.tabs[tab][nick] = []
        self.tabs[tab][nick].append(msg)
        self.api.information('Message for %s queued' % nick, 'Info')

    def command_untell(self, args):
        """/untell <nick>"""
        tab = self.api.current_tab()
        if tab not in self.tabs:
            return
        nick = args
        if nick not in self.tabs[tab]:
            return
        del self.tabs[tab][nick]
        self.api.information('Messages for %s unqueued' % nick, 'Info')

    def completion_untell(self, the_input):
        tab = self.api.current_tab()
        if tab not in self.tabs:
            return Completion(the_input.auto_completion, [], '')
        return Completion(the_input.auto_completion, list(self.tabs[tab]), '', quotify=False)

