Event Index
===========

The following events are poezio-only events, for SleekXMPP events, check out
`their index <http://sleekxmpp.com/event_index.html>`_.

.. glossary::
    :sorted:

    muc_say
        - **message:** :py:class:`~sleekxmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered whenever the user sends a message to a :py:class:`~tabs.MucTab`.

    muc_say_after
        - **message:** :py:class:`~sleekxmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.MucTab` source

        Same thing than :term:`muc_say`, but after XHTML generation of the body, if needed.
        This means you must not insert any colors in the body in the handler, since
        it may lead to send invalid XML. This hook is less safe than ``muc_say`` and
        you should probably not need it.

    private_say
        - **message:** :py:class:`~sleekxmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.PrivateTab` source

        Triggered whenever the user sends a message to a :py:class:`~tabs.PrivateTab`.

    private_say_after
        - **message:** :py:class:`~sleekxmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.PrivateTab` source

        Same thing than :term:`private_say`, but after XHTML generation of the body, if needed.
        This means you must not insert any colors in the body in the handler, since
        it may lead to send invalid XML. This hook is less safe than :term:`private_say` and
        you should probably not need it.

    conversation_say
        - **message:** :py:class:`~sleekxmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.ConversationTab` source

        Triggered whenever the user sends a message to a :py:class:`~tabs.ConversationTab`.

    conversation_say_after:
        - **message:** :py:class:`~sleekxmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.ConversationTab` source

        Same thing than :term:`conversation_say`, but after XHTML generation of the body, if needed.
        This means you must not insert any colors in the body in the handler, since
        it may lead to send invalid XML. This hook is less safe than :term:`conversation_say` and
        you should probably not need it.

    muc_msg
        - **message:** :py:class:`~sleekxmpp.Message` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a message is received in a :py:class:`~tabs.MucTab`.

    private_msg
        - **message:** :py:class:`~sleekxmpp.Message` received
        - **tab:** :py:class:`~tabs.PrivateTab` source

        Triggered when a message is received in a :py:class:`~tabs.PrivateTab`.

    conversation_msg
        - **message:** :py:class:`~sleekxmpp.Message` received
        - **tab:** :py:class:`~tabs.ConversationTab` source

        Triggered when a message is received in a :py:class:`~tabs.ConversationTab`.

    conversation_chatstate
        - **message:** :py:class:`~sleekxmpp.Message` received
        - **tab:** :py:class:`~tabs.ConversationTab` source

        Triggered when a chatstate is received in a :py:class:`~tabs.ConversationTab`.

    muc_chatstate
        - **message:** :py:class:`~sleekxmpp.Message` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a chatstate is received in a :py:class:`~tabs.MucTab`.

    private_chatstate
        - **message:** :py:class:`~sleekxmpp.Message` received
        - **tab:** :py:class:`PrivateTab <tabs.PrivateTab>` source

        Triggered when a chatstate is received in a :py:class:`~tabs.PrivateTab`.

    normal_presence
        - **presence:** :py:class:`~sleekxmpp.Presence` received
        - **resource:**  :py:class:`Resource <str>` that emitted the :py:class:`~sleekxmpp.Presence`

        Triggered when a presence is received from a contact.

    muc_presence
        - **presence:** :py:class:`~sleekxmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a presence is received from someone in a :py:class:`~tabs.MucTab`.

    send_normal_presence
        - **presence:** :py:class:`~sleekxmpp.Presence` sent

        Triggered when before poezio sends a new :py:class:`~sleekxmpp.Presence` stanza.

    muc_join
        - **presence:** :py:class:`~sleekxmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when an user joins a :py:class:`~tabs.MucTab`

    muc_ban
        - **presence:** :py:class:`~sleekxmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when an user from a :py:class:`~tabs.MucTab`
        gets banned.

    muc_kicked
        - **presence:** :py:class:`~sleekxmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when an user from a :py:class:`~tabs.MucTab`
        gets kicked.

    muc_nickchange
        - **presence:** :py:class:`~sleekxmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when an user in a :py:class:`~tabs.MucTab` changes
        his nickname.

    ignored_private
        - **message**:py:class:`~sleekxmpp.Message` received
        - **tab:** :py:class:`~tabs.PrivateTab` source

        Triggered when a private message (that goes in a :py:class:`~tabs.PrivateTab`)
        is ignored automatically by poezio.

        **tab** is always ``None``, except when a tab has already been opened.
