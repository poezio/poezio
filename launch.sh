#!/bin/sh
cd $(dirname "$0")
if [ -z "$POEZIO_VENV" ]
then
    POEZIO_VENV="poezio-venv"
fi

if [ -e .git ]
then
    args=$(git show --format='%h %ci' | head -n1)
else
    args="0.9-dev"
fi

if [ -e "$POEZIO_VENV" ]
then
    PYTHON3="$POEZIO_VENV/bin/python3"
else
    echo ""
    echo "WARNING: Not using the up-to-date launch format"
    echo "Run ./update.sh again to create a virtualenv with the deps"
    echo "(or ignore this message if you don't want to)"
    echo ""
    PYTHON3=python3
fi

$PYTHON3 -c 'import sys;(print("Python 3.5 or newer is required") and exit(1)) if sys.version_info < (3, 5) else exit(0)' || exit 1
exec "$PYTHON3" -m poezio -v "$args" "$@"

