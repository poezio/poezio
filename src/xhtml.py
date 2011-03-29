#!/usr/bin/env python3
#
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
Various methods to convert
shell colors to poezio colors,
xhtml code to shell colors,
poezio colors to xhtml code
"""

import re
import subprocess

shell_colors_re = re.compile(r'(\[(?:\d+;)*(?:\d+m))')

def shell_colors_to_poezio_colors(string):
    """
    'shell colors' means something like:

    Bonjour ^[[0;32msalut^[[0m

    The current understanding of this syntax is:
    n = 0: reset all attributes to defaults
    n >= 30 and n <= 37: set the foreground to n-30

    """
    def repl(matchobj):
        exp = matchobj.group(0)[2:-1]
        numbers = [int(nb) for nb in exp.split(';')]
        res = ''
        for num in numbers:
            if num == 0:
                res += r'\x19o'
            elif num >= 30 and num <= 37:
                res += r'\x19%s' % (num-30,)
        return res
    return shell_colors_re.sub(repl, string)

def xhtml_code_to_shell_colors(string):
    """
    Use a console browser to parse the xhtml and
    make it return a shell-colored string
    """
    process = subprocess.Popen(["elinks", "-dump", "-dump-color-mode", "2"], stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    result = process.communicate(input=string.encode('utf-8'))[0]
    return result.decode('utf-8').strip()

if __name__ == '__main__':
    print(xhtml_code_to_shell_colors("""
  <html xmlns='http://jabber.org/protocol/xhtml-im'>
    <body xmlns='http://www.w3.org/1999/xhtml'>
      <p style='font-size:large'>
        <em>Wow</em>, I&apos;m <span style='color:green'>green</span>
        with <strong>envy</strong>!
      </p>
    </body>
  </html>
"""))
