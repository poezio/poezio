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


class TimedEvent(object):
    """
    An event with a callback that is called when the specified time is passed
    Note that these events can NOT be used for very small delay or a very
    precise date, since the check for events is done once per second, as
    a maximum
    """
    def __init__(self, callback, *args, **kwargs):
        self._callback = callback
        self.args = args

