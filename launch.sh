#!/bin/sh

if [ -d "$(dirname $0)/.git" ]
then
    args=$(git --git-dir="$(dirname $0)/.git" show --format='%h %ci' | head -n1)
else
    args="0.8.3-dev"
fi
exec python3 -OO "$(dirname $0)/src/poezio.py" -v "$args" "$@"

