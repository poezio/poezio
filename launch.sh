#!/bin/sh
poezio_dir=$(dirname "$0")

if [ -d "$poezio_dir/.git" ]
then
    args=$(git --git-dir="$poezio_dir/.git" show --format='%h %ci' | head -n1)
else
    args="0.8.3-dev"
fi
exec python3 "$poezio_dir/src/poezio.py" -v "$args" "$@"

