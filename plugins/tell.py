"""
The command added by this plugin sends a message to someone when he next joins.

Usage
-----
This plugin defines two new commands for MUC tabs: :term:`/tell` and :term:`/untell`.

.. glossary::
    :sorted:

    /tell
         **Usage:** ``/tell <nick> <message>``

         Send *message* to *nick* at his next join.

    /untell
        **Usage:** ``/untell <nick>``

        Cancel all scheduled messages to *nick*.

"""
from plugin import BasePlugin
import tabs
import common

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
        self.api.add_event_handler('muc_join', self.on_join)
        # {tab -> {nick -> [messages]}
        self.tabs = {}

    def on_join(self, presence, tab):
        if not tab in self.tabs:
            return
        nick = presence['from'].resource
        if not nick in self.tabs[tab]:
            return
        for i in self.tabs[tab][nick]:
            tab.command_say("%s: %s" % (nick, i))
        del self.tabs[tab][nick]

    def command_tell(self, args):
        """/tell <nick> <message>"""
        arg = common.shell_split(args)
        if len(arg) != 2:
            self.core.command_help('tell')
            return
        nick, msg = arg
        tab = self.api.current_tab()
        if not tab in self.tabs:
            self.tabs[tab] = {}
        if not nick in self.tabs[tab]:
            self.tabs[tab][nick] = []
        self.tabs[tab][nick].append(msg)
        self.api.information('Message for %s queued' % nick, 'Info')

    def command_untell(self, args):
        """/untell <nick>"""
        tab = self.api.current_tab()
        if not tab in self.tabs:
            return
        nick = args
        if not nick in self.tabs[tab]:
            return
        del self.tabs[tab][nick]
        self.api.information('Messages for %s unqueued' % nick, 'Info')

    def completion_untell(self, the_input):
        tab = self.api.current_tab()
        if not tab in self.tabs:
            return the_input.auto_completion([], '')
        return the_input.auto_completion(list(self.tabs[tab]), '', quotify=False)

