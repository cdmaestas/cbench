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


package output_parse::com;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /output_parse::(\S+)/;

=head1 NAME

com

Cbench parse module responsible for parsing output files generated
by the LLNL Presta 'com' benchmark
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

	# we actually handle two generations of com versions now. the newer versions 
	# have more variable output making the parsing more complicated
	my $comversion = 'original';

	# process all the lines in the STDOUT buffer
	my $txtbuf = $bufrefs[0];
	my $numlines = scalar @$txtbuf; 

    my $status = 'NOTSTARTED';
	my $found_endrecord = 0;
	my $table = '';
	my $sawsummary = 0;

    foreach my $l (@{$txtbuf}) {
        ($l =~ /CBENCH NOTICE/) and $status = $l;
        if ($l =~ /Unidirectional and Bidirectional Communication Test/) {
			# original com version output looks like
			$status = 'STARTED';
		}
        elsif ($l =~ /com Point-to-Point MPI Bandwidth and Latency Benchmark/) {
			# newer com version output looks like
			$comversion = 'new';
			$status = 'STARTED';
			main::debug_print(2,"DEBUG:$shortpackage.parse() newer com version");
		}

		if ($comversion =~ 'orig') {
			($l =~ /Max Unidirectional/) and $found_endrecord = 1 and
				$status = 'COMPLETED';
			$found_endrecord or next;
			
			if ($l =~ /Max Unidirectional.*\:\s+(\d+\.\d+)\s+for.*/) {
				$data{'unidir_bw'} = $1;
			}
			if ($l =~ /Max  Bidirectional.*\:\s+(\d+\.\d+)\s+for.*/) {
				$data{'bidir_bw'} = $1;
			}
		}
		elsif ($comversion =~ 'new') {
			# Unidirectional Test Results
			# (tasks, size, ops/sample, samples) : min/mean/max
			# --------------------------------------------------------------------------------
			# (     2,      32,   100,     1):         4.024 /        4.024 /        4.024
			# ...
			# Summary  :         min/mean/max =       41.442 /     1977.469 /     6352.254

			# new test result table
			if ($l =~ /(\S+) Test Results/) {
				$table = $1;
				$sawsummary = 0;
				main::debug_print(2,"DEBUG:$shortpackage.parse() result table $table");
			}

			# Summary data line
			if ($l =~ /Summary\s+:\s+\S+\s+=\s+(\S+)\s+\/\s+(\S+)\s+\/\s+(\S+)\s+/) {
				$sawsummary = 1;
				main::debug_print(2,"DEBUG:$shortpackage.parse() table $table summary: $1 $2 $3");
				$data{"min_$table"} = $1;
				
				# if this is a NOT a latency result table record the mean/max
				if ($table !~ /Latency/) {
					$data{"ave_$table"} = $2;
					$data{"max_$table"} = $3;
				}
			}

			# catch the 8 byte latency for the job numprocs
			if ($table =~ /Latency/ and
				$l =~ /\(\s+$main::np,\s+8,\s+\S+,\s+\S+\):\s+(\S+)\s+\/\s+(\S+)\s+\/\s+(\S+)\s+/) {
				main::debug_print(2,"DEBUG:$shortpackage.parse() table $table 8byte @ $main::np procs is $1");
				$data{"8byte_$table"} = $1;
			}

			# a Summary line followed closely by a ######### line means the
			# test ended normally
			if ($l =~ /################################/ and $sawsummary) {
				$found_endrecord = 1;
				$status = 'COMPLETED';
				main::debug_print(2,"DEBUG:$shortpackage.parse() com exited normally");
			}
		}
	}

	if ($status =~ /COMPLETED/) {
		$data{'STATUS'} = "PASSED";
	}
	elsif ($status =~ /CBENCH NOTICE/) {
		# this means the job was not an error, but did not
		# run because the benchmark does not support running
		# on an odd number of processors
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
		'unidir_bw' => 'MB/s',
		'bidir_bw' => 'MB/s',
		'ave_UnidirAsync' => 'MB/s',
		'min_BidirAsync' => 'MB/s',
		'max_BidirAsync' => 'MB/s',
		'min_UnidirAsync' => 'MB/s',
		'ave_BidirAsync' => 'MB/s',
		'max_UnidirAsync' => 'MB/s',
		'max_Unidirectional' => 'MB/s',
		'max_Bidirectional' => 'MB/s',
		'ave_Unidirectional' => 'MB/s',
		'min_Unidirectional' => 'MB/s',
		'min_Bidirectional' => 'MB/s',
		'ave_Bidirectional' => 'MB/s',
		'min_Latency' => 'us',
		'8byte_Latency' => 'us',
	);
	
	return 1;
}


1;
