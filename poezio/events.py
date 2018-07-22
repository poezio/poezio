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

from typing import Callable, Dict, List


class EventHandler:
    """
    A class keeping a list of possible events that are triggered
    by poezio. You (a plugin for example) can add an event handler
    associated with an event name, and whenever that event is triggered,
    the callback is called.
    """

    def __init__(self):
        self.events = {
            'highlight': [],
            'muc_say': [],
            'muc_say_after': [],
            'conversation_say': [],
            'conversation_say_after': [],
            'private_say': [],
            'private_say_after': [],
            'conversation_msg': [],
            'private_msg': [],
            'muc_msg': [],
            'conversation_chatstate': [],
            'muc_chatstate': [],
            'private_chatstate': [],
            'normal_presence': [],
            'muc_presence': [],
            'muc_join': [],
            'joining_muc': [],
            'changing_nick': [],
            'muc_kick': [],
            'muc_nickchange': [],
            'muc_ban': [],
            'send_normal_presence': [],
            'ignored_private': [],
            'tab_change': [],
        }  # type: Dict[str, List[Callable]]

    def add_event_handler(self, name: str, callback: Callable,
                          position=0) -> bool:
        """
        Add a callback to a given event.
        Note that if that event name doesn’t exist, it just returns False.
        If it was successfully added, it returns True
        position: 0 means insert at the beginning, -1 means end
        """
        if name not in self.events:
            return False

        callbacks = self.events[name]
        if position >= 0:
            callbacks.insert(position, callback)
        else:
            callbacks.append(callback)

        return True

    def trigger(self, name: str, *args, **kwargs):
        """
        Call all the callbacks associated to the given event name.
        """
        callbacks = self.events.get(name, None)
        if callbacks is None:
            return
        for callback in callbacks:
            callback(*args, **kwargs)

    def del_event_handler(self, name: str, callback: Callable):
        """
        Remove the callback from the list of callbacks of the given event
        """
        if not name:
            for callbacks in self.events.values():
                while callback in callbacks:
                    callbacks.remove(callback)
        else:
            callbacks = self.events[name]
            if callback in callbacks:
                callbacks.remove(callback)
