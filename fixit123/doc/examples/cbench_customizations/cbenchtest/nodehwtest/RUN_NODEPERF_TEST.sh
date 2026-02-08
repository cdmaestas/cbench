#!/bin/bash

# get /apps/cbench environ
source /projects/sysapps/cbench/dotme.cbench

if [ -z $1 ]; then
	echo $0 NODENAME
	echo $0 bn196
	exit 1
fi

#$CBENCHOME-test/nodehwtest/nodehwtest_start_jobs.pl --batch --class 'cpu|memory|disk|topspin' --preamble '. $CBENCHOME/dotme.cbench' --ident breakfix --debug 1 --dryrun --nodelist $1
$CBENCHOME-test/nodehwtest/nodehwtest_start_jobs.pl --batch --match 'nodeperf' --preamble '. $CBENCHOME/dotme.cbench' --ident breakfix --iter 10 --batchargs "-q test" --nodelist $1

