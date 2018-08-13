::

                          _
                         (_)
     _ __   ___   ___ _____  ___
    | '_ \ / _ \ / _ \_  / |/ _ \
    | |_) | (_) |  __// /| | (_) |
    | .__/ \___/ \___/___|_|\___/
    | |
    |_|

Homepage:      https://poez.io

Forge Page:    https://dev.poez.io

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

=======================
    Install
=======================

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

=======================
    Authors
=======================

- Florent Le Coz (louiz’) <louiz@louiz.org> (developer)
- Mathieu Pasquet (mathieui) <mathieui@mathieui.net> (developer)
- Emmanuel Gil Peyrot (Link Mauve) <linkmauve@linkmauve.fr> (developer)

=======================
    Contact/support
=======================

Jabber ChatRoom:   `poezio@muc.poez.io <xmpp:poezio@muc.poez.io?join>`_

Report a bug:      https://dev.poez.io/new

=======================
    License
=======================

Poezio is Free Software.
(learn more: http://www.gnu.org/philosophy/free-sw.html)

Poezio is released under the zlib License.
Please read the COPYING file for details.

The artwork logo was made by Gaëtan Ribémont and released under
the Creative Commons BY license (http://creativecommons.org/licenses/by/2.0/)


=======================
       Hacking
=======================

If you want to contribute, you will be welcome on
`poezio@muc.poez.io <xmpp:poezio@muc.poez.io?join>`_ to announce your
ideas, what you are going to do, or to seek help if you have trouble
understanding some of the code.

The preferred way to submit changes is through a public git repository.
But mercurial repositories or simple patches are also welcome.

For contributors having commit access:

This section explains how the git repository is organized.
The “master” branch is the branch where all recent development is made.  This is
the unstable version, which can be broken, but we should try to keep it usable
and crash-free as much as possible (so, never push to it if you are adding a
*known* crash).

New big features that take time to be complete should be developed in feature
branches (for example the “plugins” or the “opt” branches).
If it’s a really long feature, merge the “master” branch in that feature branch
from time to time, to avoid huge merges (and merge issues) when you’ll have to
merge your feature back in “master”.

Merge your work in master once it works and is usable, not necessarily when
it’s 100% finished.  Polishing and last bug fixes can take place in “master”.

Conflicts should be solved with *rebase* and not with merge.  This means
that if two developers commited one thing at the same time in their own
repository, the first pushes on the public public repos, and the other
has to pull before being able to push too.  In that case, the second
developer should use the rebase command instead of merge.  This avoids
creating unnecessary “branches” and visible merges.
On the contrary, when merging feature branches back to “master”, we should
use merge with the --no-ff tag (this makes sure the branch will always
distinctly appear in the logs), even if no conflict occured.

Finally, when a release is ready, we should merge the “master” branch
into the releases branch, then tag it to that version number.
If an “urgent” bugfix has to be made for a release (for example
a security issue is discovered on the last stable version, and
the current master has evolved too much to be released in the current
state), we create a new bugfix branch from the “releases” branch, we fix
it and finally merge it back to the “releases” branch, and tag it (and
we merge it to “master” as well, of course).


=======================
    Thanks
=======================

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
