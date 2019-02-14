poezio
======

Homepage:      https://poez.io

Forge Page:    https://lab.louiz.org/poezio/poezio

Poezio is a console Jabber/XMPP client.  Its goal is to use anonymous
connections to simply let the user join MultiUserChats.  This way, the user
doesn't have to create a Jabber account, exactly like people are using
IRC.  Poezio's commands are designed to be (if possible) like commonly
used IRC clients (weechat, irssi, etc).

Since version 0.7, poezio can handle real Jabber accounts along with
roster and one-to-one conversations, making it a full-featured console
Jabber client, but still MultiUserChats-centered.
In the future, poezio should implement at a 100% level all XEP related to
MUCs, especially XEP 0045.

Install
=======

You need python 3.5 or higher (preferably the latest) and the associated devel
package, to build C modules, and the slixmpp python library.
You also need aiodns if you want SRV record support.

Additionally, you’ll need sphinx to build the documentation pages.
To read the documentation without these dependancies just read the rst
files in the doc/source/ directory or the generated documentation on the
website.

The simplest way to have up-to-date dependencies and to be able to test
this developement version is to use the ``update.sh`` script that downloads
them, places them in the right directory, and builds the C module.

You can then launch poezio with

::

    $ ./launch.sh

you can now simply launch ``poezio``

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
=======

- Florent Le Coz (louiz’) <louiz@louiz.org> (developer)
- Mathieu Pasquet (mathieui) <mathieui@mathieui.net> (developer)
- Emmanuel Gil Peyrot (Link Mauve) <linkmauve@linkmauve.fr> (developer)

Contact/support
===============

Jabber ChatRoom:   `poezio@muc.poez.io <xmpp:poezio@muc.poez.io?join>`_

Report a bug:      https://lab.louiz.org/poezio/poezio/issues/new

License
=======

Poezio is Free Software.
(learn more: http://www.gnu.org/philosophy/free-sw.html)

Poezio is released under the zlib License.
Please read the COPYING file for details.

The artwork logo was made by Gaëtan Ribémont and released under
the Creative Commons BY license (http://creativecommons.org/licenses/by/2.0/)


Hacking
=======

If you want to contribute, you will be welcome on
`poezio@muc.poez.io <xmpp:poezio@muc.poez.io?join>`_ to announce your
ideas, what you are going to do, or to seek help if you have trouble
understanding some of the code.

The preferred way to submit changes is through a merge request on gitlab,
at https://lab.louiz.org/poezio/poezio, but we also accept contributions
on github, or with a simple “please fetch my code on my personal git
repository hosted somewhere”


Thanks
======

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
