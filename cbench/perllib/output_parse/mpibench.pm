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


package output_parse::mpibench;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /output_parse::(\S+)/;

=head1 NAME

amg

Cbench parse module responsible for parsing output files generated
by the LLNL mpiBench collective benchmark from the Sequoia benchmarks
.

=cut

###############################################################
#
# Public methods
#

sub new {
	my $type = shift;
	my $self = {};
	bless $self, $type;
	$self->_init(@_) or return;

	return $self;
}


sub parse {
	my $self = shift;
	# a string identifying the file(s) we are parsing output from,
	# used mainly for printing out things
	my $fileid = shift;
	# should be one or more buffer references passed in,
	# they are ordered according to our very own FILE_LIST
	# array (see file_list() below)
	my @bufrefs = @_;

	my %data;

	my $status = 'NOTSTARTED';
	my $max = 0;

    foreach (@bufrefs) {
		# process all the lines in the buffer
		my $txtbuf = $_;
		my $numlines = scalar @$txtbuf;

		foreach my $l (@{$txtbuf}) {
			($l =~ /CBENCH NOTICE/) and $status = $l;
			($l =~ /START mpiBench/) and $status = "STARTED";
			($l =~ /END mpiBench/) and $status = 'COMPLETED';

			if ($l =~ /(\S+)\s+buffer corruption detected/) {
				$status = "BUFFER CORRUPTION";
			}

			# Bcast                   Bytes:    131072        Iters:     1000 Avg:    190.4283        Min:    189.7480 Max:    191.1101        Comm: MPI_COMM_WORLD    Ranks: 4
			if ($l =~ /^(\S+)\s+Bytes:\s+(\S+)\s+Iters:\s+(\d+)\s+Avg:\s+(\S+)\s+Min:\s+(\S+)\s+Max:\s+(\S+)\s+/) {
				main::debug_print(2,"DEBUG:$shortpackage.parse() tst=$1 bytes=$2 ave=$4 max=$6");

				# just one data point for Barrier
				# for the other collectives, grab the value at 8K
				if ($1 eq 'Barrier') {
					$data{$1} = $4;
				}
				else {
					($2 == 8192) and $data{$1} = $4;
				}
			}
		}
	}

	if ($status =~ /COMPLETED/) {
		$data{'STATUS'} = "PASSED";
	}
	elsif ($status =~ /CBENCH NOTICE/) {
		# this means the job was not an error, but did not
		# run because of some known non-error reason
		$data{'STATUS'} = 'NOTICE';
		(my $tmp = $status) =~ s/CBENCH NOTICE://;
        defined $main::diagnose and main::print_job_err($fileid,'NOTICE',$tmp);
	}
	else {
		$data{'STATUS'} = "ERROR($status)";
        defined $main::diagnose and main::print_job_err($fileid,'ERROR',$status);
	}

	return \%data;
}

sub name {
	my $self = shift;
	return $self->{NAME};
}

sub file_list {
	my $self = shift;

	return \@{$self->{FILE_LIST}};
}

sub alias_spec {
    my $self = shift;

    return 'mpibench(allreduce|bcast|barrier)';
}

sub metric_units {
	my $self = shift;

	return \%{$self->{METRIC_UNITS}};
}


###############################################################
#
# "Private" methods
#

sub _init {
	my $self = shift;

	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;

	# this is a KEY array... see the file_list method above for
	# more info
	@{$self->{FILE_LIST}} = qw/STDOUT/;

	# this is a KEY array... see the metric_units method above for
	# more info
	%{$self->{METRIC_UNITS}} = (
		'Allreduce-DOUBLE_MAX' => 'us',
		'Allreduce-DOUBLE_SUM' => 'us',
		'Allreduce-DOUBLE_MIN' => 'us',
		'Barrier' => 'us',
		'Allreduce-DOUBLE_SUM-3D' => 'us',
		'Allreduce-DOUBLE_MIN-3D' => 'us',
		'Allreduce-DOUBLE_MAX-3D' => 'us',
		'Bcast' => 'us',
	);
	
	return 1;
}


1;
