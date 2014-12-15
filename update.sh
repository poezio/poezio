#!/bin/sh
# Use this script to download or update all dependencies to their last
# developpement version.
# The dependencies will be located in a virtualenv, so you do not
# need to install them on your system at all.

# Use launch.sh to start poezio directly from here

cd "$(dirname "$0")"
VENV="poezio-venv"
VENV_COMMAND="pyvenv"

echo 'Updating poezio'
git pull origin master || {
    echo "The script failed to update poezio."
    exit 1
}

if [ -e "$VENV" ]
then
    # In case of a python version upgrade
    echo 'Trying to upgrade the virtualenv'
    $VENV_COMMAND --upgrade "$VENV"

    . "$VENV/bin/activate"
    python3 -c 'import sys;(print("Python 3.4 or newer is required") and exit(1)) if sys.version_info < (3, 4) else exit(0)' || exit 1
    echo 'Updating the poezio dependencies'
    pip install -r requirements.txt --upgrade
    echo 'Updating the poezio plugin dependencies'
    pip install -r requirements-plugins.txt --upgrade
else
    echo "Creating the $VENV virtualenv"
    $VENV_COMMAND "$VENV"

    . "$VENV/bin/activate"
    cd "$VENV" # needed to download slixmpp inside the venv
    python3 -c 'import sys;(print("Python 3.4 or newer is required") and exit(1)) if sys.version_info < (3, 4) else exit(0)' || exit 1

    echo 'Installing the poezio dependencies using pip'
    pip install -r "../requirements.txt"
    echo 'Installing the poezio plugin dependencies using pip'
    pip install -r "../requirements-plugins.txt"
    cd ..
fi

make


if [ -e src/slixmpp ]
then
    echo ""
    echo "The update script detected a slixmpp link in src/."
    echo "This is probably due to the old update script, you should delete it"
    echo "so that poezio can use the up-to-date copy inside the poezio-venv directory."
    echo ""
fi
