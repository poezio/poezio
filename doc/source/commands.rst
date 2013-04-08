Commands
========

Commands start with the **/** character and can take a list of any number
of arguments, separated by spaces. If an argument should contain a space,
you can use the **"** character to surround this argument.

The commands described in this page are shown like this:

.. code-block::

    /command <mandatory argument> [optional argument]

You can get the same help as below from inside poezio with the **/help** command.

.. note:: Use command parameters like this:

    - Do not use quotes if they are unnecessary (words without special chars or spaces)
    - If the command takes several agrguments, you need to put quotes around arguments containing special chars such as backslashes or quotes
    - If the command always takes only one argument, then do not use quotes even for words containing special chars

Global commands
~~~~~~~~~~~~~~~

These commands work in *any* tab.

**/help [command]**
    If called without an argument, this command will list the
    available commands. If it has a valid command as an argument, this command
    will show the usage and the help for the given command.

**/join [room_name][@server][/nick] [password]**
    Join the specified room. You
    can specify a nickname after a slash (/). If no nickname is specified, you
    will use the default_nick in the configuration file. You can omit the room
    name: you will then join the room you're looking at (useful if you were
    kicked). You can also provide a room_name without specifying a server, the
    server of the room you're currently in will be used. You can also provide a
    password to join the room.

    *Examples:*

    - /join room@server.tld
    - /join room@server.tld/John
    - /join room2
    - /join /me_again
    - /join
    - /join room@server.tld/my_nick password
    - /join / password

**/exit and /quit**
    Just disconnect from the server and exit poezio.

.. _command-next:
**/next**
    Go to the next room.

.. _command-prev:
**/prev**
    Go to the previous room.

.. _command-win:
**/win <number> or /w <number>**
    Go to the specified room.

.. _command-status:
**/status <availability> [status message]**
    Set your availability and
    (optionaly) your status message. The <availability> argument is one of
    "available, chat, away, afk, dnd, busy, xa" and the optional [status] argument
    will be your status message.'

.. _command-bookmark:
**/bookmark [roomname][/nick] [autojoin] [password]**
    Bookmark the specified
    room. This command uses  almost the same syntax as /join. Type /help join for
    syntax examples. Note that when typing /bookmark on its own, the room will be
    bookmarked with the nickname you're currently using in this room (instead of
    default_nick). You can specify an optional *autojoin* and *password* if you
    call it with the full line (/bookmark alone will put the room in autojoin
    without password). The bookmarks stored with this command are stored on your
    xmpp server.

.. _command-bookmark-local:
**/bookmark_local [roomname][/nick]**
    Bookmark the  specified room (you will
    then auto-join it on each poezio start). This commands uses almost the same
    syntax as /join. Type /help join for syntax examples. Note that when typing
    /bookmark on its own, the room will be bookmarked with the nickname you're
    currently using in this room (instead of default_nick). The bookmarks stored
    with this command will be stored locally. They have priority over the ones
    stored online.

.. _command-remove-bookmark:
**/remove_bookmark [room_jid]**
    Remove the bookmark on *room_jid* or the one on the current tab, if any.

.. _command-bookmarks:
**/bookmarks**
    Show the current bookmarks.

.. _command-set:
**/set [plugin|][section] <option> <value>**
    Set the value to the option in
    your configuration file. You can, for example, change your default nickname
    by doing "/set default_nick toto" or your resource with "/set resource
    blabla".  Doing so will write in the main config file, and in the main
    section ([Poezio]). But you can also write to another section, with "/set
    bindings M-i ^i", to a plugin configuration with "/set mpd_client| host
    main" (notice the **|**, it is mandatory to write in a plugin), or even to
    another section in a plugin configuration "/set plugin|other_section option
    value".  **toggle** can be used as a special value for a boolean option. It
    just set the option to true if it’s currently false, and to false if it’s
    currently true.

.. _command-move-tab:
**/move_tab <source> <destination>**
    Move tab <source> to <destination>. If
    the create_gaps option is true, then it will leave a gap at the <source>
    position, leading to usual behaviour. If create_gaps is not enabled, then the
    tabs will number from 0 to your actual tab number, without gaps (which means
    their number will change if you close a tab on the left of the list).

.. _command-theme:
**/theme [theme_name]**
    Reload the theme defined in the config file. If
    _theme_name_ is given, this command will act like /set theme theme_name then
    /theme.

.. _command-presence:
**/presence <jid> [type] [status]**
    Send a directed presence to _jid_ using
    _type_ and _status_ if provided.

*/rawxml <stanza>*:: Send a custom XML stanza.

*/list [server.tld]*:: Get the list of public chatrooms in the specified server
.

*/message <jid> [optional message]*:: Open a conversation with the specified
 JID (event if it is not in our roster), and send a message to him, if
 specified.

*/version <jid>*:: Get the software version of the given JID (usually its XMPP
 client and Operating System).

*/invite <jid> <room> [reason]*:: Invite _jid_ to _room_ wit _reason_ (if
  provided).

*/invitations*:: Show the pending invitations.

*/activity <jid>*:: Show the last activity of a contact or a server (its
 uptime, in that case).

*/server_cycle [server.tld] [message]*:: Disconnect and reconnect in all the
 rooms of server.tld.

*/bind <key> <eq>*:: Bind a key to another key or to a "command". For example,
 "/bind ^H KEY_UP" makes Control + h behave the same way as the Up key. See the
 link:keys.html[key bindings documentation page] for more details.

*/runkey <key>*:: Execute the action defined for _key_. For example,
 "/runkey KEY_PPAGE" will scroll up, or "/runkey ^N" will go to the next tab.

*/self*:: Reminds you of who you are and what your status is.

NOTE: The following command will work everywhere, except in the Roster tab.

*/close*:: Close the tab.

Chat tab commands
~~~~~~~~~~~~~~~~~

These commands will work in any conversation tab (MultiUserChat, Private, or
 Conversation tabs).

*/say <message>*:: Just send the message (only useful it you want your message
 to begin with a _/_). Note that you can also send message starting with a _/_
 by starting it with _//_.

*/xhtml <custom xhtml>*:: Send a custom xhtml message to the current tab.

*/clear*:: Clear the current buffer.

MultiUserChat tab commands
~~~~~~~~~~~~~~~~~~~~~~~~~~

*/ignore <nickname>*:: Ignore a specified nickname.

*/unignore <nickname>*:: Remove the specified nickname from the ignore list.

*/kick <nick> [reason]*:: Kick the user with the specified nickname. You can
 also give an optional reason.

*/topic <subject>*:: Change the subject of the room. You might want to knwow
 that entering "/topic [tab]" will autocomplete the topic.

*/query <nick> [message]*:: Open a private conversation with <nick>. This nick
 has to be present in the room you’re currently in. If you specified a message
 after the nickname, it will be sent to this user.

*/part [message]*:: Disconnect you from a room. You can specify an optional
 message.

*/close [message]*:: Disconnect you from a room (if you are connected) and
 close the tab. You can specify an optional message if you are still connected.

*/nick <nickname>*:: Change your nickname in the current room.
 *Except for gmail users* because gmail.com sucks and will do weird things
 if you change your nickname in a MUC.

*/recolor [random]*:: Re-assign a color to all the participants in the current
 room, based on the last time they talked. Use this if the participants
 currently talking have too many identical colors. If a random argument is
 given, the participants will be shuffled before they are assigned a color.

*/cycle [message]*:: Leave the current room an rejoint it immediatly. You can
 specify an optional quit message.

*/info <nickname>*:: Display some information about the user in the room:
 his/her role, affiliation, status, and status message.

*/version <nickname or jid>*:: Get the software version of the given nick in
 room or the given jid (usually its XMPP client and Operating System).

*/configure*:: Configure the current room through a form.

*/names*:: Get the list of the users in the room, their number, and the list
 of the people assuming different roles.

Private tab commands
~~~~~~~~~~~~~~~~~~~~

*/info*:: Display some info about this user in the MultiUserChat.

*/unquery*:: Close the tab.

*/version*:: Get the software version of the current interlocutor (usually its
 XMPP client and Operating System).

Normal Conversation tab commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*/info*:: Display the status of this contact.

*/unquery*:: Close the tab.

*/version*:: Get the software version of the current interlocutor (usually its
 XMPP client and Operating System).

Roster tab commands
~~~~~~~~~~~~~~~~~~~

*/accept [jid]*:: Authorize the provided JID (or the selected contact in the
 roster) to see your presence.

*/deny [jid]*:: Prevent the provided JID (or the selected contact in the
 roster) from seeing your presence.

*/add <jid>*:: Add the specified JID to your roster and authorize him to see
 your presence. If he accepts you, the subscription will be mutual (and if he
 doesn’t, you can still /deny him).

*/name <jid> <name>*:: Set the given JID’s name.

*/groupadd <jid> <group>*:: Add the given JID to the given group (if the group
 does not exist, it will be created).

*/groupmove <jid> <old_group> <new_group>*:: Move the given JID from one group
 to another (the JID has to be in the first group, and the new group  may not
 exist).

*/groupremove <jid> <group>*:: Remove the given JID from the given group (if
 the group is empty after that, it will get deleted).

*/remove [jid]*:: Remove the specified JID from your roster. This will
 unsubscribe you from its presence, cancel its subscription to yours, and
 remove the item from your roster.

*/reconnect*:: Disconnect from the remote server (if connected) and then
 connect to it again.

NOTE: The following commands only exist if your server supports them. If it
does not, you will be notified when you start poezio.

*/block [jid]*:: Block the following JID using simple blocking. You will not
 receive any of his messages and won’t be able to send some to him either.

*/unblock [jid]*:: Unblock a previously blocked JID using simple blocking. You
 will be able to send and receive messages from him again.

*/list_blocks*:: List the blocked JIDs.

NOTE: The following commands do not comply with any XEP or whatever, but they
 can still prove useful when you are migrating to an other JID.

*/export [/path/to/file]*:: Export your contacts into /path/to/file if
 specified, or $HOME/poezio_contacts if not.

*/import [/path/to/file]*:: Import your contacts from /path/to/file if
 specified, or $HOME/poezio_contacts if not.

XML tab commands
~~~~~~~~~~~~~~~~

*/clear*:: Clear the current buffer.
