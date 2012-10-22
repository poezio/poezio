from plugin import BasePlugin
from xhtml import clean_text, get_body_from_message_stanza
from timed_events import DelayedEvent
import shlex

class Plugin(BasePlugin):
    def init(self):
        self.add_event_handler('private_msg', self.on_private_msg)
        self.add_event_handler('conversation_msg', self.on_conversation_msg)
        self.add_event_handler('highlight', self.on_highlight)

    def on_private_msg(self, message, tab):
        fro = message['from']
        self.do_notify(message, fro)

    def on_highlight(self, message, tab):
        fro = message['from'].resource
        self.do_notify(message, fro)

    def on_conversation_msg(self, message, tab):
        fro = message['from'].bare
        self.do_notify(message, fro)

    def do_notify(self, message, fro):
        body = clean_text(get_body_from_message_stanza(message))
        if not body:
            return
        command_str = self.config.get('command', '').strip()
        if not command_str:
            self.core.information('No notification command was provided in the configuration file', 'Warning')
            return
        command = [arg % {'body': body.replace('\n', ' '), 'from': fro} for arg in shlex.split(command_str)]
        self.core.exec_command(command)
        after_command_str = self.config.get('after_command', '').strip()
        if not after_command_str:
            return
        after_command = [arg % {'body': body.replace('\n', ' '), 'from': fro} for arg in shlex.split(after_command_str)]
        delayed_event = DelayedEvent(self.config.get('delay', 1), self.core.exec_command, after_command)
        self.core.add_timed_event(delayed_event)
