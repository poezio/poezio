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

    /exit
    /quit
        Just disconnect from the server and exit poezio.

    /plugin
        **Usage:** ``/load <plugin name>``

        Load a plugin.

    /plugins
        List the loaded plugins.

    /next
        Go to the next room.

    /prev
        Go to the previous room.

    /win
    /w
        **Usage:** ``/win <number>``

        Go to the specified room.

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
        Show the current bookmarks.

    /set
        **Usage:** ``/set [plugin|][section] <option> <value>``

        Set the value to the option in
        your configuration file. You can, for example, change your default nickname
        by doing "/set default_nick toto" or your resource with "/set resource
        blabla".  Doing so will write in the main config file, and in the main
        section ([Poezio]). But you can also write to another section, with ``/set
        bindings M-i ^i``, to a plugin configuration with ``/set mpd_client| host
        main`` (notice the **|**, it is mandatory to write in a plugin), or even to
        another section in a plugin configuration ``/set plugin|other_section option
        value``.  **toggle** can be used as a special value for a boolean option. It
        just set the option to true if it’s currently false, and to false if it’s
        currently true.

    /move_tab
        **Usage:** ``/move_tab <source> <destination>``

        Move tab <source> to <destination>. If
        the create_gaps option is true, then it will leave a gap at the <source>
        position, leading to usual behaviour. If create_gaps is not enabled, then the
        tabs will number from 0 to your actual tab number, without gaps (which means
        their number will change if you close a tab on the left of the list).

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

        Open a conversation with the specified JID (event if it is not in our roster),
        and send a message to him/her, if specified.

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


    /close
        Close the tab.

        .. note:: The /close command will work everywhere, except in the Roster tab,
                    which can’t be closed.


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

    /clear [RosterTab version]
        **Usage:** ``/clear``

        Clear the information buffer. (was /clear_infos)

    /ignore
        **Usage:** ``/ignore <nickname>``

        Ignore a specified nickname.

    /invite [MUCTab version]
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
        **Usage:** ``/topic <subject>``

        Change the subject of the room. You might want to knwow
        that entering ``/topic [tab]`` will autocomplete the topic.

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
        **Except for gmail users** because gmail.com sucks and will do weird things
        if you change your nickname in a MUC.

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

Roster tab commands
~~~~~~~~~~~~~~~~~~~
.. glossary::
    :sorted:

    /accept
        **Usage:** ``/accept [jid]``

        Authorize the provided JID (or the selected contact in the
        roster) to see your presence.

    /deny
        **Usage:** ``/deny [jid]``

        Prevent the provided JID (or the selected contact in the
        roster) from seeing your presence.

    /add
        **Usage:** ``/add <jid>``

        Add the specified JID to your roster and authorize him to see
        your presence. If he accepts you, the subscription will be mutual (and if he
        doesn’t, you can still /remove him).

    /name
        **Usage:** ``/name <jid> <name>``

        Set the given JID’s name in your roster.

    /password
        **Usage:** ``/password <password>``

        Change your password.

    /groupadd
        **Usage:** ``/groupadd <jid> <group>``

        Add the given JID to the given group (if the group
        does not exist, it will be created).

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

        Remove the specified JID from your roster. This will
        unsubscribe you from its presence, cancel its subscription to yours, and
        remove the item from your roster.

    /reconnect

        Disconnect from the remote server (if connected) and then
        connect to it again.

.. note:: The following commands only exist if your server supports them. If it
            does not, you will be notified when you start poezio.

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

    /clear [XML tab version]
        Clear the current buffer.

    /reset
        Reset the stanza filter.

    /filter_id
        **Usage:** ``/filter_id <id>``

        Filter by stanza id attribute.

    /filter_xpath
        **Usage:** ``/filter_xpath <xpath>``

        Filter with an XPath selector.

    /filter_xmlmask
        **Usage:** ``/filter_xmlmask <xml mask>``

        Filter using an XML mask
