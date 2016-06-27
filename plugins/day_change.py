"""
This plugin adds a message at 00:00 in each of your chat tabs saying that the
date has changed.

"""

from gettext import gettext as _
from poezio.plugin import BasePlugin
import datetime
from poezio import tabs
from poezio import timed_events

class Plugin(BasePlugin):
    def init(self):
        self.schedule_event()

    def cleanup(self):
        self.api.remove_timed_event(self.next_event)

    def schedule_event(self):
        day_change = datetime.datetime.combine(datetime.date.today(), datetime.time())
        day_change += datetime.timedelta(1)
        self.next_event = timed_events.TimedEvent(day_change, self.day_change)
        self.api.add_timed_event(self.next_event)

    def day_change(self):
        msg = _("Day changed to %s") % (datetime.date.today().isoformat())

        for tab in self.core.tabs:
            if isinstance(tab, tabs.ChatTab):
                tab.add_message(msg)

        self.core.refresh_window()
        self.schedule_event()
