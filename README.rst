poezio
======

.. image:: https://lab.louiz.org/poezio/poezio/-/raw/main/data/poezio_logo.svg
   :alt: Poezio logo
   :width: 200

|pipeline| |python versions| |license|

|discuss|

Homepage:      https://poez.io

Forge Page:    https://lab.louiz.org/poezio/poezio

Poezio is a console Jabber/XMPP client. The initial goal was to provide a
way of connecting easily to XMPP without the need for an account, exactly like
IRC clients. Poezio's commands are also designed to be close, if possible,
to the ones commonly used in IRC clients (weechat, irssi, etc).

For this reason, the experience is still centered around chatrooms, despite
poezio being a full-featured XMPP client for a very long while.

Install
-------

Packages
~~~~~~~~

The stable version of poezio is packaged in
`a number of GNU/Linux (and OpenBSD) distributions <https://doc.poez.io/install.html#poezio-in-the-gnu-linux-distributions>`_.


If it is not packaged in your distribution, you can run the
`flatpak <https://flathub.org/apps/details/io.poez.Poezio>`_ or use pip
to install the package from `Pypi <https://pypi.org/project/slixmpp/>`_.


From git
~~~~~~~~

`Documentation <https://doc.poez.io/install.html#install-from-source>`_


You need python 3.7 or higher (preferably the latest) and the associated devel
package, to build C modules, and the slixmpp python library.
You also need aiodns if you want SRV record support.

The easiest way to have up-to-date dependencies and to be able to test
this developement version is to use the ``update.sh`` script that downloads
them, places them in the right directory, and builds the C module.

You can then launch poezio with

::

    $ ./launch.sh


You can edit the configuration file which is located in
``~/.config/poezio/poezio.cfg`` by default, and you will have to copy
and edit ``data/default_config.cfg`` if you want to edit the config before
the first launch. The default config file is fully commented, but you can
also read the “Configuration” documentation page which has links between
options and longer descriptions.

Please see the online documentation for more information on installing,
configuring or using poezio: https://doc.poez.io/

If you still have questions, or if you're lost, don't hesitate to come
talk to us directly on our Jabber chat room (see Contact section).

Please DO report any bug you encounter and ask for any feature you want
(we may implement it or not, but it’s always better to ask).

Authors
-------

- Florent Le Coz (louiz’) <louiz@louiz.org> (developer)
- Mathieu Pasquet (mathieui) <mathieui@mathieui.net> (developer)
- Emmanuel Gil Peyrot (Link Mauve) <linkmauve@linkmauve.fr> (developer)
- Maxime Buquet (pep.) <pep@bouah.net> (developer)

Contact/support
---------------

Jabber chat room:   `poezio@muc.poez.io <xmpp:poezio@muc.poez.io?join>`_
(`web chat`_)

Report a bug:      https://lab.louiz.org/poezio/poezio/issues/new

License
-------

Poezio is Free Software.
(learn more: http://www.gnu.org/philosophy/free-sw.html)

Poezio is released under the zlib License.
Please read the COPYING file for details.

The artwork logo was made by Gaëtan Ribémont and released under
the `Creative Commons BY license <http://creativecommons.org/licenses/by/2.0/>`_.


Hacking
-------

If you want to contribute, you will be welcome on
`poezio@muc.poez.io <xmpp:poezio@muc.poez.io?join>`_ (`web chat`_)
to announce your ideas, what you are going to do, or to seek help if you have
trouble understanding some of the code.

The preferred way to submit changes is through a merge request on gitlab,
at https://lab.louiz.org/poezio/poezio, but we also accept contributions
on github, or with a simple “please fetch my code on my personal git
repository hosted somewhere”.


Thanks
------

- People:
    - Todd Eisenberger - Plugin system and OTR support
    - Jérôme Parment (Manfraid) - Code, testing
    - Akim Sadaoui - Code
    - Florian Duraffourg - Code
    - Frédéric Meynadier - Code
    - Georg Lukas - Code
    - Johannes Krude - Code
    - Łabędź - Code
    - Lasse Aagren - Code
    - Lancelot SIX - Code
    - Luke Marlin - Code
    - Maxime Buquet - Code
    - Nicolas Braud-Santoni - Code
    - Perdu - Code
    - Eijebong - Code
    - Gaëtan Ribémont - Logo design
    - Ovart - Testing
    - Koshie - Donation
    - Gapan - Makefile
    - FlashCode (weechat dev) - Useful advices on how to use ncurses efficiently
    - And all the people using and testing poezio, and especially the ones present
      on the jabber chatroom doing bug reports and/or feature requests.


.. |pipeline| image:: https://lab.louiz.org/poezio/poezio/badges/main/pipeline.svg

.. |python versions| image:: https://img.shields.io/pypi/pyversions/poezio.svg

.. |license| image:: https://img.shields.io/badge/license-zlib-blue.svg

.. |discuss| image:: https://inverse.chat/badge.svg?room=poezio@muc.poez.io
   :target: https://chat.jabberfr.org/converse.js/poezio@muc.poez.io

.. _web chat: https://chat.jabberfr.org/converse.js/poezio@muc.poez.io
