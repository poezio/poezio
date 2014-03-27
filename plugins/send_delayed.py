"""
Send a message after a certain delay.

Usage
-----

This plugin adds a command to the chat tabs.

.. glossary::

    /send_delayed
        **Usage:** ``/send_delayed <delay> <message>``

        Send a message after a given delay to the current tab.
        The delay can be either in seconds or in a classic XdXhXm format
        (e.g. ``7h3m`` or ``1d``), some examples are given with the
        autocompletion.


"""
from plugin import BasePlugin
import tabs
import common
import timed_events

class Plugin(BasePlugin):

    def init(self):
        for _class in (tabs.PrivateTab, tabs.ConversationTab, tabs.MucTab):
            self.api.add_tab_command(_class, 'send_delayed', self.command_delayed,
                    usage='<delay> <message>',
                    help='Send <message> with a delay of <delay> seconds.',
                    short='Send a message later',
                    completion=self.completion_delay)

    def command_delayed(self, arg):
        args = common.shell_split(arg)
        if len(args) != 2:
            return
        delay = common.parse_str_to_secs(args[0])
        if not delay:
            return

        tab = self.api.current_tab()
        timed_event = timed_events.DelayedEvent(delay, self.say, (tab, args[1]))
        self.api.add_timed_event(timed_event)

    def completion_delay(self, the_input):
        txt = the_input.get_text()
        args = common.shell_split(txt)
        n = len(args)
        if txt.endswith(' '):
            n += 1
        if n == 2:
            return the_input.auto_completion(["60", "5m", "15m", "30m", "1h", "10h", "1d"], '')

    def say(self, args=None):
        if not args:
            return

        tab = args[0]
        # anything could happen to the tab during the interval
        try:
            tab.command_say(args[1])
        except:
            pass
