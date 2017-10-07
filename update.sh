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

if [ -z "$POEZIO_PYTHON" ]
then
    POEZIO_PYTHON=python3
fi

command -v "$POEZIO_PYTHON" > /dev/null 2>&1 || {
    echo "Python executable '$POEZIO_PYTHON' not found."
    exit 1
}

$POEZIO_PYTHON -c 'import venv' &> /dev/null || {
    echo "'$POEZIO_PYTHON' venv module not found. Check that you have python (>= 3.4) installed,"
    exit 1
}

echo 'Updating poezio'
git pull --ff-only origin master || {
    echo "The script failed to update poezio."
    exit 1
}

if [ -e "$POEZIO_VENV" ]
then
    # In case of a python version upgrade
    echo 'Trying to upgrade the virtualenv'
    $POEZIO_PYTHON -m venv --upgrade "$POEZIO_VENV"
    $POEZIO_PYTHON -m venv --system-site-packages "$POEZIO_VENV"

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
    $POEZIO_PYTHON -m venv "$POEZIO_VENV"
    $POEZIO_PYTHON -m venv --system-site-packages "$POEZIO_VENV"

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
