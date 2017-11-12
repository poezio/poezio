.. _overview:

Overview
========

.. note:: This is not an introduction to XMPP, but to how poezio works.


Global overview
---------------

Poezio is an application that has three main layers, mostly separated in three
different python modules: ``core``, ``tabs``, and ``windows``. An UML diagram of
Poezio would be inneficient, cluttered, or incomplete, so there is none, if
that bugs you.

.. figure:: ../images/layers.png
    :alt: Layers

**Core** is mostly a “global” object containing the state of the application at
any time, it contains the global commands, the xmpp event handlers, the list
of open tabs, etc. Most objects in poezio have a self.core attribute
referencing the **Core** (it’s a singleton, so there is never more than one
instance). **Core** also contains the main loop of the application, which then
dispatchs the I/O events (keypress) to the appropriate methods.

But the main loop is not the most important thing in poezio; because it is an
IM client, it is essentially event-driven. The event part is handled by
slixmpp, which is our fork of sleekxmpp to use asyncio instead of threads.

**Tabs** are the second layer of poezio, but the first dealing with the UI: each
**Tab** is a layout of several **windows**, it contains tab-specific commands,
tab-specific keybinds, and it has methods in order for core to
interact with it, and some methods are only proxies for the methods of a
**window**.

Example scenario: If someone presses the key PageUp, then Core will call the
appropriate method on the current _Tab_, which will in turn, if it implements the
method (inherited empty from the Tab class), call a scrolling method from the
appropriate **window**.

All tabs types inherit from the class **Tab**, and the tabs featuring
chat functionnality will inherit from **ChatTab** (which inherits from **Tab**).

Examples of **tabs**: MUCTab, XMLTab, RosterTab, MUCListTab, etc…

Event handlers
--------------

The events handlers are registered right at the start of poezio, and then
when a matching stanza is received, the handler is called. The handlers are
in **Core**, and then they call the appropriate methods in the corresponding
**tabs**.

Example scenario: if a message is received from a MUC, then the **Core** handler
will identify the **Tab**, and call the relevant handler from this **Tab**, this tab
will in turn, add the message to the buffer, which will then add it to the
relevant **windows**.

.. note:: All the _windows_ that deal with received or generated text are linked
    to a **text_buffer**, in order to rebuild all the display lines from the
    sources if necessary. This also enables us to have several **windows**
    presenting the same text, even if they are not of the same size and layout.

Commands and completion
-----------------------

Commands are quite straightforward: those are methods that take a string as a
parameter, and they do stuff.

From a user point of view, the methods are entered like that:

.. code-block:: none

    /command arg1 arg2

or

.. code-block:: none

    /command "arg1 with spaces" arg2

However, when creating a command, you wil deal with _one_ str, no matter what.
There are utilities to deal with it (common.shell_split), but it is not always
necessary. Commands are registered in the **commands** dictionnary of a tab
structured as key (command name) -> tuple(command function, help string, completion).

Completions are a bit tricky, but it’s easy once you get used to it:

They take an **Input** (a _windows_ class) as a parameter, named the_input
everywhere in the sources. To effectively have a completion, you have to create
a :py:class:`poezio.core.structs.Completion` object initialized with the
completion you want to call
(**the_input.auto_completion()** or **the_input.new_completion()**) with the
relevant parameters and return it with the function. Previously you would call
the function directly from the completion method, but having side effects
inside it makes it harder to test.

.. code-block:: python

    class Input(Win):
        # …
        def auto_completion(completion_list, after='', quotify=True):
            # …

        def new_completion(completion_list, argument_position, after='', quotify=True):
            # …

Set the input to iterate over **completion_list** when the user hits tab, to insert
**after** after the completed item, and surround the item with double quotes or
not.

To find the current completed argument, use the **input.get_argument_position()**
method. You can then use **new_completion()** to select the argument to be completed.

You can look for examples in the sources, all the possible cases are
covered (single-argument, complex arguments with spaces, several arguments,
etc…).

.. note::
    Only **new_completion()** used together with **get_argument_position()** allow
    completing arguments that are not at the end of the command line, therefore it
    is preferable to use that and not **auto_completion()**.


Dealing with the command line
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For convenience’s sake, poezio includes a **decorators** module containing a
**command_args_parser**, which can be used to filter the input easily.

Examples:

.. code-block:: python

    from decorators import command_args_parser
    class MyClass(object):

        @command_args_parser.raw
        def command_raw(self, raw):
            # the "raw" parameter will be the raw input string

        @command_args_parser.ignored
        def command_ignored(self):
            # no argument is given to that function

        @command_args_parser.quoted(mandatory=1, optional=0)
        def command_quoted_1(self, args):
            # the "args" parameter will be a list containing one argument

See the source of the CommandArgParser for more information.

.. autoclass:: poezio.decorators.CommandArgParser
