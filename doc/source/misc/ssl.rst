TLS in poezio
=============

.. _security settings:

Security of the connection
~~~~~~~~~~~~~~~~~~~~~~~~~~

Enabling or disabling TLS
-------------------------

Starting from version 0.8, poezio is configured to reject unencrypted connections
by default, in accordance to the `TLS manifesto`_. Users can still allow
unencrypted connections by setting the :term:`force_encryption` option to false.

If you cannot connect to your server, maybe it does not allow encrypted connections,
in which case you should reconfigure it if it is yours, or contact your admin
to let him know he should try to protect your privacy and credentials, at least
a little.


.. _ciphers:

Ciphers
-------

From the version 0.8, poezio offers the possibility to define your own set of
ciphers.

You can set this with the :term:`ciphers` option, the default for poezio being
``HIGH+kEDH:HIGH+kEECDH:HIGH:!PSK:!SRP:!3DES:!aNULL``.
You can check what ciphers are enabled by that list by running the command
``openssl ciphers -v 'cipher list'``. The default list prioritizes `Forward Secrecy`_
and does not have any cipher suite providing less than 128 bits of security.

You should change this if you either cannot connect to your server (but in this
case, you should notify the administrator that his XMPP server configuration
is probably not great), or if you want to be even more restrictive (only allowing
256 bits of security *and* forward secrecy, for example).

For example, gmail.com (and subsequent XMPP services) only support RC4-MD5 and RC4-SHA,
so you will want to set the option to ``RC4`` (or the default with ``:RC4`` appended,
just in case they upgrade their service, though that is very unlikely). Please consider
moving to a better XMPP service provider.

Certificate validation
~~~~~~~~~~~~~~~~~~~~~~

Starting from version 0.7.5, poezio offers some options to check the validity
of a X.509 certificate.

TOFU
----

The default handling method is the `TOFU/TUFU`_
method. At your first connection, poezio will save the hash of the certificate
received, and will compare the received one and the first one for the next
connections.


If you are paranoid (or run poezio for the first time in an unsafe
environment), you can set the :term:`certificate` value of your config file yourself
(the hash, colon-separated).


If the certificate is not the same, poezio will open a :ref:`confirmtab` and wait
for confirmation:

.. figure:: ../images/cert_warning.png
    :alt: Warning message

If you refuse, you will be disconnected.


CA-Based
--------

If you are connecting to a large server that has several front-facing
endpoints, you might be bothered by having to validate the change each time,
and you may want to check only if it the same authority delivered the
certificate.

You can then set the :term:`ca_cert_path` option to the path of a file
containing the validation chain in `PEM format`_ ; those certificates are
usually in /usr/share/ca-certificates/ but it may vary depending of your
distribution.

If the authority does not match when connecting, you should be disconnected.

None
----

If you do not want to bother with certificate validation at all (which can be
the case when you run poezio on the same computer as your jabber server), you
can set the :term:`ignore_certificate` value to true, and let the
:term:`ca_cert_path` option empty (or even remove it).

.. warning:: Only do this if you know what you are doing, or you will be open
            to Man in The Middle attacks!

.. _Forward Secrecy: https://en.wikipedia.org/wiki/Forward_secrecy
.. _TOFU/TUFU: https://en.wikipedia.org/wiki/User:Dotdotike/Trust_Upon_First_Use
.. _PEM format: https://tools.ietf.org/html/rfc1422.html
.. _TLS manifesto: https://github.com/stpeter/manifesto/blob/master/manifesto.txt
