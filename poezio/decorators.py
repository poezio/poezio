"""
Module containing various decorators
"""
from typing import Any, Callable, List, Optional

from poezio import common


class RefreshWrapper:
    def __init__(self):
        self.core = None

    def conditional(self, func: Callable) -> Callable:
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

    def always(self, func: Callable) -> Callable:
        """
        Decorator that refreshs the UI no matter what after the function
        """

        def wrap(*args, **kwargs):
            ret = func(*args, **kwargs)
            if self.core:
                self.core.refresh_window()
            return ret

        return wrap

    def update(self, func: Callable) -> Callable:
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


class CommandArgParser:
    """Modify the string argument of the function into a list of strings
    containing the right number of extracted arguments, or None if we don’t
    have enough.
    """

    @staticmethod
    def raw(func: Callable) -> Callable:
        """Just call the function with a single string, which is the original string
        untouched
        """

        def wrap(self, args, *a, **kw):
            return func(self, args, *a, **kw)

        return wrap

    @staticmethod
    def ignored(func: Callable) -> Callable:
        """
        Call the function without any argument
        """

        def wrap(self, args=None, *a, **kw):
            return func(self, *a, **kw)

        return wrap

    @staticmethod
    def quoted(mandatory: int,
               optional=0,
               defaults: Optional[List[Any]] = None,
               ignore_trailing_arguments=False):
        """The function receives a list with a number of arguments that is between
        the numbers `mandatory` and `optional`.

        If the string doesn’t contain at least `mandatory` arguments, we return
        None because the given arguments are invalid.

        If there are any remaining arguments after `mandatory` and `optional`
        arguments have been found (and “ignore_trailing_arguments" is not True),
        we append them to the last argument of the list.

        An argument is a string (with or without whitespaces) between two quotes
        ("), or a whitespace separated word (if not inside quotes).

        The argument `defaults` is a list of strings that are used when an
        optional argument is missing.  For example if we accept one optional
        argument and none is provided, but we have one value in the `defaults`
        list, we use that string inplace. The `defaults` list can only
        replace missing optional arguments, not mandatory ones. And it
        should not contain more than `mandatory` values. Also you cannot

        Example:
        This method needs at least one argument, and accepts up to 3
        arguments

        >> @command_args_parser.quoted(1, 2, ['default for first arg'], False)
        >> def f(args):
        >>     print(args)

        >> f('coucou les amis') # We have one mandatory and two optional
        ['coucou', 'les', 'amis']
        >> f('"coucou les amis" "PROUT PROUT"') # One mandator and only one optional,
                                                # no default for the second
        ['coucou les amis', 'PROUT PROUT']
        >> f('')                # Not enough args for mandatory number
        None
        >> f('"coucou les potes"') # One mandatory, and use the default value
                                   # for the first optional
        ['coucou les potes, 'default for first arg']
        >> f('"un et demi" deux trois quatre cinq six') # We have three trailing arguments
        ['un et demi', 'deux', 'trois quatre cinq six']

        """
        default_args_outer = defaults or []

        def first(func: Callable):
            def second(self, args: str, *a, **kw):
                default_args = default_args_outer
                if args and args.strip():
                    split_args = common.shell_split(args)
                else:
                    split_args = []
                if len(split_args) < mandatory:
                    return func(self, None, *a, **kw)
                res, split_args = split_args[:mandatory], split_args[
                    mandatory:]
                if optional == -1:
                    opt_args = split_args[:]
                else:
                    opt_args = split_args[:optional]

                if opt_args:
                    res += opt_args
                    split_args = split_args[len(opt_args):]
                    default_args = default_args[len(opt_args):]
                res += default_args
                if split_args and res and not ignore_trailing_arguments:
                    res[-1] += " " + " ".join(split_args)
                return func(self, res, *a, **kw)

            return second

        return first


command_args_parser = CommandArgParser()


def deny_anonymous(func: Callable) -> Callable:
    """Decorator to disable commands when using an anonymous account."""
    def wrap(self: 'RosterInfoTab', *args, **kwargs):
        if self.core.xmpp.anon:
            return self.core.information(
                'This command is not available for anonymous accounts.',
                'Info'
            )
        return func(self, *args, **kwargs)
    return wrap
