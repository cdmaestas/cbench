# vim: syntax=perl tabstop=4
###############################################################################
#    Copyright (2005) Sandia Corporation.  Under the terms of Contract
#    DE-AC04-94AL85000 with Sandia Corporation, the U.S. Government retains
#    certain rights in this software
#
#    This file is part of Cbench.
#
#    Cbench is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    any later version.
#
#    Cbench is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Cbench; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

package parse_filter::misc;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /parse_filter::(\S+)/;

# This module contains custom parse filters that will optionally be
# employed by the Cbench output parsers when looking at job output.
# With these filters, the user can dynamically tell the output parsers
# to look for user-defined errors. These filters are only used when
# the --customparse parameter is given to the *_output_parse.pl scripts.
#
# Each filter is composed of a key/value pair.  The key is is a Perl
# regular expression including capturing. The value is a string that will
# be used to identify when an occurrence of the regex is found. The value
# can include the $1,$2,... etc variables that would be captured by
# the Perl regular expression
#
# The %parse_filter_include hash in cluster.def controls which parse
# filter modules are used by the output parsing engine.
#
# These parse filters are for miscellaneous things
our %parse_filters = (
	'CBENCH WARNING:\s+(.*)$' =>
		'CBENCH WARNING: $1',

	'HPL ERROR from process #\s*(\d+), on line' =>
		'HPL ERROR from process #$1',

	'\>\>\> \[.*\] Memory allocation failed for A, x and b.' =>
		'HPL Memory allocation failure',

	'\>\>\> Illegal input in file HPL.dat' =>
		'Illegal input in file HPL.dat',

	#Memory allocation failed. code position: set_buf 1. tried to alloc. 805306368 bytes
	'Memory allocation failed\..*tried to alloc.\s+(\d+)\s+bytes' =>
		'Memory allocation failed, tried to alloc $1 bytes',

# old quadrics RMS stuff
#	'prun: Error: .*: hostname (\S+) not in partition' =>
#		'PRUN says $1 not in partition',
#
#	prun: /usr/lib/rms/bin/pfloader (host n5 process 5 pid 1648) killed by signal 11 (SEGV)
#	'prun:.*\(host\s+(\S+)\s+process\s+\d+\s+pid\s+\S+\) killed by signal\s+(\d+)\s+\((\w+)\)' =>
#		'PRUN killed process on host $1 by signal $3',
#
#	prun: Error: request 40522 has been deallocate
#	'prun: Error: request\s+(\d+)\s+has been deallocated' =>
#		'PRUN says the job was deallocated by RMS (request $1)',

    # forrtl: error (78): process killed (SIGTERM)
	'forrtl\:\s+error\s+\((\S+)\)\:\s+process\s+killed\s+\((\S+)\)' =>
		'FORRTL: error $1, process killed via $2',

	# /projects/cbench-test-ompi121-intel/bin.goto-core2/npb/mg.C.4: error while loading shared libraries: libg2c.so.0: cannot open shared object file: No such file or directory
	'^(.*)\: error while loading shared libraries:\s+(\S+)\:\s+cannot open shared object file:(.*)$' =>
		'ERROR loading shared library: $2',

    # MX assertion
	#MX: assertion: <<Bailing out>>  failed at line 1125, file ./../mx__lib.c
	'MX: assertion: <<Bailing out>>  failed at line 1125, file ./../mx__lib.c' =>
		'MYRINET MX ASSERTION: <<Bailing out>>',
	
	# /var/spool/pbs/mom_priv/prologue: line 20: /apps/joblogs/352539.tbird-admin2: No such file or directory
	#cp: cannot create regular file `/apps/jobscripts/352539.tbir.SC': Permission denied
	#'No such file or directory' => 'No such file or directory',
	#'Permission denied' => 'Permission denied',
);


1;

