# -*- coding: utf-8 -*-

# Copyright 2010, Florent Le Coz <louizatakk@fedoraproject.org>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation version 3 of the License.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# various useful functions

import base64
import os
import mimetypes
import hashlib

def get_base64_from_file(path):
    if not os.path.isfile(path):
        return (None, None, "File does not exist")
    size = os.path.getsize(path)
    if size > 16384:
        return (None, None,"File is too big")
    fd = open(path, 'rb')
    data = fd.read()
    encoded = base64.encodestring(data)
    sha1 = hashlib.sha1(data).hexdigest()
    mime_type = mimetypes.guess_type(path)[0]
    return (encoded, mime_type, sha1)
