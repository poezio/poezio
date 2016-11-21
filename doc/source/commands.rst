Commands
========

Commands start with the ``/`` character and can take a list of any number
of arguments, separated by spaces. If an argument should contain a space,
you can use the ``"`` character to surround this argument.

The commands described in this page are shown like this:

``/command <mandatory argument> [optional argument]``

You can get the same help as below from inside poezio with the :term:`/help` command.

.. note:: Use command parameters like this:

    - Do not use quotes if they are unnecessary (words without special chars or spaces)
    - If the command takes several agrguments, you need to put quotes around arguments containing special chars such as backslashes or quotes
    - If the command always takes only one argument, then do not use quotes even for words containing special chars

.. _global-commands:

Global commands
~~~~~~~~~~~~~~~

These commands work in *any* tab.

.. glossary::
    :sorted:

    /help
        **Usage:** ``/help [command]``

        If called without an argument, this command will list the
        available commands. If it has a valid command as an argument, this command
        will show the usage and the help for the given command.

    /join
        **Usage:** ``/join [room_name][@server][/nick] [password]``

        Join the specified room. You
        can specify a nickname after a slash (/). If no nickname is specified, you
        will use the default_nick in the configuration file. You can omit the room
        name: you will then join the room you're looking at (useful if you were
        kicked). You can also provide a room_name without specifying a server, the
        server of the room you're currently in will be used. You can also provide a
        password to join the room.

        *Examples:*

        - ``/join room@server.tld``
        - ``/join room@server.tld/John``
        - ``/join room2``
        - ``/join /me_again``
        - ``/join``
        - ``/join room@server.tld/my_nick password``
        - ``/join / password``

    /destroy_room
        **Usage:** ``/destroy_room [room JID]``

        Try to destroy the room given as a parameter, or the current room
        is not parameter is given and the current tab is a chatroom.

        You need to be the owner of a room or a server admin to destroy it.

    /exit
    /quit
        Just disconnect from the server and exit poezio.

    /load
        **Usage:** ``/load <plugin name> [<other plugin> …]``

        Load or reload one or several plugins.

    /unload
        **Usage:** ``/unload <plugin name> [<other plugin> …]``

        Unload one or several plugins.

    /plugins
        List the loaded plugins.

    /next
        Go to the next room.

    /prev
        Go to the previous room.

    /win
    /w
        **Usage:** ``/win <number or string>``

        Go to the matching tab.  If the argument is a number, it goes to the tab with that number.
        Otherwise, it goes to the next tab whose name contains the given string.

    /status
        **Usage:** ``/status <availability> [status message]``

        Set your availability and
        (optionaly) your status message. The <availability> argument is one of
        "available, chat, away, afk, dnd, busy, xa" and the optional [status] argument
        will be your status message.'

    /bookmark
        **Usage:** ``/bookmark [roomname][/nick] [autojoin] [password]``

        Bookmark the specified
        room. This command uses  almost the same syntax as /join. Type ``/help join`` for
        syntax examples. Note that when typing /bookmark on its own, the room will be
        bookmarked with the nickname you're currently using in this room (instead of
        default_nick). You can specify an optional *autojoin* and *password* if you
        call it with the full line (/bookmark alone will put the room in autojoin
        without password). The bookmarks stored with this command are stored on your
        xmpp server.

    /bookmark_local
        **Usage:** ``/bookmark_local [roomname][/nick]``

        Bookmark the  specified room (you will
        then auto-join it on each poezio start). This commands uses almost the same
        syntax as /join. Type /help join for syntax examples. Note that when typing
        /bookmark on its own, the room will be bookmarked with the nickname you're
        currently using in this room (instead of default_nick). The bookmarks stored
        with this command will be stored locally. They have priority over the ones
        stored online.

    /remove_bookmark
        **Usage:** ``/remove_bookmark [room_jid]``

        Remove the bookmark on *room_jid* or the one on the current tab, if any.

    /bookmarks
      **Usage:** ``/bookmarks``

      Open a :ref:`bookmarks tab` in order to edit the current boookmarks.

    /set
        **Usage:** ``/set [plugin|][section] <option> <value>``

        Set the value to the option in
        your configuration file. You can, for example, change your default nickname
        by doing "/set default_nick toto" or your password with "/set password
        blabla".  Doing so will write in the main config file, and in the main
        section ([Poezio]). But you can also write to another section, with ``/set
        bindings M-i ^i``, to a plugin configuration with ``/set mpd_client| host
        main`` (notice the **|**, it is mandatory to write in a plugin), or even to
        another section in a plugin configuration ``/set plugin|other_section option
        value``.  **toggle** can be used as a special value for a boolean option. It
        just set the option to true if it’s currently false, and to false if it’s
        currently true.

    /set_default
        **Usage:** ``/set_default [section] <option>``

        Set the value of an option back to the default. For example,
        ``/set_default password`` will reset the ``password`` option.

    /toggle
        **Usage:** ``/toggle <option>``

        Toggle an option, shortcut for :term:`/set` <option> toggle.

    /move_tab
        **Usage:** ``/move_tab <source> <destination>``

        Move tab <source> to <destination>. If the :term:`create_gaps` option
        is true, then it will leave a gap at the <source> position, leading
        to usual behaviour. If create_gaps is not enabled, then the tabs will
        number from 0 to your actual tab number, without gaps (which means
        their number will change if you close a tab on the left of the list).

        A value of ``.`` for a parameter means the current tab.

    /theme
        **Usage:** ``/theme [theme_name]``

        Reload the theme defined in the config file. If
        *theme_name* is given, this command will act like :samp:`/set theme {theme_name}` then
        /theme.

    /presence
        **Usage:** ``/presence <jid> [type] [status]``

        Send a directed presence to *jid* using
        *type* and *status* if provided.

    /rawxml
        **Usage:** ``/rawxml <stanza>``

        Send a custom XML stanza.

    /xml_tab
        Open an XML tab.

    /list
        **Usage:** ``/list [server.tld]``

        Get the list of public chatrooms in the specified server (open a :ref:`listtab`)

    /message
        **Usage:** ``/message <jid> [optional message]``

        Open a conversation with the specified JID (event if it is not in our
        contact list), and send a message to them, if specified.

    /version
        **Usage:** ``/version <jid>``

        Get the software version of the given JID (usually its XMPP
        client and Operating System).

    /invite
        **Usage:** ``/invite <jid> <room> [reason]``

        Invite *jid* to *room* with *reason* (if
        provided).

    /invitations
        Show the pending invitations.

    /activity
        **Usage:** ``/activity [<general> [specific] [comment]]``

        Send your current activity to your contacts (use the completion to cycle
        through all the general and specific possible activities).

        Nothing means "stop broadcasting an activity".

    /mood
        **Usage:** ``/mood [<mood> [comment]]``
        Send your current mood to your contacts (use the completion to cycle
        through all the possible moods).

        Nothing means "stop broadcasting a mood".

    /gaming
        **Usage:** ``/gaming [<game name> [server address]]``

        Send your current gaming activity to your contacts.

        Nothing means "stop broadcasting a gaming activity".

    /last_activity
        **Usage:** ``/activity <jid>``

        Show the last activity of a contact or a server (its
        uptime, in that case).

    /server_cycle
        **Usage:** ``/server_cycle [server.tld] [message]``

        Disconnect and reconnect in all the
        rooms of server.tld.

    /bind
        **Usage:** ``/bind <key> <eq>``

        Bind a key to another key or to a "command". For example,
        ``/bind ^H KEY_UP`` makes Control + h behave the same way as the Up key. See the
        *key bindings documentation page* for more details.

    /runkey
        **Usage:** ``/runkey <key>``

        Execute the action defined for *key*. For example,
        ``/runkey KEY_PPAGE`` will scroll up, or ``/runkey ^N`` will go to the next tab.

    /self
        Reminds you of who you are and what your status is.

    /reload
        Reload the config. You can achieve the same by sending SIGUSR1 to poezio.

    /close
        Close the tab.

        .. note:: The /close command will work everywhere, except in the
                    Contact list tab, which can’t be closed.


.. _chattab-commands:

Chat tab commands
~~~~~~~~~~~~~~~~~

These commands will work in any conversation tab (MultiUserChat, Private, or
 Conversation tabs).

.. glossary::
    :sorted:

    /correct
        **Usage:** ``/correct <corrected message>``

        Replace the content of the last sent message with *corrected message*.

    /say
        **Usage:** ``/say <message>``

        Just send the message (only useful it you want your message
        to begin with a **/**). Note that you can also send message starting with a **/**
        by starting it with **//**.

    /xhtml
        **Usage:** ``/xhtml <custom xhtml>``

        Send a custom xhtml message to the current tab.

    /clear
        Clear the current buffer.

.. _muctab-commands:

MultiUserChat tab commands
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. glossary::
    :sorted:

    /affiliation
       **Usage:** ``/affiliation <nick> <affiliation>``

       Sets the affiliation of the participant designated by **nick** to the
       given **affiliation** (can be one of owner, admin, member, outcast
       and none).

    /role
       **Usage:** ``/affiliation <nick> <role>``

       Sets the role of the participant designated by **nick** to the given
       **role** (can be one of moderator, participant, visitor and none).

    /color
        **Usage:** ``/color <nick> <color>``

        Assign a color to the given nick. The nick and all its alias (nicks
        are considered identical if they only differ by the presence of one
        ore more **_** character at the beginning or the end. For example
        _Foo and Foo___ are considered aliases of the nick Foo) will then
        always have the specified color, in all MultiUserChat tabs.  This is
        true whatever the value of **deterministic_nick_colors** is.

        Use the completion to get a list of all the available color values.
        Use the special color **unset** to remove the attributed color on
        this nick.
        You can also use **random** to attribute a random color.

    /clear [Chatroom version]
        **Usage:** ``/clear``

        Clear the messages buffer.

    /ignore
        **Usage:** ``/ignore <nickname>``

        Ignore a specified nickname.

    /invite [Chatroom version]
        **Usage:** ``/invite <jid> [reason]``

        Invite *jid* to this room with *reason* (if
        provided).


    /unignore
        **Usage:** ``/unignore <nickname>``

        Remove the specified nickname from the ignore list.

    /kick
        **Usage:** ``/kick <nick> [reason]``

        Kick the user with the specified nickname. You can
        also give an optional reason.

    /topic
        **Usage:** ``/topic [subject]``

        Change the subject of the room.

        Using the auto-completion of this command writes the current topic
        in the input, to help the user make a small change to the topic
        whithout having to rewrite it all by hand.

        If no subject is specified as an argument, the current topic is
        displayed, unchanged.

    /query
        **Usage:** ``/query <nick> [message]``

        Open a :ref:`privatetab` with <nick>. This nick
        has to be present in the room you’re currently in. If you specified a message
        after the nickname, it will be sent to this user.

    /part
        **Usage:** ``/part [message]``

        Disconnect you from a room. You can specify an optional
        message.

    /nick
        **Usage:** ``/nick <nickname>``

        Change your nickname in the current room.

    /recolor
        **Usage:** ``/recolor [random]``

        Re-assign a color to all the participants in the current
        room, based on the last time they talked. Use this if the participants
        currently talking have too many identical colors. If a random argument is
        given, the participants will be shuffled before they are assigned a color.

    /cycle
        **Usage:** ``/cycle [message]``

        Leave the current room an rejoint it immediatly. You can
        specify an optional quit message.

    /info
        **Usage:** ``/info <nickname>``

        Display some information about the user in the room:
        his/her role, affiliation, status, and status message.

    /version
        **Usage:** ``/version <nickname or jid>``

        Get the software version of the given nick in
        room or the given jid (usually its XMPP client and Operating System).

    /configure
        Configure the current room through a form (Open a :ref:`dataformtab`).

    /names
        Get the list of the users in the room, their number, and the list
        of the people assuming different roles.

.. _privatetab-commands:

Private tab commands
~~~~~~~~~~~~~~~~~~~~

.. glossary::
    :sorted:

    /info
        Display some info about this user in the MultiUserChat.

    /unquery
        Close the tab.

    /version
        Get the software version of the current interlocutor (usually its
        XMPP client and Operating System).

.. _conversationtab-commands:

Normal Conversation tab commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. glossary::
    :sorted:

    /info
        Display the status of this contact.

    /unquery
        Close the tab.

    /version
        Get the software version of the current interlocutor (usually its
        XMPP client and Operating System).

.. _rostertab-commands:

Contact list tab commands
~~~~~~~~~~~~~~~~~~~~~~~~~
.. glossary::
    :sorted:

    /accept
        **Usage:** ``/accept [jid]``

        Authorize the provided JID (or the selected contact in the
        contact list) to see your presence.

    /deny
        **Usage:** ``/deny [jid]``

        Prevent the provided JID (or the selected contact in the
        contact list) from seeing your presence.

    /add
        **Usage:** ``/add <jid>``

        Add the specified JID to your contact list and authorize them to see
        your presence. If they accepts you, the subscription will be mutual
        (and if they don’t, you can still /remove them).

    /name
        **Usage:** ``/name <jid> <name>``

        Set the given JID’s name in your contact list.

    /password
        **Usage:** ``/password <password>``

        Change your password.

    /groupadd
        **Usage:** ``/groupadd (<jid> <group>|<group>)

        Add the given JID to the given group (if the group
        does not exist, it will be created). If no jid is provided,
        the currently selected item on the contact list (resource or JID)
        will be used.

    /groupmove
        **Usage:** ``/groupmove <jid> <old_group> <new_group>``

        Move the given JID from one group
        to another (the JID has to be in the first group, and the new group  may not
        exist).

    /groupremove
        **Usage:** ``/groupremove <jid> <group>``

        Remove the given JID from the given group (if
        the group is empty after that, it will get deleted).

    /remove
        **Usage:** ``/remove [jid]``

        Remove the specified JID from your contact list. This will
        unsubscribe you from its presence, cancel its subscription to yours, and
        remove the item from your contact list.

    /reconnect

        Disconnect from the remote server (if connected) and then
        connect to it again.

.. note:: The following commands only exist if your server announces it
          supports them.

.. glossary::
    :sorted:

    /block
        **Usage:** ``/block [jid]``

        Block the following JID using simple blocking. You will not
        receive any of his messages and won’t be able to send some to him either.

    /unblock
        **Usage:** ``/unblock [jid]``

        Unblock a previously blocked JID using simple blocking. You
        will be able to send and receive messages from him again.

    /list_blocks
        List the blocked JIDs.

    /certs

        List the remotely stored X.509 certificated allowed to connect
        to your accounts.

    /cert_add
        **Usage:** ``/cert_add <name> <certificate file> [management]``

        Add a client X.509 certificate to the list of the certificates
        which grand access to your account. It must have an unique name
        the file must be in PEM format. ``[management]`` is true by
        default and specifies if the clients connecting with this
        particular certificate will be able to manage the list of
        authorized certificates.

    /cert_disable
        **Usage:** ``/cert_disable <name>``

        Remove a certificate from the authorized list. Clients currently
        connected with the certificate identified by ``<name>`` will
        however **not** be disconnected.

    /cert_revoke
        **Usage:** ``/cert_revoke <name>``

        Remove a certificate from the authorized list. Clients currently
        connected with the certificate identified by ``<name>`` **will**
        be disconnected.

    /cert_fetch
        **Usage:** ``/cert_fetch <name> <path>``

        Download the public key of the authorized certificate identified by
        ``name`` from the XMPP server, and store it in ``<path>``.

.. note:: The following commands do not comply with any XEP or whatever, but they
 can still prove useful when you are migrating to an other JID.

.. glossary::
    :sorted:

    /export
        **Usage:** ``/export [/path/to/file]``

        Export your contacts into :file:`/path/to/file` if
        specified, or :file:`$HOME/poezio_contacts` if not.

    /import
        **Usage:** ``/import [/path/to/file]``

        Import your contacts from :file:`/path/to/file` if
        specified, or :file:`$HOME/poezio_contacts` if not.

.. _xmltab-commands:

XML tab commands
~~~~~~~~~~~~~~~~

.. glossary::
    :sorted:

    /clear [XML tab version]
        Clear the current buffer.

    /dump
        **Usage:** ``/dump <filename>``

        Write the content of the XML buffer into a file.

    /filter_reset
        Reset the stanza filters.

    /filter_id
        **Usage:** ``/filter_id <id>``

        Filter by stanza id attribute.

    /filter_xpath
        **Usage:** ``/filter_xpath <xpath>``

        Filter with an XPath selector.

    /filter_xmlmask
        **Usage:** ``/filter_xmlmask <xml mask>``

        Filter using an XML mask

    /filter_jid
        **Usage:** ``/filter_jid <jid>``

        Filter by JID, both ``to`` and ``from``.

    /filter_to
        **Usage:** ``/filter_to <jid>``

        Filter by JID for the ``to`` attribute.

    /filter_from
        **Usage:** ``/filter_from <jid>``

        Filter by JID for ``from`` attribute.
