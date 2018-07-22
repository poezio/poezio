# Copyright 2018 Emmanuel Gil Peyrot <linkmauve@linkmauve.fr>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.
"""
Implements the XDG base directory specification.

https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
"""

from pathlib import Path
from os import environ
from typing import Dict

# $HOME has already been checked to not be None in test_env().
DEFAULT_PATHS = {
    'XDG_CONFIG_HOME': Path.home() / '.config',
    'XDG_DATA_HOME': Path.home() / '.local' / 'share',
    'XDG_CACHE_HOME': Path.home() / '.cache',
}  # type: Dict[str, Path]


def _get_directory(variable: str) -> Path:
    """
    returns the default configuration directory path
    """
    if variable not in DEFAULT_PATHS:
        raise ValueError('Invalid XDG basedir variable')
    xdg = environ.get(variable)
    if xdg is not None:
        xdg_path = Path(xdg)
        if xdg_path.is_absolute():
            return xdg_path / 'poezio'
    return DEFAULT_PATHS[variable] / 'poezio'


CONFIG_HOME = _get_directory('XDG_CONFIG_HOME')
DATA_HOME = _get_directory('XDG_DATA_HOME')
CACHE_HOME = _get_directory('XDG_CACHE_HOME')
