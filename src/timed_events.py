# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
To use these, just use core.add_timed_event(event)
where event is an instance of one of these classes
"""

import logging

log = logging.getLogger(__name__)

import datetime

class TimedEvent(object):
    """
    An event with a callback that is called when the specified time is passed
    Note that these events can NOT be used for very small delay or a very
    precise date, since the check for events is done once per second, as
    a maximum.
    The callback and its arguments should be passed as the lasts arguments.
    """
    def __init__(self, date, callback, *args):
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
        returns True if the callback should be called
        """
        if self.next_call_date < current_date:
            return True
        else:
            return False

    def change_date(self, date):
        """
        Simply change the date of the event
        """
        self.next_call_date = date

    def add_delay(self, delay):
        """
        Add a delay (in seconds) to the date
        """
        self.next_call_date += datetime.timedelta(seconds=delay)

class DelayedEvent(TimedEvent):
    """
    The date is calculated from now + a delay in seconds
    Use it if you want an event to happen in, e.g. 6 seconds
    """
    def __init__(self, delay, callback, *args):
        date = datetime.datetime.now() + datetime.timedelta(seconds=delay)
        TimedEvent.__init__(self, date, callback, *args)

