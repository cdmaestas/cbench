#!/bin/bash

# get /apps/cbench environ
source /apps/cbench/dotme.cbench

if [ -z $1 ]; then
	echo $0 NODENAME
	echo $0 bn196
	exit 1
fi

if [ "$2" == "noquiet" ]; then
	EXTRA=""
else
	EXTRA="--quiet"
fi

#echo $CBENCHOME-test/nodehwtest/nodehwtest_output_parse.pl --ident breakfix --loadtarget $CBENCHOME-test/nodehwtest/cluster_target_values --match $1
$CBENCHOME-test/nodehwtest/nodehwtest_output_parse.pl --ident breakfix --loadtarget $CBENCHOME-test/nodehwtest/cluster_target_values $EXTRA --match "$1\."

