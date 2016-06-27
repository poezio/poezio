"""
Repeats the last message in the conversation.

Command
-------

.. glossary::

    /mirror
        **Usage:** ``/mirror``

"""
from poezio.plugin import BasePlugin
from poezio import tabs

class Plugin(BasePlugin):
    def init(self):
        for tab_type in (tabs.MucTab, tabs.PrivateTab, tabs.ConversationTab):
            self.api.add_tab_command(tab_type, 'mirror',
                    handler=self.mirror,
                    help='Repeat the last message from the conversation.',
                    short='Repeat the last message from the conversation.')

    def mirror(self, args):
        messages = self.api.get_conversation_messages()
        if not messages:
            # Do nothing if the conversation doesn’t contain any message
            return
        last_message = messages[-1]
        self.api.send_message(last_message.txt)
