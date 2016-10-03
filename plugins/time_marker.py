"""
Display the time between two messages.

Helps you identify the times of a conversation.  For example
if you disable the timestamps, and remove the join/quit notifications in a
chatroom, you can’t really distinguish when a conversation stopped and when
a new one started, because you don’t have a visual separation between the two.

This plugin displays a message in the conversation indicating the time that
passed between two messages, if the time is bigger than X minutes
(configurable, of course. Default is 15 minutes). This way you know how many time elapsed between
them, letting you understand more easily what is going on without any visual
clutter.

Configuration
-------------

You can configure the minimum delay between two messages, to display the time marker, in seconds. The default is 10 minutes (aka 600 seconds).

.. code-block:: ini

    [time_marker]
    delay = 600

Usage
-----

Messages like “2 hours, 25 minutes passed…” are automatically displayed into the converstation. You don’t need to (and can’t) do anything.

"""

from poezio.plugin import BasePlugin
from datetime import datetime, timedelta

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler("muc_msg", self.on_muc_msg)
        # Dict of MucTab.name: last_message date, so we don’t have to
        # retrieve the messages of the given muc to look for the last
        # message’s date each time.  Also, now that I think about it, the
        # date of the message is not event kept in the Message object, so…
        self.last_messages = {}

    def on_muc_msg(self, message, tab):
        def format_timedelta(delta):
            """
            Return a string of the form D days, H hours, M minutes, S
            seconds.  If the number of total minutes is bigger than 10, we
            usually don’t care anymore about the number of seconds, so we
            don’t display it.  Same thing if the number of days is bigger
            than one, we don’t display the minutes either.
            """
            days = delta.days
            hours = delta.seconds // 3600
            minutes = delta.seconds // 60 % 60
            seconds = delta.seconds % 60
            res = ''
            if days > 0:
                res = "%s days, " % days
            if hours > 0:
                res += "%s hours, " % hours
            if days == 0 and minutes != 0:
                res += "%s minutes, " % minutes
            if delta.total_seconds() < 600:
                res += "%s seconds, " % seconds
            return res[:-2]

        last_message_date = self.last_messages.get(tab.name)
        self.last_messages[tab.name] = datetime.now()
        if last_message_date:
            delta = datetime.now() - last_message_date
            if delta >= timedelta(0, self.config.get('delay', 900)):
                tab.add_message("%s passed…" % (format_timedelta(delta),), str_time='')


