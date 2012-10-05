#!/bin/sh

if [ -d "$PWD/.git" ]
then
    args=$(git show --format='%h %ci' | head -n1)
else
    args="0.8-dev"
fi


exec python3 -OO src/poezio.py -v "$args" "$@"

