#!/bin/bash

function kill_children () {
	no_children=0
	if [ "$1" != "--verbose" ] ; then
		alias echo=true
	else
		shift
	fi
	if [ "$1" != "--KILL" ] ; then
		SIGNAL=-INT
	else
		SIGNAL=-KILL
	fi
	for i in `pstree -p $$ | sed 's/[a-z\+\`\(\)\|\.\/\-]/ /g'` ; do {
		if [ $i != $$ ] ; then {
			x=`ps --no-heading -f $i 2>&1`
			if [ "$?" -eq "0" ] ; then {
				echo Trying to destroy $i..
				echo $x
			} ; else {
				# false alarm
				continue
			} ; fi
			# There is a (winnable, I hope) race between the pstree command 
			# and the last kill where a PID might be reallocated to a 
			# process that is not part of the tree.  This is more likely 
			# using the random PID patch from getrewted.net.
	                kill $SIGNAL $i >> /dev/null 2>&1
			if [ "$?" -eq "0" ] ; then {
				echo "Subprocess $i terminated.."
				no_children=1
			} ; else {
				# There may situations in which a process died in between
				# when I looked for it and when I sent the signal.
				echo "Process $i was already dying."
			} ; fi
	        } ; fi
	} ; done
	unalias echo
	return $no_children
}
