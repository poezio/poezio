#!/bin/sh
poezio_dir=$(dirname "$0")
VENV="poezio-venv"

if [ -d "$poezio_dir/.git" ]
then
    args=$(git --git-dir="$poezio_dir/.git" show --format='%h %ci' | head -n1)
else
    args="0.8.3-dev"
fi

if [ -e "$poezio_dir/$VENV" ]
then
    PYTHON3="$poezio_dir/$VENV/bin/python3"
else
    echo ""
    echo "WARNING: Not using the up-to-date launch format"
    echo "Run ./update.sh again to create a virtualenv with the deps"
    echo "(or ignore this message if you don't want to)"
    echo ""
    PYTHON3=python3
fi

exec "$PYTHON3" "$poezio_dir/src/poezio.py" -v "$args" "$@"

