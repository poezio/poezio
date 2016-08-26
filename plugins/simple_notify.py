"""
This plugin lets you execute a command, to notify you from new important
messages.

Installation and configuration
------------------------------

You need to create a plugin configuration file. Create a file named :file:`simple_notify.cfg`
into your plugins configuration directory (:file:`~/.config/poezio/plugins` by
default), and fill it like this:

First example:

.. code-block:: ini

    [simple_notify]
    command = notify-send -i /path/to/poezio/data/poezio_80.png "New message from %(from)s" "%(body)s"

Second example:

.. code-block:: ini

    [simple_notify]
    command = echo \\<%(from)s\\> %(body)s >> some.fifo
    delay = 3
    after_command = echo >> some.fifo

You can put any command, instead of these ones. You can also use the
special keywords ``%(from)s`` and ``%(body)s`` that will be replaced
directly in the command line by the author of the message, and the body.

The first example shown above will display something like this:

.. figure:: ../images/simple_notify_example.png
    :alt: Simple notify example

The second example will first write the author and the message in a
fifo, that fifo can locally be read by some other program (was tested
with the xmobar PipeReader command, which displays what is read from a
fifo into a status bar. Be careful, you have two different fifos in
that case, don’t get confused). The :term:`delay` and :term:`after_command` options
are used to erase/delete/kill the notification after a certain
delay.  In our example it is used to display an empty message in our
xmobar, erasing the notification after 3 seconds.

Third example:

.. code-block:: ini

    [simple_notify]
    command = notify-send -i /path/to/poezio/data/poezio_80.png "New message from %(from)s" "%(body)s"
    muc_too = true
    muc_list = someroom@conference.jabber.org:someotherroom@conference.jabber.org

If present and set to ``True``, the ``muc_too`` option will also trigger a
notification when a new message arrives on a Multi User Chat you've joined.

If present and set to a colon separated list of muc JIDs, muc_list together 
with muc_too = true will only notify when a new message arrives on a Multi 
User Chat, you've joined if it is present on the list.

.. note:: If you set the :term:`exec_remote` option to ``true`` into the
    main configuration file, the command will be executed remotely
    (as explained in the :ref:`link-plugin` plugin help).

Options defined
---------------

.. glossary::
    :sorted:

    command
        The command to execute (with special keywords ``%{from}s`` and ``${body}s``)

    delay
        Delay after which :term:`after_command` must be executed.

    after_command
        Command to run after :term:`delay`. You probably want to clean up things.

    muc_too
        Boolean indicating whether new messages in Multi User Chat rooms should
        trigger a notification or not.

"""

from poezio.plugin import BasePlugin
from poezio.xhtml import get_body_from_message_stanza
from poezio.timed_events import DelayedEvent
import shlex
from poezio import common


class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('private_msg', self.on_private_msg)
        self.api.add_event_handler('conversation_msg', self.on_conversation_msg)
        if self.config.get('muc_too', False):
            self.api.add_event_handler('muc_msg', self.on_muc_msg)
        self.api.add_event_handler('highlight', self.on_highlight)

    def on_private_msg(self, message, tab):
        fro = message['from']
        self.do_notify(message, fro)

    def on_highlight(self, message, tab):
        whitelist = self.config.get('muc_list', '').split(':')
        # prevents double notifications
        if message['from'].bare in whitelist:
            return
        fro = message['from'].resource
        self.do_notify(message, fro)

    def on_conversation_msg(self, message, tab):
        fro = message['from'].bare
        self.do_notify(message, fro)

    def on_muc_msg(self, message, tab):
        # Dont notify if message is from yourself
        if message['from'].resource == tab.own_nick:
            return

        fro = message['from'].full
        muc = message['from'].bare
        whitelist = self.config.get('muc_list', '').split(':')

        # Prevent old messages to be notified
        # find_delayed_tag(message) returns (True, the datetime) or
        # (False, None)
        if not common.find_delayed_tag(message)[0]:
            # Only notify if whitelist is empty or muc in whitelist
            if whitelist == [''] or muc in whitelist:
                self.do_notify(message, fro)

    def do_notify(self, message, fro):
        body = get_body_from_message_stanza(message, use_xhtml=False)
        if not body:
            return
        command_str = self.config.get('command', '').strip()
        if not command_str:
            self.api.information('No notification command was provided in the configuration file', 'Warning')
            return
        command = [arg % {'body': body.replace('\n', ' '), 'from': fro} for arg in shlex.split(command_str)]
        self.core.exec_command(command)
        after_command_str = self.config.get('after_command', '').strip()
        if not after_command_str:
            return
        after_command = [arg % {'body': body.replace('\n', ' '), 'from': fro} for arg in shlex.split(after_command_str)]
        delayed_event = DelayedEvent(self.config.get('delay', 1), self.core.exec_command, after_command)
        self.api.add_timed_event(delayed_event)
