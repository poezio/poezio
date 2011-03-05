# Copyright 2010-2011 Le Coz Florent <louiz@louiz.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

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
