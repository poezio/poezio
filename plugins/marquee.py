"""
Marquee plugin: replicate the html <marquee/> tag with message corrections.

Usage of this plugin is not recommended.

Commands
--------

.. glossary::

    /marquee <text>
        Send the following text with <marquee/> behavior

Configuration
-------------

.. glossary::
    :sorted:

    refresh
        **Default:** ``1``

        Interval between each correction (the closest to 0 is the fastest)

    total_duration
        **Default:** ``30``

        Total duration of the animation.

    padding
        **Default:** ``20``

        Padding to use to move the text.


"""
from poezio.plugin import BasePlugin
from poezio import tabs
from poezio import xhtml
from poezio.decorators import command_args_parser

def move(text, step, spacing):
    new_text = text + (" " * spacing)
    return new_text[-(step % len(new_text)):] + new_text[:-(step % len(new_text))]

class Plugin(BasePlugin):
    default_config = {"marquee": {"refresh": 1.0, "total_duration": 30, "padding": 20}}

    def init(self):
        for tab_t in [tabs.MucTab, tabs.ConversationTab, tabs.PrivateTab]:
            self.add_tab_command(tab_t, 'marquee', self.command_marquee,
                                 'Replicate the <marquee/> behavior in a message')

    @command_args_parser.raw
    def command_marquee(self, args):
        tab = self.api.current_tab()
        args = xhtml.clean_text(xhtml.convert_simple_to_full_colors(args))
        tab.command_say(args)
        is_muctab = isinstance(tab, tabs.MucTab)
        msg_id = tab.last_sent_message["id"]
        jid = tab.name

        event = self.api.create_delayed_event(self.config.get("refresh"),
                                              self.delayed_event,
                                              jid, args, msg_id, 1, 0,
                                              is_muctab)
        self.api.add_timed_event(event)

    def delayed_event(self, jid, body, msg_id, step, duration, is_muctab):
        if duration >= self.config.get("total_duration"):
            return
        message = self.core.xmpp.make_message(jid)
        message["type"] = "groupchat" if is_muctab else "chat"
        message["body"] = move(body, step, self.config.get("padding"))
        message["replace"]["id"] = msg_id
        message.send()
        event = self.api.create_delayed_event(self.config.get("refresh"),
                                              self.delayed_event, jid, body,
                                              message["id"], step + 1,
                                              duration + self.config.get("refresh"),
                                              is_muctab)
        self.api.add_timed_event(event)


