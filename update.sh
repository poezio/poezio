#!/bin/bash

if [ -e "SleekXMPP" ]
then
    echo "Updating SleekXMPP"
    cd SleekXMPP
    git pull
    cd ..
else
    echo "Downloading SleekXMPP"
    git clone git://github.com/louiz/SleekXMPP.git
fi
if [ -e "dnspython" ]
then
    echo "Updating dnspython"
    cd dnspython
    hg pull -u
    cd ..
else
    echo "Downloading dnspython"
    hg clone http://hg.louiz.org/dnspython
fi

if [ ! -e "src/dns" ]
then
    echo "Creating link src/dns"
    ln -s src/dns dnspython/dns
fi
if [ ! -e "src/sleekxmpp" ]
then
    echo "Creating link src/sleekxmpp"
    ln -s src/sleekxmpp SleekXMPP/sleekxmpp
fi
