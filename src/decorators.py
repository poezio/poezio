"""
Module containing various decorators
"""

from functools import partial

class RefreshWrapper(object):
    def __init__(self):
        self.core = None

    def conditional(self, func):
        """
        Decorator to refresh the UI if the wrapped function
        returns True
        """
        def wrap(*args, **kwargs):
            ret = func(*args, **kwargs)
            if self.core and ret:
                self.core.refresh_window()
            return ret
        return wrap

    def always(self, func):
        """
        Decorator that refreshs the UI no matter what after the function
        """
        def wrap(*args, **kwargs):
            ret = func(*args, **kwargs)
            if self.core:
                self.core.refresh_window()
            return ret
        return wrap

    def update(self, funct):
        """
        Decorator that only updates the screen
        """
        def wrap(*args, **kwargs):
            ret = func(*args, **kwargs)
            if self.core:
                self.core.doupdate()
            return ret
        return wrap

def __completion(quoted, func):
    class Completion(object):
        quoted = quoted
        def __new__(cls, *args, **kwargs):
            return func(*args, **kwargs)
    return Completion


completion_quotes = partial(__completion, True)
completion_raw = partial(__completion, False)
refresh_wrapper = RefreshWrapper()
