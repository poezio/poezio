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

from datetime import datetime
from typing import Callable, Union


class DelayedEvent:
    """
    A TimedEvent, but with the date calculated from now + a delay in seconds.
    Use it if you want an event to happen in, e.g. 6 seconds.
    """

    def __init__(self, delay: Union[int, float], callback: Callable,
                 *args) -> None:
        """
        Create a new DelayedEvent.

        :param int delay: The number of seconds.
        :param function callback: The handler that will be executed.
        :param args: Optional arguments passed to the handler.
        """
        self.callback = callback
        self.args = args
        self.delay = delay
        # An asyncio handler, as returned by call_later() or call_at()
        self.handler = None


class TimedEvent(DelayedEvent):
    """
    An event with a callback that is called when the specified time is passed.

    The callback and its arguments should be passed as the lasts arguments.
    """

    def __init__(self, date: datetime, callback: Callable, *args) -> None:
        """
        Create a new timed event.

        :param datetime.datetime date: Time at which the callback must be run.
        :param function callback: The handler that will be executed.
        :param args: Optional arguments passed to the handler.
        """
        delta = date - datetime.now()
        delay = delta.total_seconds()
        DelayedEvent.__init__(self, delay, callback, *args)
