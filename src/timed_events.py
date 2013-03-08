# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Timed events are the standard way to schedule events for later in poezio.

Once created, they must be added to the list of checked events with
:py:func:`Core.add_timed_event` (within poezio) or with
:py:func:`.PluginAPI.add_timed_event` (within a plugin).
"""

import logging

log = logging.getLogger(__name__)

import datetime

class TimedEvent(object):
    """
    An event with a callback that is called when the specified time is passed.

    Note that these events can NOT be used for very small delay or a very
    precise date, since the check for events is done once per second, as
    a maximum.

    The callback and its arguments should be passed as the lasts arguments.
    """
    def __init__(self, date, callback, *args):
        """
        Create a new timed event.

        :param datetime.datetime date: Time at which the callback must be run.
        :param function callback: The handler that will be executed.
        :param \*args: Optional arguments passed to the handler.
        """
        self._callback = callback
        self.args = args
        self.repetive = False
        self.next_call_date = date

    def __call__(self):
        """
        the call should return False if this event should be remove from
        the events list.
        If it’s true, the date should be updated beforehand to a later date,
        or else it will be called every second
        """
        self._callback(*self.args)
        return self.repetive

    def has_timed_out(self, current_date):
        """
        Check if the event has timed out.

        :param datetime.datetime current_date: The current date.
        :returns: True if the callback should be called
        :rtype: bool
        """
        if self.next_call_date < current_date:
            return True
        else:
            return False

    def change_date(self, date):
        """
        Simply change the date of the event.

        :param datetime.datetime date: Next date.
        """
        self.next_call_date = date

    def add_delay(self, delay):
        """
        Add a delay (in seconds) to the date.

        :param int delay: The delay to add.
        """
        self.next_call_date += datetime.timedelta(seconds=delay)

class DelayedEvent(TimedEvent):
    """
    A TimedEvent, but with the date calculated from now + a delay in seconds.
    Use it if you want an event to happen in, e.g. 6 seconds.
    """
    def __init__(self, delay, callback, *args):
        """
        Create a new DelayedEvent.

        :param int delay: The number of seconds.
        :param function callback: The handler that will be executed.
        :param \*args: Optional arguments passed to the handler.
        """
        date = datetime.datetime.now() + datetime.timedelta(seconds=delay)
        TimedEvent.__init__(self, date, callback, *args)

