#!/bin/sh
python3 -c 'import sys;(print("Python 3.4 or newer is required") and exit(1)) if sys.version_info < (3, 4) else exit(0)' || exit 1
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

