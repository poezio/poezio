Using client certificates to login
==================================

Passwordless authentication is possible in XMPP through the use of mecanisms
such as `SASL External`_. This mechanism has to be supported by both the client
and the server. This page does not cover the server setup, but prosody has a
`mod_client_certs`_ module which can perform this kind of authentication, and
also helps you create a self-signed certificate.

Poezio configuration
--------------------

If you created a certificate using the above link, you should have at least
two files, a ``.crt`` (public key in PEM format) and a ``.key`` (private key
in PEM format).

You only have to store the files wherever you want and set :term:`keyfile`
with the path to the private key (``.key``), and :term:`certfile` with the
path to the public key (``.crt``).

Authorizing your keys
---------------------

Now your poezio is setup to try to use client certificates at each connection.
However, you still need to inform your XMPP server that you want to allow
those keys to access your account.

This is done through :term:`/cert_add`. Once you have added your certificate,
you can try to connect without a password by commenting the option.

.. note:: The :term:`/cert_add` command and the others are only available if
          your server supports them.

Next
----
Now that this is setup, you might want to use :term:`/certs` to list the
keys currently known by your XMPP server, :term:`/cert_revoke` or
:term:`/cert_disable` to remove them, and :term:`/cert_fetch` to retrieve
a public key.


.. _SASL External: http://xmpp.org/extensions/xep-0178.html
.. _mod_client_certs: https://code.google.com/p/prosody-modules/wiki/mod_client_certs
