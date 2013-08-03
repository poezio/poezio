"""
Module containing various decorators
"""

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

refresh_wrapper = RefreshWrapper()
