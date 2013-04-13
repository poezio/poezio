Contributing
============

Conventions
-----------

We don’t have a strict set of conventions, but you should respect PEP8 mostly
(e.g. 4 spaces, class names in CamelCase and methods lowercased with
underscores) except if it means less-readable code (80 chars is often a hassle,
and if you look inside poezio you’ll see lots of long lines, mostly because of
strings).

As explained in the :ref:`overview`, “global” code goes in
:file:`core.py`, tab-related code goes in :file:`tabs.py`, and ui-related code goes in
:file:`windows.py`. There are other modules (e.g. :file:`xhtml.py`) but they do not matter
for the application as a whole.

Commit guidelines
-----------------

Commits **should** have a meaninful title (first line), and *may* have a detailed
description below. There are of course exceptions (for example, a single-line
commit that takes care of a typo right behind a big commit does not need to
say ``fix a typo ("azre" → "are") in toto.py line 45454``, since the metainfos
already take care of that.), but if you do not have commit access on the
poezio trunk, you can still reset and commit again.


Try to do atomic commits: since git is a DVCS, it doesn’t hurt to ``git add -p``
and split the commit into several meaningful small commits ; on the contrary,
it helps to track the changes on different levels.


If you have a conflict, solve it with rebase and not merge if the fast-forwards
do not resolve it automatically in your case. This helps to avoid creating
useless merges (and polluting the commit history) when none is needed.

.. code-block:: bash

    git fetch origin
    git rebase origin/master
    git push origin master

If your commit is related to an issue on our tracker_ (or fixes such an
issue), you can use ``Fix #BUGID`` or ``References #BUGID`` to help with the
tracking.


Getting your code into poezio
-----------------------------

If you have code you want to contribute, you can:

* Give us a patch and a description of what it does
* Give us a link to a **git** repo from which we can pull

The code is of course reviewed and tested a bit, but we trust the contributors
to submit good code. If we can’t integrate the given code into poezio (if it
crashes or has some issues), if the size is small, we may tweak it ourselves
and integrate it, and if not, you are of course free to take our advice into
account and submit it again.


If you have already submitted some code and plan to do more, you can ask us
 direct commit access on the main repo.

.. _tracker: https://dev.louiz.org/project/poezio/bugs
