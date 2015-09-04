#!/bin/sh
# Use this script to download or update all dependencies to their last
# developpement version.
# The dependencies will be located in a virtualenv, so you do not
# need to install them on your system at all.

# Use launch.sh to start poezio directly from here

cd "$(dirname "$0")"
if [ -z "$POEZIO_VENV" ]
then
    POEZIO_VENV="poezio-venv"
fi

if [ -z "$POEZIO_VENV_COMMAND" ]
then
    POEZIO_VENV_COMMAND="pyvenv"
fi
command -v $POEZIO_VENV_COMMAND > /dev/null 2>&1 || {
    echo "'$POEZIO_VENV_COMMAND' executable not found. Check that you have python (>= 3.4) installed,"
    echo " and that \$POEZIO_VENV_COMMAND points to a valid virtualenv command."
    if [ "$POEZIO_VENV_COMMAND" = 'pyvenv' ]; then
        echo "If your distribution does not provide a 'pyvenv' command, maybe it has another name, like 'pyvenv-3.4'"
        echo 'Set the $POEZIO_VENV_COMMAND env variable to the name of that executable and this script will use it.'
    fi
    exit 1
}

echo 'Updating poezio'
git pull origin master || {
    echo "The script failed to update poezio."
    exit 1
}

if [ -e "$POEZIO_VENV" ]
then
    # In case of a python version upgrade
    echo 'Trying to upgrade the virtualenv'
    $POEZIO_VENV_COMMAND --upgrade "$POEZIO_VENV"
    $POEZIO_VENV_COMMAND --system-site-packages "$POEZIO_VENV"

    . "$POEZIO_VENV/bin/activate"
    echo 'Updating the in-venv pip'
    pip install --upgrade pip
    python3 -c 'import sys;(print("Python 3.4 or newer is required") and exit(1)) if sys.version_info < (3, 4) else exit(0)' || exit 1
    echo 'Updating the poezio dependencies'
    pip install -r requirements.txt --upgrade
    echo 'Updating the poezio plugin dependencies'
    pip install -r requirements-plugins.txt --upgrade
else
    echo "Creating the $POEZIO_VENV virtualenv"
    $POEZIO_VENV_COMMAND "$POEZIO_VENV"
    $POEZIO_VENV_COMMAND --system-site-packages "$POEZIO_VENV"

    . "$POEZIO_VENV/bin/activate"
    cd "$POEZIO_VENV" # needed to download slixmpp inside the venv
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
