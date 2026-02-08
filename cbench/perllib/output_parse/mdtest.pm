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


package output_parse::mdtest;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /output_parse::(\S+)/;

=head1 NAME

mdtest

Cbench parse module responsible for parsing output files generated
Mdtest parallel io metatdata mpi test
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

    foreach (@bufrefs) {
		# process all the lines in the buffer
		my $txtbuf = $_;
		my $numlines = scalar @$txtbuf;

		foreach my $l (@{$txtbuf}) {
			($l =~ /CBENCH NOTICE/) and $status = $l;
			($l =~ /mdtest\S+ was launched/) and $status = "STARTED";

			($l =~ /SUMMARY:/) and $status = 'COMPLETED';

			#SUMMARY: (of 50 iterations)
			#   Operation                  Max        Min       Mean    Std Dev
			#   ---------                  ---        ---       ----    -------
			#   Directory creation:   9273.825   6788.107   8343.664    668.352
			#   Directory stat    :   5502.662   5106.717   5300.309     77.801
			#   Directory removal :   6128.883   5015.467   5705.629    263.386
			#   File creation     :   7412.247   6136.470   6833.696    292.678
			#   File stat         :   5517.454   5035.605   5261.947     99.959
			#   File removal      :   4813.524   4207.714   4505.605    125.475

			if ($l =~ /Directory creation\s*:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
				$data{'directory_create'} = $3;
			}
			elsif ($l =~ /Directory stat\s*:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
				$data{'directory_stat'} = $3;
			}
			elsif ($l =~ /Directory removal\s*:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
				$data{'directory_remove'} = $3;
			}
			elsif ($l =~ /File creation\s*:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
				$data{'file_create'} = $3;
			}
			elsif ($l =~ /File stat\s*:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
				$data{'file_stat'} = $3;
			}
			elsif ($l =~ /File removal\s*:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
				$data{'file_remove'} = $3;
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

    return 'gears';
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
		'directory_remove' => 'ops/sec',
		'file_remove' => 'ops/sec',
		'directory_stat' => 'ops/sec',
		'directory_create' => 'ops/sec',
		'file_create' => 'ops/sec',
		'file_stat' => 'ops/sec',
	);
	
	return 1;
}


1;
