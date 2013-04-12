Plugins
=======

Starting from the 0.7.5 version, poezio supports plugins.
Here is a quick howto and a plugin index.


Setting up plugins
------------------

Poezio seeks the plugins in the :file:`~/.local/share/poezio/plugins/` dir (more
generally, the :file:`$XDG_DATA_HOME/poezio/plugins/` dir), but that can be changed
by setting the :term:`plugins_dir` option to the directory where you want to
put your plugins.

This means that if you want to use a plugin, you have to copy it (the .py file or the directory) into :term:`plugins_dir`.


Plugin autoload
---------------

Use the :term:`plugins_autoload` optionto select which plugins should be
loaded on startup. The value is a list of plugin names separated by colons,
e.g.

.. code-block:: ini

    plugins_autoload = gpg:tell:exec

Plugin configuration
--------------------

Most plugins will manage their configuration internally, and you do not (and
should not) have to edit it, but some (e.g. mpd_client or gpg) require manual
editing (the :term:`/set` command can be used, but it is not pleasant to set
multiple values with it).

The plugin configuration directory is located in :file:`~/.config/poezio/plugins/`
(or :file:`$XDG_CONFIG_HOME/poezio/plugins/`) and the file related to a specific
plugin is named :file:`plugin_name.cfg`. The configuration options should usually be
inside a section named after the plugin (sections are delimited with ``[]``).

.. code-block:: ini

    [plugin_name]
    key = value
    other_key = other_value

Plugin index
------------

.. glossary::

    Admin
        :ref:`Documentation <admin-plugin>`

        Creates convenient aliases for MUC administration.

    Alias

        Allows you to create your own aliases.

    Amsg

        Allows a message to be broadcasted on all the rooms your are in.
        Caution: do not overuse.

    Day Change

        Logs the day change inside the buffers, to keep track of the days when
        backlogging.

    Display corrections

        Lists old versions of a corrected message.

    Exec

        Runs a system command an optionally sends the output as a message.

    Figlet

        Ascii-art writing (requires the ``figlet`` package on your system).

    GPG

        Allows encrypted exchanges and presence signing using GnuPG.

    IQ Show

        Shows the received IQs, for debugging purposes.

    Link

        Opens links in a web browser, locally or remotely using a FIFO and SSH.

    MPD Client

        Sends the current song (and optionally the progress inside the song) to
        the current (chat) tab.

    OTR

        Allows encrypted and deniable exchanges using OTR.

    PacoKick

        Kicks a random user in the room.

    Ping

        Sends a ping probe to an entity (XEP-0199)

    Quote

        Adds a /quote command to quote a message at HH:MM:SS and put it in the
        input (to prevent painful copy/pastes).

    Rainbow

        Sends your messages in rainbow colors using XHTML-IM.

    Reminder

        Reminds you to do something every now and then.

    Screen Detach

        Changes your status to _away_ if the screen poezio is in is detached.

    Simple notify

        Sends a notification with a command of your choice on (non-MUC) messages.

    Status

        Adds convenient aliases to /status (/away, etc).

    Tell

        Tells a message to a nick when he connects to a MUC.

    Uptime

        Gets the uptime of a XMPP server or a component.

    Replace

        Replace some patterns in your messages.

    Time Marker

        Display the time between two messages.

