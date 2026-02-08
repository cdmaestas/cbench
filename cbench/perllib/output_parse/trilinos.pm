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


package output_parse::trilinos;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /output_parse::(\S+)/;

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

	# process all the lines in the STDOUT buffer
	my $txtbuf = $bufrefs[0];

	my $status = 'NOTSTARTED';
	for my $l (@{$txtbuf}) {
		chomp $l;
		if ($l =~ /CBENCH NOTICE/) {
			$status = $l;
		}
		elsif ($l =~ /^Epetra Benchmark Test Version/) {
			$status = 'STARTED';
		}
		elsif ($l =~ /^MFLOP\/s/) {
			my $procs;
			(undef,$procs,$data{'SpMV'},$data{'SpMM2'},$data{'SpMM4'},$data{'SpMM8'},$data{'NORM'},$data{'DOT'},$data{'AXPY'}) =
				split /\s+/, $l;

			if (defined $data{'AXPY'}) {
				$status = 'SUCCESSFUL';
			} else {
				print STDERR "Error in trilinos output parser: MFLOP/s line without required fields...\n";
				$status = 'UNSUCCESSFUL';
			}
		}
	}

	if ($status =~ /SUCCESSFUL/) {
		$data{'STATUS'} = "PASSED";
	}
	elsif ($status =~ /UNSUCCESSFUL/) {
		$data{'STATUS'} = "FAILED VERIFICATION";
		$data{'SpMV'} = $data{'SpMM2'} = $data{'SpMM4'} = $data{'SpMM8'} = $data{'NORM'} = $data{'DOT'} = $data{'AXPY'} = 'NODATA';
	}
	elsif ($status =~ /CBENCH NOTICE/) {
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

	return 'epetra';
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
	%{$self->{METRIC_UNITS}} = qw/
									SpMV    MegaFlops
									SpMM2   MegaFlops
									SpMM4   MegaFlops
									SpMM8   MegaFlops
									NORM    MegaFlops
									DOT     MegaFlops
									AXPY    MegaFlops
								/;

	return 1;
}


1;
