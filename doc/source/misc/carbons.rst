.. _carbons-details:

Message Carbons
===============

Starting from poezio 0.8, poezo now supports `message carbons`_.

Message carbons are useful to duplicate chat messages between several
connected devices, so that when you switch from one to another, you
don’t lose any message you sent or received.

To enable it, you only have to set the :term:`enable_carbons` option to ``true``.

.. note::

    This feature only duplicates *chat* messages (direct conversations between
    two JIDs), not groupchat messages or private conversations in groupchats.

.. _message carbons: http://xmpp.org/extensions/xep-0280.html
