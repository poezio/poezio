Using several accounts
======================

Poezio does not support multi-accounts, and we do not plan to do so in a
foreseeable future. However, you can run several poezio instances (e.g. with
tmux or screen) to have similar functionnality.

You can specify a different configuration file than the default with:

.. code-block:: bash

    ./launch.sh -f separate_config.cfg


The relevant options for a separate config are the following:

* :term:`plugins_dir`: A different directory for the plugin sources (not _that_ useful)
* :term:`log_dir`: A different directory for logs
* :term:`plugins_conf_dir`: A different directory for plugin configurations

Those options are detailed in the *configuration page*.
