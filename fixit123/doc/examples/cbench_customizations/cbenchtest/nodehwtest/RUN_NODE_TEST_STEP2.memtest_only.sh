#!/bin/bash
#set -ex

# get /apps/cbench environ
source /projects/sysapps/cbench/dotme.cbench

if [ -z $1 ]; then
	echo $0 NODENAME
	echo $0 bn196
	exit 1
fi

#$CBENCHTEST/nodehwtest/nodehwtest_start_jobs.pl --batch --class 'memory' --preamble '. $CBENCHOME/dotme.cbench' --ident breakfix --burnin --batchargs "-l walltime=12:00:00 -q step2" --nodelist $1

$CBENCHTEST/nodehwtest/nodehwtest_start_jobs.pl --batch --class 'memory' --preamble '. $CBENCHOME/dotme.cbench' --ident breakfix --burnin --batchargs "-l walltime=12:00:00 -q step2" --nodelist $1

