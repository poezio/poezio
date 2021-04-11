"""
Module containing various decorators
"""

from __future__ import annotations
from asyncio import iscoroutinefunction

from typing import (
    cast,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    TYPE_CHECKING,
)

from poezio import common
if TYPE_CHECKING:
    from poezio.core.core import Core


T = TypeVar('T', bound=Callable[..., Any])


BeforeFunc = Optional[Callable[[List[Any], Dict[str, Any]], Any]]
AfterFunc = Optional[Callable[[Any, List[Any], Dict[str, Any]], Any]]


def wrap_generic(func: Callable, before: BeforeFunc = None, after: AfterFunc = None):
    """
    Generic wrapper which can both wrap coroutines and normal functions.
    """
    def wrap(*args, **kwargs):
        args = list(args)
        if before is not None:
            result = before(args, kwargs)
            if result is not None:
                return result
        result = func(*args, **kwargs)
        if after is not None:
            result = after(result, args, kwargs)
        return result

    async def awrap(*args, **kwargs):
        args = list(args)
        if before is not None:
            result = before(args, kwargs)
            if result is not None:
                return result
        result = await func(*args, **kwargs)
        if after is not None:
            result = after(result, args, kwargs)
        return result
    if iscoroutinefunction(func):
        return awrap
    return wrap


class RefreshWrapper:
    core: Optional[Core]

    def __init__(self) -> None:
        self.core = None

    def conditional(self, func: T) -> T:
        """
        Decorator to refresh the UI if the wrapped function
        returns True
        """
        def after(result: Any, args, kwargs) -> Any:
            if self.core is not None and result:
                self.core.refresh_window()  # pylint: disable=no-member
            return result

        wrap = wrap_generic(func, after=after)

        return cast(T, wrap)

    def always(self, func: T) -> T:
        """
        Decorator that refreshs the UI no matter what after the function
        """
        def after(result: Any, args, kwargs) -> Any:
            if self.core is not None:
                self.core.refresh_window()  # pylint: disable=no-member
            return result

        wrap = wrap_generic(func, after=after)
        return cast(T, wrap)

    def update(self, func: T) -> T:
        """
        Decorator that only updates the screen
        """

        def after(result: Any, args, kwargs) -> Any:
            if self.core is not None:
                self.core.doupdate()  # pylint: disable=no-member
            return result
        wrap = wrap_generic(func, after=after)
        return cast(T, wrap)


refresh_wrapper = RefreshWrapper()


class CommandArgParser:
    """Modify the string argument of the function into a list of strings
    containing the right number of extracted arguments, or None if we don’t
    have enough.
    """

    @staticmethod
    def raw(func: T) -> T:
        """Just call the function with a single string, which is the original string
        untouched
        """
        return func

    @staticmethod
    def ignored(func: T) -> T:
        """
        Call the function without textual arguments
        """
        def before(args: List[Any], kwargs: Dict[Any, Any]) -> None:
            if len(args) >= 2:
                del args[1]

        wrap = wrap_generic(func, before=before)
        return cast(T, wrap)

    @staticmethod
    def quoted(mandatory: int,
               optional: int = 0,
               defaults: Optional[List[Any]] = None,
               ignore_trailing_arguments: bool = False) -> Callable[[T], T]:
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

        def first(func: T) -> T:
            def before(args: List, kwargs: Dict[str, Any]) -> Any:
                default_args = default_args_outer
                cmdargs = args[1]
                if cmdargs and cmdargs.strip():
                    split_args = common.shell_split(cmdargs)
                else:
                    split_args = []
                if len(split_args) < mandatory:
                    args[1] = None
                    return
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
                args[1] = res
                return
            wrap = wrap_generic(func, before=before)
            return cast(T, wrap)
        return first

command_args_parser = CommandArgParser()


def deny_anonymous(func: T) -> T:
    """Decorator to disable commands when using an anonymous account."""

    def before(args: Any, kwargs: Any) -> Any:
        core = args[0].core
        if core.xmpp.anon:
            core.information(
                'This command is not available for anonymous accounts.',
                'Info'
            )
            return False
    wrap = wrap_generic(func, before=before)
    return cast(T, wrap)
