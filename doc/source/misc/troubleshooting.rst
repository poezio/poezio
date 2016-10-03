Troubleshooting
===============

I cannot connect.
-----------------

1. Check that you are still connected to the internet.
2. Double-check your credentials.
3. Check the :ref:`security settings <security settings>`, maybe your server does not support encryption, or only with weak parameters (like gmail).
4. Maybe your DNS are wrong, try setting the :term:`custom_host` option with the server IP.
5. Overzealous firewall?
6. Running poezio with -d file.txt (debug mode) might reveal your issues.
7. Come see us from the `web client`_ to discuss your issues further.


The outline of poezio is not displayed and unicode characters are broken
------------------------------------------------------------------------
We believe we (or unrelated people) have reported the bug of python3 compiled against the wrong
ncurses to every_ significant_ distribution_ `out there`_, but if there is still
one with it, please go ahead and report it.

Poezio tracebacks with weird encoding errors
--------------------------------------------
Please check your locale for utf-8 compatibility.

Python is too heavy
-------------------
We know. It’s too late to change that. If you are running your XMPP client on a toaster,
please try mcabber_.


Other issues
------------
Some things may appear in ``$XDG_DATA_HOME/poezio/logs/errors.log``. (or a user-defined :term:`log_dir`/errors.log)


.. _web client: https://jappix.com/?r=poezio@muc.poez.io
.. _mcabber: http://mcabber.com/
.. _every: https://bugs.mageia.org/show_bug.cgi?id=2156
.. _significant: https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=602720
.. _distribution: https://bugzilla.redhat.com/show_bug.cgi?id=539917
.. _out there: https://bugs.launchpad.net/ubuntu/+source/python3.2/+bug/789732
