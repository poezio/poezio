#!/bin/bash
# Use this script to Download or Update all dependances to their last
# developpement version.
# The dependances will be placed in the sources directory, so you do not
# need to install them on your system at all.

# Use launch.sh to start poezio directly from here

echo 'Updating poezio'
git pull

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

cd src
if [ -h "dns" ]
then
    echo 'Link src/dns already exists'
else
    echo "Creating link src/dns"
    ln -s ../dnspython/dns dns
fi
if [ -h "sleekxmpp" ]
then
    echo 'Link src/sleekxmpp already exists'
else
    echo "Creating link src/sleekxmpp"
    ln -s ../SleekXMPP/sleekxmpp sleekxmpp
fi
