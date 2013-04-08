Installing Poezio
=================


.. important:: Python 3.2 or better is highly recommended, as we do not
    officially support python 3.1 (although we do try to keep things running).

Poezio in the GNU/Linux distributions
-------------------------------------

As far as I know, Poezio is available in the following distributions, you just
have to install it by using the package manager of the distribution, if you're
using one of these.

- *Archlinux*: A poezio and poezio-git packages are in AUR (use your favourite
    AUR wrapper to install them)
- *Gentoo*: `Sekh’s overlay`_ contains everything required to build poezio
    (sleekxmpp, dnspython, and poezio)
- *Debian*: Use an other distro. (or make a package, we can provide help :) )

(If an other distribution provides a poezio package, please tell us and we will
 add it to the list)

Install poezio from the sources
-------------------------------

You can download poezio's `stable sources`_, or fetch the development
version (trunk), using git:

.. code-block:: bash

    git clone https://git.louiz.org/poezio

.. note:: To clone the repo, which uses a self-signed certificated, you can
    prefix the clone command with GIT_SSL_NO_VERIFY=1.

In order for poezio to correctly work, you need the libs SleekXMPP and
 dnspython. You can install them by downloading it from the `SleekXMPP`_
 page and the `dnspython`_ page , but you'll need the development
 version of SleekXMPP. Alternatively, you can download poezio's sources
 including SleekXMPP and dnspython, that's the easier way.

""""""""""""
Dependencies
""""""""""""

.. note:: If your python3 version is too old because of debian (e.g. < 3.2), you
    should install the python3-argparse package if it exists, or use
    pip3/virtualenvs to install it.

If you want to install SleekXMPP and dnspython by yourself, use the following
instructions. Else, go to the :ref:`next section <poezio-install-label>` (recommended).


Download SleekXMPP

.. code-block:: bash

    git clone git://github.com/fritzy/SleekXMPP.git

Make sure you're using the develop branch by typing

.. code-block:: bash

    cd SleekXMPP
    git checkout develop

Install SleekXMPP with

.. code-block:: bash

    python3 setup.py build
    su -c "python3 setup.py install"

Install the dnspython3 package on your distribution or install it manually:

.. code-block:: bash

    wget -O dnspython.tgz http://www.dnspython.org/kits3/1.10.0/dnspython3-1.10.0.tar.gz
    tar xvf dnspython.tgz
    cd dnspython3-1.10.0

And do the same again:

.. code-block:: bash

    python3 setup.py build
    su -c "python3 setup.py install"

.. _poezio-install-label:

"""""""""""""""""""
Poezio installation
"""""""""""""""""""

If you skipped the installation of the dependencies and you only want to test
poezio without a system-wide install, do, in the *poezio* directory:

.. code-block:: bash

    ./update.sh

If you have git installed, it will download and update locally the
 libraries for you. (and if you don’t have git installed, install it)


If you don't want to install poezio but just test it (or keep a development
 version), do:

.. code-block:: bash

    ./launch.sh

To install poezio, do, as root (or sudo with ubuntu or whatever):

.. code-block:: bash

    make install

And then start it with:

.. code-block:: bash

    poezio

.. _Sekh’s overlay: https://github.com/sekh/sekh_overlay
.. _stable sources: https://dev.louiz.org/project/poezio/download
.. _SleekXMPP: https://github.com/fritzy/SleekXMPP/
.. _dnspython: http://www.dnspython.org/
