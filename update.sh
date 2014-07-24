#!/bin/sh
# Use this script to Download or Update all dependances to their last
# developpement version.
# The dependances will be placed in the sources directory, so you do not
# need to install them on your system at all.

# Use launch.sh to start poezio directly from here

error() {
    echo -e "\033[1;31mThe script failed to update $1.\033[0m"
    echo -e "\033[1;31mPlease investigate.\033[0m"
    exit 1
}

echo 'Updating poezio'
git pull origin master || error poezio

make
if [ $? -ne 0 ]
then
    echo -e "It seems that you do not have the python development"\
        "files.\nSearch for a package named python3-dev or python3-devel"\
        "in your repos."
    exit -1
fi

if [ -e "slixmpp" ]
then
    echo "Updating slixmpp"
    cd slixmpp
    git pull || error slixmpp
    cd ..
else
    echo "Downloading slixmpp"
    git clone git://git.louiz.org/slixmpp || error slixmpp
fi

if [ -e ".dnspython.tgz" ]
then
    if [ -e "dnspython" ]
    then
        echo "dnspython up to date"
    else
        echo "Restoring dnspython"
        tar xfz .dnspython.tgz
        mv dnspython3-1.10.0 dnspython
    fi
else
    echo "Downloading dnspython"
    wget -c -q -O .dnspython.tgz http://www.dnspython.org/kits3/1.10.0/dnspython3-1.10.0.tar.gz || error dnspython
    rm -fr dnspython
    tar xfz .dnspython.tgz
    mv dnspython3-1.10.0 dnspython
fi

cd src
if [ -h "dns" ]
then
    echo 'Link src/dns already exists'
else
    echo "Creating link src/dns"
    ln -s ../dnspython/dns dns
fi
if [ -h "slixmpp" ]
then
    echo 'Link src/slixmpp already exists'
else
    echo "Creating link src/slixmpp"
    ln -s ../slixmpp/slixmpp slixmpp
fi
