"""
Opens links in a browser.

Installation
------------

First use case: local use
~~~~~~~~~~~~~~~~~~~~~~~~~
If you use poezio on your workstation, this is for you.
You only have to load the plugin: ::

    /load link

Second use case: remote use
~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you use poezio through SSH, this is for you.

.. note:: Small explanation: Poezio will create a `Unix FIFO`_ and send the commands in,
            and you will have to run a dæmon locally with ssh, to get those commands.

First, set the :term:`exec_remote` option in the config file to ``true``. Then select
the directory you want to put the fifo in (default is the current
directory, :file:`./`), the :file:`poezio.fifo` file will be created there.

After that, load the plugin: ::

    /load link

And open a link with :term:`/link` (as described below), this will create the FIFO.

You need to grab poezio’s sources on your client computer, or at least the `daemon.py`_
file.

Finally, on your client computer, run the ssh command:

.. code-block:: bash

    ssh toto@example.org "cat ~/poezio/poezio.fifo" | python3 daemon.py

Usage
-----

.. glossary::

    /link
        **Usage:** ``/link [range]``

        This plugin adds a :term:`/link` command that will open the links in ``firefox``. If
        you want to use another browser, you can use the :term:`/set` command  to change the
        :term:`browser` option.


        :term:`/link` without argument will open the last link found
        in the current tab, if any is found. An optional range
        argument can be given, to select one or more links to
        open. Examples:
        ``/link 1`` is equivalent to ``/link``
        ``/link 3`` will open the third link found in the current tab,
        starting from the bottom.
        ``/link 1:5`` will open the last five links in the current tab
        ``/link :2`` will open the last two links

Options
-------

:term:`exec_remote`

    To execute the command on your client

.. glossary::

    browser
        Set the default browser started by the plugin

.. _Unix FIFO: https://en.wikipedia.org/wiki/Named_pipe
.. _daemon.py: http://dev.louiz.org/projects/poezio/repository/revisions/master/raw/src/daemon.py

"""
import re

from plugin import BasePlugin
from xhtml import clean_text
import common
import tabs

url_pattern = re.compile(r'\b(http[s]?://(?:\S+))\b', re.I|re.U)

class Plugin(BasePlugin):
    def init(self):
        for _class in (tabs.MucTab, tabs.PrivateTab, tabs.ConversationTab):
            self.api.add_tab_command(_class, 'link', self.command_link,
                    usage='[num]',
                    help='Opens the last link from the conversation into a browser.\nIf [num] is given, then it will open the num-th link displayed.',
                    short='Open links into a browser')

    def find_link(self, nb):
        messages = self.api.get_conversation_messages()
        if not messages:
            return None
        for message in messages[::-1]:
            matches = url_pattern.findall(clean_text(message.txt))
            if matches:
                for url in matches[::-1]:
                    if nb == 1:
                        return url
                    else:
                        nb -= 1
        return None

    def command_link(self, args):
        args = common.shell_split(args)
        if len(args) == 1:
            if args[0].find(':') == -1:
                try:
                    start = int(args[0])
                    end = start
                except ValueError:
                    return self.api.run_command('/help link')
            else:
                start, end = args[0].split(':', 1)
                if start == '':
                    start = 1
                try:
                    start = int(start)
                    end = int(end)
                except ValueError:
                    return self.api.information('Invalid range: %s' % (args[0]), 'Error')
        else:
            start = 1
            end = 1
        for nb in range(start, end+1):
            link = self.find_link(nb)
            if not link:
                return self.api.information('No URL found.', 'Warning')
            self.core.exec_command([self.config.get('browser', 'firefox'), link])

    def cleanup(self):
        del self.config
