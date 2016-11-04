.. _keys-page:

Keys
====

This file describes the default keys of poezio and explains how to
configure them.

By default, most keys manipulating the input (where you type your
messages and commands) behave like emacs does.

.. note:: Keys are case sensitive. Ctrl-X is not the same than Ctrl-x

Key bindings listing
--------------------
Some key bindings are available only in some tabs, others are global.

.. _global-keys:

Global keys
~~~~~~~~~~~
These keys work in **any** tab.

**Ctrl-p** or **F5**: Go to the previous tab.

**Ctrl-n** or **F6**: Go to the next tab.

**Alt-number**: Go to the tab with that number.

**Alt-j**: Waits for you to type a two-digits number. Go to tab number xx.

**Alt-e**: Go to the tab with a higher priority (private message >
highlight > message > non-empty input).

**Alt-z**: Go to the previously selected tab.

**Alt-r**: Go to the contact list tab.

**F4**: Toggle the left pane.

**F7**: Shrink the information buffer.

**F8**: Grow the information buffer.

**Ctrl-l**: Refresh the screen.

**Alt-D**: Scroll the information buffer up.

**Alt-C**: Scroll the information buffer down.

.. _input-keys:

Input keys
~~~~~~~~~~
These keys concern only the inputs.

NOTE: The clipboard is common to all inputs. This lets you cut a text
from one input to paste it into an other one.

**Ctrl-a**: Move the cursor to the beginning of line.

**Ctrl-e**: Move the cursor to the end of line.

**Ctrl-u**: Delete the text from the start of the input until the cursor
and save it to the clipboard.

**Ctrl-k**: Delete the text from the cursor until the end of the input
and save it to the clipboard.

**Ctrl-y**: Insert the content of the clipboard at the cursor position.

**Ctrl-Enter** or **Ctrl-j**: Insert a line break. Since the input is only one line,
the line break is represented by the character ``|`` in it but will be
sent as the real ``\n`` character.

**Alt-k**: Escape the next key pressed. For example if you press Alt-k,
followed by Ctrl-q, this will enter “^Q” into the text input. This is useful
for example in conjunction with the bind command, to help you know how to
bind something to a key combination without having to remember how to write
them by hand.

.. _chattab-keys:

Chat tab input keys
~~~~~~~~~~~~~~~~~~~

These keys work in any conversation tab (MultiUserChat, Private or
Conversation tabs).

**Key Up**: Use the previous message from the message history.

**Key Down**: Use the next message from the message history.

**Page Up**: Scroll up in the conversation by x lines, where x is the
height of the conversation window - 1.

**Page Down**: Like Page Up, but down.

**Ctrl-b**: Go one line up in the buffer.

**Ctrl-f**: Go one line down in the buffer.

**Ctrl-s**: Go half a screen up in the buffer.

**Ctrl-x**: Go half a screen down in the buffer.

**Alt-/**: Complete what you’re typing using the "recent" words from the
current conversation, if any.

**Alt-v**: Move the separator at the bottom of the tab.

**Alt-h**: Scroll to the separator, if there is one.

**Ctrl-c**: Insert xhtml formatting.

    You have to press Ctrl-c then a character listed below:
        - 1: Red
        - 2: Green
        - 3: Yellow/Orange
        - 4: Blue
        - 5: Pink
        - 6: Turquoise
        - b: Bold
        - u: Underlined
        - o: Stop formatting

.. _muctab-keys:

MultiUserChat tab input keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These keys work only in the MultiUserChat tab.

**Alt-u**: Scroll the user list down.

**Alt-y**: Scroll the user list up.

**Alt-p**: Scroll to the previous highlight.

**Alt-n**: Scroll to the next highlight.

**tabulation**: Complete a nick.

.. _muclisttab-keys:

MultiUserChat List tab input keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These keys work only in the MultiUserChat List tab (obtained with :term:`/list`).

**Up**: Go up one row.

**Down**: Go down one row.

**j**: Join the MultiUserChat currently selected.

**J**: Join the MultiUserChat currently selected, without giving focus to its tab.

**Ctrl-M**: Join the MultiUserChat currently selected (same as ``j``.

**PageUp**: Scroll a page of chats up.

**PageDown**: Scroll a page of chats down.


.. _rostertab-keys:

Contact list tab input keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~

These keys work only in the Contact list tab (the tab number 0).

**/**: Open a prompt for commands.

**s**: Start a search on the contacts.

**S**: Start a (slow) search with approximation on the contacts.

**Alt-u**: Move the cursor to the next group.

**Alt-y**: Move the cursor to the previous group.

**Ctrl-c**: Cancel the input (search or command)

**Enter** on a contact/resource: open a chat tab with this contact/resource

**Enter** on a group: fold/unfold that group

**Up**: Move the cursor down one contact.

**Down**: Move the cursor up one contact.

**PageUp**: Scroll a page of contacts up.

**PageDown**: Scroll a page of contacts down.

.. note:: The following will not work if you can still write things in the
                input (meaning you previously typed ``s`` or ``/``)

**Space**: Fold/Unfold the current item.

**o**: Show the offline contacts.

During a search
"""""""""""""""

**Enter**: end the search while keeping the selected contact under the cursor
(tip: press **Enter** a second time to open a chat window)

.. _forms-keys:

Data Forms tab keys
~~~~~~~~~~~~~~~~~~~

**Ctrl+y**: Validate the form, send it and close the tab.

**Ctrl+g**: Cancel that form (do not send your changes) and close the
tab.

**Up**: Select the next field.

**Down**: Select the previous field.

**Right/Left**: Switch between possible values, in a jid-multi,
 list-multi, list-single or text-multi field.

**Space**: Select that option

XML tab input keys
~~~~~~~~~~~~~~~~~~

These keys only work in the XML tab (obtained with :term:`/xml_tab`)

**Ctrl+k**: Freeze or un-freeze the display in order to have a clear view of
 the stanzas.


.. _key-conf:

Key configuration
-----------------

Bindings are keyboard shortcut aliases. You can use them
to define your own keys to replace the default ones.
where ``^x`` means *Control + x*
and ``M-x`` means *Alt + x*

To know exactly what the code of a key is, just run

.. code-block:: bash

    python3 poezio/keyboard.py

And enter any key.

Turn Alt-i into a tab key (completion, etc):

.. code-block:: ini

    M-i = ^I

Actions
-------

Mapping actions on keys
~~~~~~~~~~~~~~~~~~~~~~~

One may want to add keyboard shortcuts on actions that were not mapped already
in poezio. To this effect, you can map the keys on actions using the
:ref:`key-conf` seen in the previous section.


The actions are pseudo-keystrokes, and have to be treated the same way.
They all begin with an underscore to prevent any possible collision with things
already defined.

Actions list
~~~~~~~~~~~~

.. note:: Even if some of these actions are labelled as similar to other
        keystrokes, remapping the keystrokes will not remap the actions defined here.

**_bookmark**

    Bookmarks the current room.

    Similar to :term:`/bookmark`.

**_bookmark_local** Bookmarks the current room, locally.

    Similar to :term:`/bookmark_local`

**_close_tab**: Closes the current tab.

    This is the same as :term:`/close`. The first tab (the contact list) can
    not be closed.

**_disconnect**: Disconnects poezio from the server.

**_quit**: Exits poezio.

    Similar to :term:`/quit`.

**_reconnect**: Disconnects then reconnects poezio, if possible.

    This is similar to :term:`/reconnect`.

**_redraw_screen**: Redraws the screen.

    This isn’t normally useful, similar to Ctrl-l.

**_reload_theme**: Reloads the theme.

    Similar to :term:`/theme`.

**_remove_bookmark**: Removes the bookmark on the current room.

    Similar to :term:`/remove_bookmark`.

**_room_left**: Goes to the room on the left.

    Similar to the default Ctrl-p action.

**_room_right**: Goes to the room on the right.

    Similar to the default Ctrl-n action.

**_show_roster**: Goes to the contact list

    Similar to Alt-r action.

**_scroll_down**: Scrolls down in the current buffer.

    Similar to PAGEDOWN.

**_scroll_up**: Scrolls up in the current buffer.

    Similar to PAGEUP.

**_scroll_info_down**: Scrolls down in the info buffer.

    Similar to Alt-c.

**_scroll_info_up**: Scrolls up in the info buffer.

    Similar to Alt-d.

**_server_cycle**: Cycles in the current chatroom server.

    Similar to :term:`/server_cycle` in a chatroom. If you are not in a
    chatroom, you will get an error.

**_show_bookmarks**: Shows the current bookmarks.

    Similar to :term:`/bookmarks`.

**_show_important_room**: Goes to the most important room.

    Similar to Alt-e.

**_show_invitations**: Shows all the pending chatroom invitations.

    Similar to :term:`/invitations`.

**_show_plugins**: Shows the currently loaded plugins.

    Similar to :term:`/plugins`.

**_show_xmltab**: Opens an XML tab.

    Similar to :term:`/xml_tab`.

**_toggle_pane**: Toggles the left pane.

    Similar to F4.

Status actions
~~~~~~~~~~~~~~

**_available**: Sets the status to *available*.

    Similar to ``/status available``.

**_away**: Sets the status to *away*.

    Similar to ``/status away``.

**_chat**: Sets the status to *chat*.

    Similar to ``/status chat``.

**_dnd**: Sets the status to *dnd*.

    Similar to ``/status dnd``.

**_xa**: Sets the status to *xa*.

    Similar to ``/status xa``.

Command execution
~~~~~~~~~~~~~~~~~

With that kind of actions, you can also execute arbitrary commands, with the
``_exc_`` keyword.


You only have to prefix your command line with ``_exc_``, and without the  ``/``.


**/kick Partauche bound on Ctrl-w**:

.. code-block:: ini

    ^W = _exc_kick Partauche


That key binding will only work in the tabs defining the command (here, the
chatroom tab), and will show an error message in the others.

Examples
~~~~~~~~

**Config with user-defined actions**

.. code-block:: ini

    [bindings]
    ^W = _close_tab
    M-x = _show_xmltab
    M-i = _show_important_room
    M-p = _toggle_pane

**Config with commands mapped**

.. code-block:: ini

    [bindings]
    M-c = _exc_configure
    ^Q = _exc_part RAGE QUIT
    ^J = _exc_join
    ^F = _exc_load figlet
    ^R = _exc_load rainbow
    ^S = _exc_say llollllllllllll
