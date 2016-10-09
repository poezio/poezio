.. _install:

Installing poezio
=================

.. warning:: Python 3.4 or above is **required**.
             To install it on a distribution that doesn't provide it, see :ref:`pyenv <pyenv-install>`.

poezio in the GNU/Linux distributions
-------------------------------------

As far as I know, Poezio is available in the following distributions, you just
have to install it by using the package manager of the distribution, if you're
using one of these.

- **Archlinux**: poezio_ and poezio-git_ packages are in the AUR
  (use your favourite AUR wrapper to install them)
- **Gentoo**: It’s uncertain, but the bgo-overlay_ appears to contain poezio
  and slixmpp packages.
- **Fedora**: The stable poezio package was out of date for a long time in
  Fedora, but now thanks to Casper, there is an `up-to-date package`_ in
  the repos since F19.
- **Debian**: A set of `development builds`_ are available for poezio and its
  dependencies; those are automatically generated (and most likely untested)
  packages. We welcome anyone willing to make proper ones.
- **Nix** (and **NixOS**): The last stable version of poezio is availalble in
  the unstable branch of `nixpkgs`. Use ``nix-env -f "<nixpkgs>" -iA poezio``
  to install poezio for the current user.
- **OpenBSD**: a poezio port_ is available

(If another distribution provides a poezio package, please tell us and we will
add it to the list)

Install from source
-------------------

Stable version
~~~~~~~~~~~~~~

`Stable version`_ packages are available in standalone (dependencies provided)
and poezio-only packages (both with prebuilt html doc for convenience).

Those versions are also available on pypi_ (using pip3, for example), and it is
recommended to install them this way if you absolutely want to **install** poezio
and your distribution provides no package.

Development version
~~~~~~~~~~~~~~~~~~~

The stable versions of poezio are more like snapshots of states of
development we deem acceptable. There is always an incentive to
use the development version, like new features, bug fixes, and more
support. Therefore, you might want to use the git version.

.. code-block:: bash

    git clone git://git.poez.io/poezio
    cd poezio

"""""""
General
"""""""

Poezio is a python3.4 (and above)-only application, so you will first need that.

Packages required for building poezio and deps:

- make
- gcc
- libidn and libidn-dev, only if you want to use cython_ (see below)
- python3-devel (or equivalent)
- python3-setuptools

Then you can run ``make`` to build it the poezio C extension module.
If you downloaded the standalone stable package, you are finished here and can skip
to :ref:`running poezio <poezio-run-label>`.

Poezio needs two libraries to run:

- aiodns_
- slixmpp_
- slixmpp can make use of cython_ to compile performance-critical modules and be faster

.. versionchanged:: 0.9


.. note:: We provide an ``update.sh`` script that creates a virtualenv and
          downloads all the required and optional dependencies inside it.
          we recommend using it with the git version of poezio, in order
          to keep everything up-to-date.

If you don’t want to use the update script for whatever reason, install the
following dependencies by hand; otherwise, skip to the
:ref:`installation part <poezio-install-label>`.


""""""""
slixmpp
""""""""

Poezio depends on slixmpp, a non-threaded fork of the SleekXMPP library.

.. code-block:: bash

    git clone git://git.poez.io/slixmpp
    python3 setup.py install --user


""""""
aiodns
""""""

The aiodns library is required in order to properly resolve XMPP domains (with SRV records).


.. code-block:: bash

    pip install --user aiodns

This will also install pycares, which aiodns uses.


""""""""
Building
""""""""

If you don’t run the ``update.sh`` script, you need to manually build the C
module used by poezio:

.. code-block:: bash

    make


.. _poezio-install-label:

Installation
~~~~~~~~~~~~

.. note::

    The update.sh + launch.sh method is the recommended way of using and upgrading
    the devel version of poezio. Installing should only be done with stable versions.
    And preferably using your distribution’s package manager.


If you skipped the installation of the dependencies and you only want to run
poezio without a system-wide install, do, in the :file:`poezio` directory:

.. code-block:: bash

    ./update.sh


.. note::

    You should probably install cython (for python3) on your system using your
    package manager, since the installation from pypi takes a long time.

.. note::

    If you want to use a custom directory for the virtualenv used by poezio,
    you can use the ``$POEZIO_VENV`` environment variable to set use
    another path (the default is :file:`poezio-venv`).

    If your distribution does not have a ``pyvenv`` symlink to the latest
    pyvenv available, you will need to set ``$POEZIO_VENV_COMMAND`` to it.
    For example, if you have python 3.4, you will need to set it to
    ``pyvenv-3.4`` instead.


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


If you did, it should be in the ``$PATH`` as ``poezio``, so run:

.. code-block:: bash

    poezio

.. _stable sources: https://dev.louiz.org/project/poezio/download
.. _slixmpp: https://dev.louiz.org/projects/slixmpp
.. _aiodns: https://github.com/saghul/aiodns
.. _poezio: https://aur.archlinux.org/packages/poezio/
.. _poezio-git: https://aur.archlinux.org/packages/poezio-git/
.. _up-to-date package: https://apps.fedoraproject.org/packages/poezio
.. _pypi: https://pypi.python.org/pypi/poezio
.. _development builds: http://dédié.jeproteste.info/poezio_debian/
.. _cython: http://cython.org
.. _bgo-overlay: https://bgo.zugaina.org/
.. _port: http://ports.su/net/poezio
