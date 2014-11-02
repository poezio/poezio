#!/bin/sh
# Use this script to download or update all dependencies to their last
# developpement version.
# The dependencies will be located in a virtualenv, so you do not
# need to install them on your system at all.

# Use launch.sh to start poezio directly from here

cd "$(dirname "$0")"
VENV="poezio-venv"

echo 'Updating poezio'
git pull origin slix || {
    echo "The script failed to update poezio."
    exit 1
}

if [ -e "$VENV" ]
then
    # In case of a python version upgrade
    echo 'Trying to upgrade the virtualenv'
    pyvenv --upgrade "$VENV"

    source "$VENV/bin/activate"
    echo 'Updating the poezio dependencies'
    pip install -r requirements.txt --upgrade
    echo 'Updating the poezio plugin dependencies'
    pip install -r requirements-plugins.txt --upgrade
else
    echo "Creating the $VENV virtualenv"
    pyvenv "$VENV"

    source "$VENV/bin/activate"
    cd "$VENV" # needed to download slixmpp inside the venv

    echo 'Installing the poezio dependencies using pip'
    pip install -r "../requirements.txt"
    echo 'Installing the poezio plugin dependencies using pip'
    pip install -r "../requirements-plugins.txt"
    cd ..
fi

make
