#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Defines the EventHandler class
"""

import logging
log = logging.getLogger(__name__)

class EventHandler(object):
    """
    A class keeping a list of possible events that are triggered
    by poezio. You (a plugin for example) can add an event handler
    associated with an event name, and whenever that event is triggered,
    the callback is called
    """
    def __init__(self):
        self.events = {
            # when you are highlighted in a muc tab
            'highlight': [],
            'muc_say': [],
            'conversation_say': [],
            'private_say': [],
            'conversation_msg': [],
            'private_msg': [],
            'muc_msg': [],
            }

    def add_event_handler(self, name, callback, position=0):
        """
        Add a callback to a given event.
        Note that if that event name doesn’t exist, it just returns False.
        If it was successfully added, it returns True
        position: 0 means insert a the beginning, -1 means end
        """
        if name not in self.events:
            return False

        if position >= 0:
            self.events[name].insert(position, callback)
        else:
            self.events[name].append(callback)

        return True

    def trigger(self, name, *args, **kwargs):
        """
        Call all the callbacks associated to the given event name
        """
        callbacks = self.events[name]
        for callback in callbacks:
            callback(*args, **kwargs)

    def del_event_handler(self, name, callback):
        """
        Remove the callback from the list of callbacks of the given event
        """
        if not name:
            for event in self.events:
                while callback in self.events[event]:
                    self.events[event].remove(callback)
            return True
        else:
            if callback in self.events[name]:
                self.events[name].remove(callback)

