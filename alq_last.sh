#!/usr/bin/env bash

if [ -n "$1" ] && [ "$1" != "-h" ]; then
    if [ "$1" == "-n" ]; then
        sequence=$2
        numonly=1
    else
        sequence=$1
        numonly=0
    fi
    if [ -n $COOKIE ]; then
	    last=$(curl -X GET --cookie "$COOKIE" "http://factordb.com/sequences.php?se=1&aq='${sequence}'&action=last" | grep -A 2 Number | tail -n 1 | cut -d'>' -f 2 | cut -d'<' -f 1)
    else
        	    last=$(curl -X GET "http://factordb.com/sequences.php?se=1&aq='${sequence}'&action=last" | grep -A 2 Number | tail -n 1 | cut -d'>' -f 2 | cut -d'<' -f 1)
    fi
    if [ $numonly = "1" ]; then
        echo $last
    else
    	echo Last index is $last
    fi
else
    echo "Usage: ./alq_fast.sh [-n] SEQUENCE"
    echo ""
    echo "SEQUENCE is the sequence you want the last index of from the factordb."
    echo 'prints "last index is <index>" unless -n is included in which case it just prints the index.'
    echo 'Setting COOKIE will use the factordb cookie (if you have one) under API tab.'
fi
