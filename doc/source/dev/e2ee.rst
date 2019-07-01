End-to-end Encryption API documentation
=======================================

E2EEPlugin
----------

.. module:: poezio.plugin_e2ee


.. autoclass:: E2EEPlugin
  :members:

Builds on top of :py:class:`~BasePlugin` and requires the developer to
implement two methods, `decrypt` and `encrypt`, as well as the
`encryption_name` and `eme_ns` attribute.

Please refer to :py:class:`~BasePlugin` for more information on how to
write plugins.

Example plugins
---------------

**Example 1:** Base64 plugin

.. code-block:: python

    from base64 import b64decode, b64encode
    from poezio.plugin_e2ee import E2EEPlugin
    from slixmpp import Message


    class Plugin(E2EEPlugin):
        """Base64 Plugin"""

        encryption_name = 'base64'
        encryption_short_name = 'b64'
        eme_ns = 'urn:xmpps:base64:0'

        # This encryption mechanism is using <body/> as a container
        replace_body_with_eme = False

        def decrypt(self, message: Message, _tab) -> None:
            """
                Decrypt base64
            """
            body = message['body']
            message['body'] = b64decode(body.encode()).decode()

        def encrypt(self, message: Message, _tab) -> None:
            """
                Encrypt to base64
            """
            # TODO: Stop using <body/> for this. Put the encoded payload in another element.
            body = message['body']
            message['body'] = b64encode(body.encode()).decode()
