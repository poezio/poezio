#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.
"""
Defines the EventHandler class.
The list of available events is here:
http://poezio.eu/doc/en/plugins.html#_poezio_events
"""

from collections import OrderedDict
from typing import Callable, Dict, List


class EventHandler:
    """
    A class keeping a list of possible events that are triggered
    by poezio. You (a plugin for example) can add an event handler
    associated with an event name, and whenever that event is triggered,
    the callback is called.
    """

    def __init__(self):
        events = [
            'highlight',
            'muc_say',
            'muc_say_after',
            'conversation_say',
            'conversation_say_after',
            'private_say',
            'private_say_after',
            'conversation_msg',
            'private_msg',
            'muc_msg',
            'conversation_chatstate',
            'muc_chatstate',
            'private_chatstate',
            'normal_presence',
            'muc_presence',
            'muc_join',
            'joining_muc',
            'changing_nick',
            'muc_kick',
            'muc_nickchange',
            'muc_ban',
            'send_normal_presence',
            'ignored_private',
            'tab_change',
        ]
        self.events = {}  # type: Dict[str, OrderedDict[int, List[Callable]]]
        for event in events:
            self.events[event] = OrderedDict()

    def add_event_handler(self, name: str, callback: Callable,
                          priority: int = 50) -> bool:
        """
        Add a callback to a given event.
        Note that if that event name doesn’t exist, it just returns False.
        If it was successfully added, it returns True
        priority is a integer between 0 and 100. 0 is the highest priority and
        will be called first. 100 is the lowest.
        """

        if name not in self.events:
            return False

        callbacks = self.events[name]

        # Clamp priority
        priority = max(0, min(priority, 100))

        entry = callbacks.setdefault(priority, [])
        entry.append(callback)

        return True

    def trigger(self, name: str, *args, **kwargs):
        """
        Call all the callbacks associated to the given event name.
        """
        callbacks = self.events.get(name, None)
        if callbacks is None:
            return
        for priority in callbacks.values():
            for callback in priority:
                callback(*args, **kwargs)

    def del_event_handler(self, name: str, callback: Callable):
        """
        Remove the callback from the list of callbacks of the given event
        """
        if not name:
            for callbacks in self.events.values():
                for priority in callbacks.values():
                    for entry in priority[:]:
                        if entry == callback:
                            priority.remove(callback)
        else:
            callbacks = self.events[name]
            for priority in callbacks.values():
                for entry in priority[:]:
                    if entry == callback:
                        priority.remove(callback)
