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


package output_parse::hpcc;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /output_parse::(\S+)/;

=head1 NAME

hpcc

Cbench parse module responsible for parsing output files generated
by the HPC Challenge benchmark
.

=cut

###############################################################
#
# Public methods
#


=head1 PUBLIC METHODS

=over 4

=item B<new()> - Create a new parse object

  $obj = output_parse::->new();

=cut

sub new {
	my $type = shift;
	my $self = {};
	bless $self, $type;
	$self->_init(@_) or return;

	return $self;
}


=item B<parse()> - Responsible for actually parsing the output
contained in an output file and returning a hash reference with
the extracted data.

parse() takes a reference to a buffer (array) as the single input

  $obj = output_parse::hpcc->new();
  .
  read in an output file into @buf
  .
  $datahashref = $obj->parse(\@buf);
  for $k (keys %{$datahashref}) {
  print "$k => $datahashref->{$k}\n";
  }

The implementation of the parse() routine/method for a parse
module encompasses most of the work in creating a new
parse module.

=cut

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
	my $numlines = scalar @$txtbuf; 

    my $status = 'NOTSTARTED';
	my $found_endrecord = 0;
	my $key;
	my $fail = 0;
	my $start_time = 0;
	my $end_time = 0;
    foreach my $l (@{$txtbuf}) {
        ($l =~ /CBENCH NOTICE/) and $status = $l;
        
        ($l =~ /DARPA\/DOE HPC Challenge Benchmark/) and
			$status = 'STARTED';
		($l =~ /Begin of Summary section/) and $found_endrecord = 1 and
			$status = 'COMPLETED';

        if($l =~ /Current time \((\d+)\) is/) {
			if (!$start_time) {
				$start_time = $1;
			}
			else {
				$end_time = $1;
			}
		}

		$found_endrecord or next;
		
		if ($l =~ /HPL_Tflops=(\d+\.\d+)/) {
			$key = "hpl";
			$data{$key} = $1 * 1000;
		}
		elsif ($l =~ /StarDGEMM_Gflops=(\d+\.\d+)/) {
			$key = "EP-dgemm";
			$data{$key} = $1;
		}
		elsif ($l =~ /PTRANS_GBs=(\d+\.\d+)/) {
			$key = "ptrans";
			$data{$key} = $1;
		}
		elsif ($l =~ /MPIRandomAccess_GUPs=(\d+\.\d+)/) {
			$key = "G-RandomAccess";
			$data{$key} = $1;
		}
		elsif ($l =~ /StarSTREAM_Triad=(\d+\.\d+)/) {
			$key = "EP-stream_triad";
			$data{$key} = $1;
		}
		elsif ($l =~ /MPIFFT_Gflops=(\d+\.\d+)/) {
			$key = "G-ffte";
			$data{$key} = $1;
		}
		elsif ($l =~ /RandomlyOrderedRingBandwidth_GBytes=(\d+\.\d+)/) {
			$key = "randomring_bw";
			$data{$key} = $1;
		}
		elsif ($l =~ /RandomlyOrderedRingLatency_usec=(\d+\.\d+)/) {
			$key = "randomring_latency";
			$data{$key} = $1;
		}
		elsif ($l =~ /FAILED/) {
			$fail++;
		}
	}

	if ($end_time > $start_time) {
		$data{"runtime"} = ($end_time - $start_time)/60;
	}

	if ($status =~ /COMPLETED/ and $fail == 0) {
		$data{'STATUS'} = "PASSED";
	}
	elsif ($status =~ /COMPLETED/ and $fail > 0) {
		$data{'STATUS'} = "PARTIAL FAILED RESIDUALS";
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

=item B<name()> - Return the name of the parse module

For example: output_parse::xhpl

=cut

sub name {
	my $self = shift;
	return $self->{NAME};
}

=item B<files_list()> - Return the ordered array of file(s) we
want to parse

For example: ['STDOUT','STDERR'] or  ['STDOUT','hpccoutf.txt']

STDOUT and STDERR are keywords and not actual filenames. The
keywords are groked by the output parsing core code and handled
appropriately.

=cut

sub file_list {
	my $self = shift;

	return \@{$self->{FILE_LIST}};
}


=item B<alias_spec()> - Return a regex specification of benchmark names
we will parse in addition to our module name, i.e. 'hpcc'

This routine is optional.

=cut

#sub alias_spec {
#	my $self = shift;
#
#	return "";
#}

=item B<metric_units()> - Return a hash with a mapping of the
metrics this module returns to a string specifying the units
of the metric

=cut

sub metric_units {
	my $self = shift;

	return \%{$self->{METRIC_UNITS}};
}


###############################################################
#
# "Private" methods
#

=head1 PRIVATE METHODS

=over 4

=item B<_init> - parse arguments for B<new()>

Parse the arguments passed to B<new()> and sets the
appropriate object variables and such.

=cut

sub _init {
	my $self = shift;

	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;

	# this is a KEY array... see the file_list method above for
	# more info
	#@{$self->{FILE_LIST}} = qw/hpccoutf.txt.JOBID STDOUT/;
	@{$self->{FILE_LIST}} = qw/STDOUT hpccoutf.txt.JOBID/;

	# this is a KEY array... see the metric_units method above for
	# more info
	%{$self->{METRIC_UNITS}} = (
		'hpl' => 'GigaFlops',
		'EP-dgemm' => 'GigaFlops',
		'ptrans' => 'GB/s',
		'G-RandomAccess' => 'GUP/s',
		'EP-stream_triad' => 'GB/s',
		'G-ffte' => 'GigaFlops',
		'runtime' => 'minutes',
		'randomring_bw' => 'GB/s',
		'randomring_latency' => 'us',
	);
	
	return 1;
}


1;
