.. _plugins-doc:

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

By default, poezio will also seek the plugins in :file:`../plugins`, in the source
directory, in order to always load the latest versions. You should put a plugin
in :file:`$XDG_DATA_HOME/poezio/plugins` only if you have a custom version (that
will override the one in :file:`../plugins`), or if it is a plugin you made.


Plugin autoload
---------------

Use the :term:`plugins_autoload` option to select which plugins should be
loaded on startup. The value is a list of plugin names separated by colons,
e.g.

.. code-block:: ini

    plugins_autoload = tell:exec

Manual plugin load
------------------

Plugins can of course be loaded with the command :term:`/load` and unloaded
with the command :term:`/unload`.

.. _plugin-configuration:

Plugin configuration
--------------------

Most plugins will manage their configuration internally, and you do not (and
should not) have to edit it, but some (e.g. mpd_client) require manual
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
    :sorted:

    Admin
        :ref:`Documentation <admin-plugin>`

        Creates convenient aliases for chatroom administration.

    Alias
        :ref:`Documentation <alias-plugin>`

        Allows you to create your own aliases.

    Amsg
        :ref:`Documentation <amsg-plugin>`

        Allows a message to be broadcasted on all the rooms your are in.
        Caution: do not overuse.

    Close all
        :ref:`Documentation <closeall-plugin>`

        Close all tabs except chatrooms and the contact list.

    CSI
        :ref:`Documentation <csi-plugin>`

        Set the client state indication manually.

    Cyber
        :ref:`Documentation <cyber-plugin>`

        Add a cybertouch to your messages.

    Day Change
        :ref:`Documentation <daychange-plugin>`

        Logs the day change inside the buffers, to keep track of the days when
        backlogging.

    Display corrections
        :ref:`Documentation <displaycorrections-plugin>`

        Lists old versions of a corrected message.

    Embed
        :ref:`Documentation <embed-plugin>`

        Send an URL annotating it as embedded.

    Exec
        :ref:`Documentation <exec-plugin>`

        Runs a system command an optionally sends the output as a message.

    Figlet
        :ref:`Documentation <figlet-plugin>`

        Ascii-art writing (requires the ``figlet`` package on your system).

    IQ Show
        :ref:`Documentation <iqshow-plugin>`

        Shows the received IQs, for debugging purposes.

    Link
        :ref:`Documentation <link-plugin>`

        Opens links in a web browser, locally or remotely using a FIFO and SSH.

    MPD Client
        :ref:`Documentation <mpdclient-plugin>`

        Sends the current song (and optionally the progress inside the song) to
        the current (chat) tab.

    OTR
        :ref:`Documentation <otr-plugin>`

        Allows encrypted and deniable exchanges using OTR.

    PacoKick
        :ref:`Documentation <pacokick-plugin>`

        Kicks a random user in the room.

    Ping
        :ref:`Documentation <ping-plugin>`

        Sends a ping probe to an entity (XEP-0199)

    Quote
        :ref:`Documentation <quote-plugin>`

        Adds a /quote command to quote a message at HH:MM:SS and put it in the
        input (to prevent painful copy/pastes).

    Rainbow
        :ref:`Documentation <rainbow-plugin>`

        Sends your messages in rainbow colors using XHTML-IM.

    Reminder
        :ref:`Documentation <reminder-plugin>`

        Reminds you to do something every now and then.

    Screen Detach
        :ref:`Documentation <screendetach-plugin>`

        Changes your status to **away** if the screen (or tmux) poezio is in
        gets detached.

    Send Delayed
        :ref:`Documentation <senddelayed-plugin>`

        Program the sending of futur messages.

    Simple notify
        :ref:`Documentation <simplenotify-plugin>`

        Sends a notification with a command of your choice on (non-chatroom)
        messages.

    Spam
        :ref:`Documentation <spam-plugin>`

        Adds a subtle little advertising in your messages.

    Status
        :ref:`Documentation <status-plugin>`

        Adds convenient aliases to /status (/away, etc).

    Tell
        :ref:`Documentation <tell-plugin>`

        Sends a message to a nick when he connects to a chatroom.

    Uptime
        :ref:`Documentation <uptime-plugin>`

        Gets the uptime of a XMPP server or a component.

    Regex Admin
        :ref:`Documentation <regex-admin-plugin>`

        Add regex-based kick and ban commands.

    Replace
        :ref:`Documentation <replace-plugin>`

        Replace some patterns in your messages.

    Time Marker
        :ref:`Documentation <timemarker-plugin>`

        Display the time between two messages.

    Reorder
        :ref:`Documentation <reorder-plugin>`

        Reorder the tabs according to a static layout.

    Revstr
        :ref:`Documentation <revstr-plugin>`

        Reverse everything you say.

    Pipe Command
        :ref:`Documentation <pipecmd-plugin>`

        Send commands to poezio through a named pipe.

    Shuffle
        :ref:`Documentation <shuffle-plugin>`

        Shuffle everything you say.

    Double
        :ref:`Documentation <double-plugin>`

        Double the first word of each sentence.

    PointPoint
        :ref:`Documention <pointpoint-plugin>`

        Insert dots in your messages.

    Autocorrect
        :ref:`Documentation <autocorrect-plugin>`

        Add new ways to correct messages.

    IRC
        :ref:`Documentation <irc-plugin>`

        Manage IRC gateways with biboumi more easily

    Title change
        :ref:`Documentation <changetitle-plugin>`

        Change the title of the terminal according to the name
        of the current tab.

    Marquee
        :ref:`Documentation <marquee-plugin>`

        Reproduce the behavior of the ``<marquee/>`` html tag.

    Server Part
        :ref:`Documentation <serverpart-plugin>`

        Add a ``/server_part`` command.

    Dice
        :ref:`Documentation <dice-plugin>`

        Roll one or several dice using message corrections.

    Disco
        :ref:`Documentation <disco-plugin>`

        Add a ``/disco`` command to display the disco#info of a JID.

    vCard
        :ref:`Documentation <vcard-plugin>`

        Add a ``/vcard`` command to retrieve and display a vCard.

    Upload
        :ref:`Documentation <upload-plugin>`

        Add an ``/upload`` command to upload a file.

.. toctree::
    :hidden:

    admin
    alias
    amsg
    day_change
    display_corrections
    embed
    exec
    figlet
    link
    mpd_client
    otr
    pacokick
    ping
    quote
    rainbow
    reminder
    replace
    screen_detach
    send_delayed
    simple_notify
    spam
    status
    tell
    time_marker
    uptime
    revstr
    double
    shuffle
    iq_show
    regex_admin
    pointpoint
    autocorrect
    irc
    change_title
    pipe_cmd
    close_all
    reorder
    cyber
    csi
    dice
    disco
    marquee
    server_part
    vcard
    upload
