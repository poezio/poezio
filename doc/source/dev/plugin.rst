Plugin API documentation
========================

External plugins
----------------

It is possible to create external plugins easily using `setuptools'
entry_point
<https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins>`_
feature. You can register your plugin against the ``poezio_plugins`` entry
group with the following snippet in your project ``setup.py``:

.. code-block:: python

    setup(
        ..
        packages=['yourmodule'],
        entry_points={'poezio_plugins': 'yourplugin = yourmodule'},
        ..
    )

The plugin will then be available as ``yourplugin`` at runtime.

BasePlugin
----------

.. module:: poezio.plugin

.. autoclass:: BasePlugin

    .. method:: init(self)

        Method called at the creation of the plugin.

        Do not override __init__ and use this instead.

    .. method:: cleanup(self)

        Method called before the destruction of the plugin.

        Use it to erase or save things before the plugin is disabled.

    .. attribute:: core

        The Poezio :py:class:`~Core` object. Use it carefully.

    .. attribute:: api

        The :py:class:`~PluginAPI` instance for this plugin.

    .. attribute:: dependencies

        Dependencies on other plugins, as a set of strings. A reference
        to each dependency will be added in ``refs``.

    .. attribute:: refs

        This attribute is not to be edited by the user. It will be
        populated when the plugin is initialized with references on each
        plugin specified in the ``dependencies`` attribute.

Each plugin inheriting :py:class:`~BasePlugin` has an ``api`` member variable, which refers
to a :py:class:`~PluginAPI` object.

The :py:class:`~PluginAPI` object is an a interface through which the :py:class:`~BasePlugin`
(and inheritors) *should* go to interact with poezio. If it is not sufficient, then the ``core``
member can be used.

PluginAPI
---------

.. autoclass:: PluginAPI
    :members:
    :undoc-members:


Example plugins
---------------

**Example 1:** Add a simple command that sends "Hello World!" into the conversation

.. code-block:: python

    class Plugin(BasePlugin):
        def init(self):
            self.add_command('hello', self.command_hello, "Send 'Hello World!'")

        def command_hello(self, arg):
            self.core.send_message('Hello World!')

**Example 2:** Adds an event handler that sends “tg” to a groupchat when a message is received from someone named “Partauche”

.. code-block:: python

    class Plugin(BasePlugin):
        def init(self):
            self.add_event_handler('muc_msg', self.on_groupchat_message)

        def on_groupchat_message(self, message, tab):
            if message['mucnick'] == "Partauche":
                tab.command_say('tg')
