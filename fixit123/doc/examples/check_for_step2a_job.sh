#!/bin/bash

if [ -z $1 ]; then
	echo $0 NODE
	exit 1
fi

TEMP=`mktemp`

qstat | grep "hwt-$1\." > $TEMP
if [ $? -eq 1 ]; then
	echo "$1 NO step2a"
else
	grep -q " R " $TEMP
	if [ $? -eq 0 ]; then
		echo "$1 RUNNING step2a"
	else
		echo "$1 QUEUED step2a"
	fi
fi

rm -f $TEMP
