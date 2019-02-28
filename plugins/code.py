"""
This plugin adds a :term:`/code` command, to send syntax highlighted snippets
of code using pygments and XHTML-IM (XEP-0071).

Install
-------

Either use your distribution tools to install python3-pygments or equivalent,
or run:

.. code-block:: shell

    pip install --user pygments

Usage
-----

.. glossary::

    /code <language> <snippet>

        Run this command to send the <snippet> of code, syntax highlighted
        using pygments’s <language> lexer.
"""

from poezio.plugin import BasePlugin

from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter  #pylint: disable=no-name-in-module
FORMATTER = HtmlFormatter(nowrap=True, noclasses=True)


class Plugin(BasePlugin):
    def init(self):
        self.api.add_command(
            'code',
            self.command_code,
            usage='<language> <code>',
            short='Sends syntax-highlighted code',
            help='Sends syntax-highlighted code in the current tab')

    def command_code(self, args):
        language, code = args.split(None, 1)
        lexer = get_lexer_by_name(language)
        tab = self.api.current_tab()
        code = highlight(code, lexer, FORMATTER)
        tab.command_xhtml('<pre><code class="language-%s">%s</code></pre>' % (language, code.rstrip('\n')))
