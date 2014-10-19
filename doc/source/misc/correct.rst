.. _correct-feature:

Message Correction
==================

Poezio implements the `XEP-0308`_
which allows the correction of the last message sent.

The corrections are signalled with a number append to the nick of the user, in
a different color.

.. figure:: ../images/correct.png
    :alt: Corrected message

The **9** here represents the number of times this message has been corrected.


You can show the revisions of a message by loading the
:ref:`displaycorrections-plugin` plugin, and you
can correct your own messages with the :term:`/correct` command.


.. note:: Please do not abuse of this feature, as it will simply be displayed as
            another plain message in the clients that do not support correction.

.. _XEP-0308: http://xmpp.org/extensions/xep-0308.html
