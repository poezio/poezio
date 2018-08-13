.. _pyenv-install:

Installing python 3.5 as a user
-------------------------------

Building your own python 3
==========================

- Go to the `python download page`_
- Select the “Latest Python 3 Release”
- Download a tarball and extract it
- Run ``./configure && make`` (takes only a few minutes even on old CPUs)
- Edit the poezio launch.sh script to make it call your user-compiled python binary

Pyenv (x86/x86_64 only)
=======================

Pyenv_ is a useful script that allows you to install several python versions
in your user directory, and lets you manage which one you want depending on
the directory you are in. It is therefore useful for people who are on
distributions not providing the latest stable version, such as Debian or
CentOS.

You can follow the step-by-step `installation tutorial`_ on github that will
help you install it to your home directory (on step 5, you should use 3.7.0
which is the latest python release at the time of writing this page); or you
can use the `automated installer`_ and use ``pyenv install 3.7.0`` thereafter.

Then you only need to add a ``.python-version`` file containing ``3.7.0`` in
your poezio directory to make the python version in that directory default to
the python 3.7.0 installed with pyenv.


Other
=====

pythonz_ allows the same kind of version management as pyenv, but builds
from source instead of fetching precompiled binaries, so it allows more
control over what is going on.


.. _Pyenv: https://github.com/yyuu/pyenv
.. _installation tutorial: https://github.com/yyuu/pyenv#installation
.. _automated installer: https://github.com/yyuu/pyenv-installer
.. _python download page: https://www.python.org/downloads/source/
.. _pythonz: https://github.com/saghul/pythonz
