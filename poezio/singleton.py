# Copyright 2010-2011 Florent Le Coz <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the zlib license. See the COPYING file.

"""
Defines a Singleton function that initialize an object
of the given class if it was never instantiated yet. Else, returns
the previously instantiated object.
This method is the only one that I can come up with that do not call
__init__() each time.
"""

instances = {}
def Singleton(cls, *args, **kwargs):
    if not cls in instances:
        instances[cls] = cls(*args, **kwargs)
    return instances[cls]
