Event Index
===========

The following events are poezio-only events, for Slixmpp events, check out
`their index <http://slixmpp.com/event_index.html>`_.

.. glossary::
    :sorted:

    highlight
        - **message:** :py:class:`~slixmpp.Message` that was received
        - **tab:** :py:class:`~tabs.MucTab` source of the event

    tab_change
        - **old_tab:** :py:class:`int` Old current tab.
        - **new_tab:** :py:class:`int` New current tab.

        Triggered whenever the user switches between tabs.

    muc_say
        - **message:** :py:class:`~slixmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered whenever the user sends a message to a :py:class:`~tabs.MucTab`.

    muc_say_after
        - **message:** :py:class:`~slixmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.MucTab` source

        Same thing than :term:`muc_say`, but after XHTML generation of the body, if needed.
        This means you must not insert any colors in the body in the handler, since
        it may lead to send invalid XML. This hook is less safe than ``muc_say`` and
        you should probably not need it.

    private_say
        - **message:** :py:class:`~slixmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.PrivateTab` source

        Triggered whenever the user sends a message to a :py:class:`~tabs.PrivateTab`.

    private_say_after
        - **message:** :py:class:`~slixmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.PrivateTab` source

        Same thing than :term:`private_say`, but after XHTML generation of the body, if needed.
        This means you must not insert any colors in the body in the handler, since
        it may lead to send invalid XML. This hook is less safe than :term:`private_say` and
        you should probably not need it.

    conversation_say
        - **message:** :py:class:`~slixmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.ConversationTab` source

        Triggered whenever the user sends a message to a :py:class:`~tabs.ConversationTab`.

    conversation_say_after:
        - **message:** :py:class:`~slixmpp.Message` that will be sent
        - **tab:** :py:class:`~tabs.ConversationTab` source

        Same thing than :term:`conversation_say`, but after XHTML generation
        of the body, if needed.  This means you must not insert any colors
        in the body in the handler, since it may lead to send
        invalid XML. This hook is less safe than :term:`conversation_say`
        and you should probably not need it.

    muc_msg
        - **message:** :py:class:`~slixmpp.Message` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a message is received in a :py:class:`~tabs.MucTab`.

    private_msg
        - **message:** :py:class:`~slixmpp.Message` received
        - **tab:** :py:class:`~tabs.PrivateTab` source

        Triggered when a message is received in a :py:class:`~tabs.PrivateTab`.

    conversation_msg
        - **message:** :py:class:`~slixmpp.Message` received
        - **tab:** :py:class:`~tabs.ConversationTab` source

        Triggered when a message is received in a :py:class:`~tabs.ConversationTab`.

    conversation_chatstate
        - **message:** :py:class:`~slixmpp.Message` received
        - **tab:** :py:class:`~tabs.ConversationTab` source

        Triggered when a chatstate is received in a :py:class:`~tabs.ConversationTab`.

    muc_chatstate
        - **message:** :py:class:`~slixmpp.Message` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a chatstate is received in a :py:class:`~tabs.MucTab`.

    private_chatstate
        - **message:** :py:class:`~slixmpp.Message` received
        - **tab:** :py:class:`PrivateTab <tabs.PrivateTab>` source

        Triggered when a chatstate is received in a :py:class:`~tabs.PrivateTab`.

    normal_presence
        - **presence:** :py:class:`~slixmpp.Presence` received
        - **resource:** :py:class:`Resource <str>` that emitted the :py:class:`~slixmpp.Presence`

        Triggered when a presence is received from a contact.

    muc_presence
        - **presence:** :py:class:`~slixmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a presence is received from someone in a
        :py:class:`~tabs.MucTab`.

    joining_muc
        - **presence:** :py:class:`~~slixmpp.Presence` to be sent

        Triggered when joining a MUC. The presence can thus be modified
        before being sent.

    changing_nick
        - **presence:** :py:class:`~~slixmpp.Presence` to be sent

        Triggered when the user changes his/her nickname on a MUC. The
        presence can thus be modified before being sent.

    send_normal_presence
        - **presence:** :py:class:`~slixmpp.Presence` sent

        Triggered when poezio sends a new :py:class:`~slixmpp.Presence`
        stanza. The presence can thus be modified before being sent.

    muc_join
        - **presence:** :py:class:`~slixmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a user joins a :py:class:`~tabs.MucTab`

    muc_ban
        - **presence:** :py:class:`~slixmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a user from a :py:class:`~tabs.MucTab`
        gets banned.

    muc_kick
        - **presence:** :py:class:`~slixmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a user from a :py:class:`~tabs.MucTab`
        gets kicked.

    muc_nickchange
        - **presence:** :py:class:`~slixmpp.Presence` received
        - **tab:** :py:class:`~tabs.MucTab` source

        Triggered when a user in a :py:class:`~tabs.MucTab` changes
        his nickname.

    ignored_private
        - **message**:py:class:`~slixmpp.Message` received
        - **tab:** :py:class:`~tabs.PrivateTab` source

        Triggered when a private message (that goes in a
        :py:class:`~tabs.PrivateTab`) is ignored automatically by poezio.

        **tab** is always ``None``, except when a tab has already been
         opened.
