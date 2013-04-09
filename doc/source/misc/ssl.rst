SSL Management
==============

Starting from version 0.7.5, poezio offers some options to check the validity
of a X.509 certificate.

TOFU
----

The default handling method is the `TOFU/TUFU`_
method. At your first connection, poezio will save the hash of the certificate
received, and will compare the received one and the first one for the next
connections.


If you are paranoid (or run poezio for the first time in an unsafe
environment), you can set the _certificate_ value of your config file yourself
(the hash, not colon-separated).


If the certificate is not the same, poezio will show an error message and wait
for confirmation:

.. figure:: ../images/ssl_warning.png
    :alt: Warning message

If you press y, the change is validated an poezio will match the next certs
with the accepted one.

If you press n, you will get the confirmation that the change has been
refused, and you will be disconnected.

CA-Based
--------

If you are connecting to a large server that has several front-facing
endpoints, you might be bothered by having to validate the change each time,
and you may want to check only if it the same authority delivered the
certificate.

You can then set the *ca_cert_path* option to the path of a file containing
the validation chain in `PEM format`_ ; those certificates are usually in
/usr/share/ca-certificates/ but it may vary depending of your distribution.


If the authority does not match when connecting, you should be disconnected.

None
----

If you do not want to bother with certificate validation at all (which can be
the case when you run poezio on the same computer as your jabber server), you
can set the *ignore_certificate* value to true, and let the *ca_cert_path*
option empty (or even remove it).

.. warning:: Only do this if you know what you are doing, or you will be open
            to Man in The Middle attacks!

.. _TOFU/TUFU: https://en.wikipedia.org/wiki/User:Dotdotike/Trust_Upon_First_Use
.. _PEM format: https://tools.ietf.org/html/rfc1422.html
