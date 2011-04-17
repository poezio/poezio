#!/bin/bash
# Use this script to Download or Update all dependances to their last
# developpement version.
# The dependances will be placed in the sources directory, so you do not
# need to install them on your system at all.

# Use launch.sh to start poezio directly from here

echo 'Updating poezio'
hg pull -u

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

if [ -h "src/dns" ]
then
    echo 'Link src/dns already exists'
else
    echo "Creating link src/dns"
    ln -s dnspython/dns src/dns
fi
if [ -h "src/sleekxmpp" ]
then
    echo 'Link src/sleekxmpp already exists'
else
    echo "Creating link src/sleekxmpp"
    ln -s SleekXMPP/sleekxmpp src/sleekxmpp
fi
