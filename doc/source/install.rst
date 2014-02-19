Installing poezio
=================

.. important:: Python 3.3 or better is highly recommended, as we do not
    officially support python 3.1 (although we do try to keep things running),
    and python 3.2 has some unfixable issues.

poezio in the GNU/Linux distributions
-------------------------------------

As far as I know, Poezio is available in the following distributions, you just
have to install it by using the package manager of the distribution, if you're
using one of these.

- *Archlinux*: A poezio_ and poezio-git_ packages are in AUR (use your favourite
    AUR wrapper to install them)
- *Gentoo*: `Sekh’s overlay`_ contains everything required to build poezio
    (sleekxmpp, dnspython, and poezio)
- *Fedora*: The poezio package was out of date for a long time in Fedora, but
    now thanks to Casper, there is an `up-to-date package`_ in the repos since F19.
- *Debian*: Use an other distro. (or make a package, we can provide help :) )

(If another distribution provides a poezio package, please tell us and we will
add it to the list)

Install from source
-------------------

.. note:: The ``make`` command is always required, because while we could provide
    the compiled file into the archive, the ABI changes and platform variety would
    make it sure that the list of archives is either incomplete or wrong.

    Packagers are of course welcome to compile the file and include it in their
    architecture-specific and fixed-python packages.


Stable version
~~~~~~~~~~~~~~

`Stable version`_ packages are available in standalone (included dependencies)
and poezio-only packages (both with prebuilt html doc for convenience).


Development version
~~~~~~~~~~~~~~~~~~~

The stable versions of poezio are more like snapshots of states of
development we deem acceptable. There is always an incentive to
use the development version, like new features, bug fixes, and more
support. Therefore, you might want to use the git version.

.. code-block:: bash

    git clone git://git.poez.io/poezio
    cd poezio

Dependencies
~~~~~~~~~~~~

"""""""
General
"""""""

Poezio is a python3-only application, so you will first need that, preferably
in the latest available version, down to 3.2.

.. note:: Python 3.1 is not officially supported and tested, but should
    work (if it doesn’t, we can fix it if the fix does not require ugly
    modifications). In this case, you will want to install the
    python3-argparse package if it exists, or use pip3/virtualenvs to
    install it.

You will first need python3-devel, or whatever your distribution named it, along
with standard utilities such as make. Once you have them, you can run ``make``
to build the only part of poezio that needs it. If you downloaded the standalone
stable package, you are finished here and can skip to :ref:`running poezio <poezio-run-label>`.

Poezio depends on two libraries:

- DNSPython_ (the python3 version, often called dnspython3)
- SleekXMPP_

If you do not want to install those libraries, you can skip directly to
the :ref:`installation part <poezio-install-label>`


"""""""""
DNSPython
"""""""""

It should be available right now in most software repositories, under the name
``python3-dnspython`` or ``python3-dnspython3``. Any stable version should fit.

For a manual install:

.. code-block:: bash

    wget -O dnspython.tar.gz http://www.dnspython.org/kits3/1.11.1/dnspython3-1.11.1.tar.gz
    tar xvf dnspython.tar.gz
    cd dnspython3-1.11.1
    python3 setup.py build
    python3 setup.py install --user

"""""""""
SleekXMPP
"""""""""

Poezio now depends on SleekXMPP 1.2. if your distribution does not provide it yet,
you can install it this way:

.. code-block:: bash

    wget https://github.com/fritzy/SleekXMPP/archive/1.2.0.tar.gz
    tar xvf 1.2.0.tar.gz
    SleekXMPP-1.2.0
    python3 setup.py build
    python3 setup.py install --user


.. _poezio-install-label:

Installation
~~~~~~~~~~~~

.. note::

    The update.sh + launch.sh method is the recommended way of using and upgrading
    the devel version of poezio. Installing should only be done with stable versions.


If you skipped the installation of the dependencies and you only want to run
poezio without a system-wide install, do, in the :file:`poezio` directory:

.. code-block:: bash

    ./update.sh

If you have git installed, it will download and update locally the
libraries for you. (and if you don’t have git installed, install it)


If you really want to install it, run as root (or sudo in ubuntu or whatever):

.. code-block:: bash

    make install


.. _poezio-run-label:

Running
~~~~~~~

If you didn’t install poezio, you can run it from the source directory
with:

.. code-block:: bash

    ./launch.sh


If you did, it should be in he ``$PATH`` as ``poezio``, so run:

.. code-block:: bash

    poezio

.. _Sekh’s overlay: https://github.com/sekh/sekh_overlay
.. _stable sources: https://dev.louiz.org/project/poezio/download
.. _SleekXMPP: https://github.com/fritzy/SleekXMPP/
.. _DNSPython: http://www.dnspython.org/
.. _poezio: https://aur.archlinux.org/packages/poezio/
.. _poezio-git: https://aur.archlinux.org/packages/poezio-git/
.. _up-to-date package: https://apps.fedoraproject.org/packages/poezio
