#!/bin/bash
#set -ex

# get /apps/cbench environ
source /projects/sysapps/cbench/dotme.cbench

if [ -z $1 ]; then
	echo $0 NODENAME
	echo $0 bn196
	exit 1
fi

$CBENCHOME-test/nodehwtest/nodehwtest_start_jobs.pl --batch --class 'cpu|memory|disk|topspin' --preamble '. $CBENCHOME/dotme.cbench' --ident breakfix --burnin --batchargs "-l walltime=16:00:00 -q step2" --nodelist $1
#$CBENCHOME-test/nodehwtest/nodehwtest_start_jobs.pl --batch --class 'cpu|memory|disk|topspin' --preamble '. $CBENCHOME/dotme.cbench' --ident breakfix --burnin --extraargs "-l walltime=04:00:00 -q diag" --nodelist $1

