#!/bin/bash

TEMP=`mktemp`
TEMP2=`mktemp`
TEMP3=`mktemp`

for n in `showres -n | grep -P 'STEP2' | awk '{print $1}' | grep -P '(a|b|c|d|e)n'`
do 
	check_node_ib_port.sh $n > $TEMP3 2>&1 &
	do_node_cmd power $n status | grep -v EXEC > $TEMP &
	ping -c 2 $n > /dev/null
	if [ $? -eq 1 ]; then
		echo "$n: NOT pingable"
	else
		echo "$n: pingable"
		pdsh -u 30 -w $n "uptime" > $TEMP2 2>&1 
		grep load $TEMP2 > /dev/null
		if [ $? -eq 0 ]; then
			cat $TEMP2
		else
			echo "$n: ssh FAILED"
		fi
	fi
	wait
	echo -n "$n: "
	cat $TEMP
	cat $TEMP3
done


rm -f $TEMP $TEMP2 $TEMP3
