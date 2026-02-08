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


package output_parse::sqmr;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /output_parse::(\S+)/;

=head1 NAME

amg

Cbench parse module responsible for parsing output files generated
by the LLNL SQMR message rate benchmark from the Sequoia benchmarks
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
	my $err = 0;

    foreach (@bufrefs) {
		# process all the lines in the buffer
		my $txtbuf = $_;
		my $numlines = scalar @$txtbuf;

		foreach my $l (@{$txtbuf}) {
			($l =~ /CBENCH NOTICE/) and $status = $l;
			($l =~ /SQMR v1/) and $status = "STARTED";

			# sqmr doesn't have a good indication of being done...
			($l =~ /Cbench end timestamp/ and !$err) and $status = 'COMPLETED';

			if ($l =~ /(^ERROR .*)$/) {
				$err = 1;
				#$status = "SQMR said \'$1\'";
				$status = "SQMR ERROR";
			}

			#                            average               max                  min
			# msgsize iters time     msgs/sec MiB/sec     msgs/sec MiB/sec     msgs/sec MiB/sec
			#       0 10000  0.01   1781096.44    0.00   1781096.44    0.00   1781096.44    0.00
			if ($l =~ /(\S+)\s+(\S+)\s+(\d+\.\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
				main::debug_print(2,"DEBUG:$shortpackage.parse() sz=$1 ave=$4 max=$6");
				$max = main::max($max,$6);
			}
		}
	}

	if ($status =~ /COMPLETED/) {
		$data{'STATUS'} = "PASSED";
		$data{message_rate} = $max;
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

    return undef;
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
		'message_rate' => 'messages/s',
	);
	
	return 1;
}


1;
