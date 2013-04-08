Plugin API documentation
========================

.. module:: plugin

.. autoclass:: BasePlugin
    :members: init, cleanup, api, core

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


Each plugin inheriting :py:class:`~BasePlugin` has an ``api`` member variable, which refers
to a :py:class:`~PluginAPI` object.

The :py:class:`~PluginAPI` object is an a interface through which the :py:class:`~BasePlugin`
(and inheritors) *should* go to interact with poezio. If it is not sufficient, then the ``core``
member can be used.

.. autoclass:: PluginAPI
    :members:
    :undoc-members:


