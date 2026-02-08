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

package parse_filter::openmpi;

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
# These parse filters are for OpenMpi (oooooooooompi)
our %parse_filters = (
	'\[.*\]\[.*\]\s+from\s+(\S+) to\:\s+(\S+)\s+error\s+polling.*with\s+status\s+(.*)status\s+number\s+(\d+)' =>
		'OMPI error \'$3\' with status $4 ($1 to $2)',

	'\[(\S+):.*\]\s+pls:(.*)$' =>
		'OMPI says \'$2\' on $1',

	'\[(\S+):.*\]\s+mca:.*component_find:\s+unable to open:\s+(\S+):' =>
		'OMPI could not load $2 on $1',

	'Signal:(\d+)\s+(.*)$' =>
		'OMPI saw Signal $1 ($2)' ,

	'An error occurred in MPI_Init' =>
		'OMPI says MPI_INIT failed',

	#[0,1,12][btl_openib_endpoint.c:1022:mca_btl_openib_endpoint_qp_init_query] error modifying QP to RTS errno
	#[0,1,24][btl_openib.c:808:mca_btl_openib_create_cq_srq] error creating low priority cq for mthca0 errno says Cannot allocate memory
	'\[\d+,\d+,\d+\]\[(\S+)\]\s+(.*)' =>
		'OMPI says \'$2\'',

	'Failed to find or execute the following executable' =>
		'OMPI says \'Failed to find or execute the executable',

	# orterun noticed that job rank 0 with PID 4696 on node slot1 exited on signal 4 (Illegal instruction).
	# orterun noticed that process rank 0 with PID 6075 on node n253 exited on signal 6 (Aborted).
	'orterun noticed that \S+ rank (\d+) with PID (\d+) on node (\S+) exited on\s+(.*)$' =>
		'OMPI says orterun noticed rank $1 on node $3 exited with $4',

	#orterun: killing job...
	'orterun: killing job' =>
		'OMPI says orterun killing job',

	#[sn251:07747] Error in ompi_mtl_mx_send, mx_wait returned something other than MX_STATUS_SUCCESS: mx_status (-1777530232).
	#'\[(\S+)\:\S+\] Error in ompi_mtl_mx_send,\s+mx_wait returned something other than MX_STATUS_SUCCESS: mx_status (\(.*\))' =>
	'\[(\S+)\:\S+\] Error in ompi_mtl_mx_send,\s+(.*)$' =>
		'OMPI says \'Error in ompi_mtl_mx_send on $1, $2\'',

	#[sn430:06846] *** An error occurred in MPI_Reduce_scatter
	#[sn430:06846] *** on communicator MPI COMMUNICATOR 3 SPLIT FROM 0
	#[sn430:06846] *** MPI_ERR_INTERN: internal error
	#[sn430:06846] *** MPI_ERRORS_ARE_FATAL (goodbye)
	'\[(\S+)\:\S+\] \*\*\* (An error occurred in.*)$' =>
		'OMPI says on node $1 \'$2\'',
	'\[(\S+)\:\S+\] \*\*\* (MPI_.*)$' =>
		'OMPI says on node $1 \'$2\'',

	# [sn405:29687] Error in mx_open_endpoint (error Failure querying MX driver(wrong driver?))
	'\[(\S+)\:\S+\] Error in mx_open_endpoint (\(.*\))' =>
		'OMPI says on node $1 \'Error in mx_open_endpoint $2\'',

	#[en65:07751] [0,1,15]-[0,1,14] mca_oob_tcp_peer_try_connect: connect to 10.100.128.225:35152 failed: Software caused connection abort (103)
	#[en65:07751] [0,1,15]-[0,1,14] mca_oob_tcp_peer_try_connect: connect to 10.100.128.225:35152 failed, connecting over all interfaces failed!
	'\[(\S+)\:\S+\].*(mca_oob_tcp_peer_try_connect:\s+connect to (\S+) failed:.*)$' =>
		'OMPI says on node $1 \'$2\'',

	# [tcompute2:32649] MPI_ABORT invoked on rank 0 in communicator MPI_COMM_WORLD with errorcode 1
	'\[(\S+)\:\S+\]\s+MPI_ABORT invoked on rank\s+(\S+)\s+in.*' =>
		'OMPI saw MPI_ABORT on node $1 (rank $2)',

	'There are not enough slots on the nodes' =>
		'OMPI says not enough slots on the nodes to run as requested',

	'There are not enough nodes in your allocation' =>
		'OMPI says not enough nodes to run as requested',

	# A daemon (pid unknown) died unexpectedly with status 0 while attempting to launch so we are aborting.
	'A daemon \(.+\) died unexpectedly with status (\d+) while attempting' =>
		'OMPI says a daemon died (status $1)',

	'Error name:\s+(\S+)' =>
		'OMPI saw error name $1',

	'A daemon \(pid \S+\) died unexpectedly on (signal\s+\d+)\s+while attempting to' =>
		'OMPI says a daemon died ($1)',
);

1;

