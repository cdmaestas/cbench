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


package output_parse::xhpl2;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /output_parse::(\S+)/;

=head1 NAME

xhpl

Cbench parse module responsible for parsing output files generated
by the xhpl2, i.e. HP Linpack 2.0, benchmark
.

=cut

###############################################################
#
# Public methods
#


=head1 PUBLIC METHODS

=over 4

=item B<new()> - Create a new parse object

  $obj = output_parse::xhpl->new();

=cut

sub new {
	my $type = shift;
	my $self = {};
	bless $self, $type;
	$self->_init(@_) or return;

	return $self;
}


=item B<alias_spec()> - Return a regex specification of benchmark names
we will parse in addition to our module name, i.e. 'xhpl'

This routine is optional.

=cut

sub alias_spec {
    my $self = shift;

    return "xhpl2-.*";
}


=item B<parse()> - Responsible for actually parsing the output
contained in an output file and returning a hash reference with
the extracted data.

parse() takes a reference to a buffer (array) as the single input

  $obj = output_parse::xhpl->new();
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

	# strip the buffer of stderr output that can show up non-deterministically
	# in the output stream and confuses the assumptions during parsing
	my @cleanbuf = ();
	foreach (@{$bufrefs[0]}) {
		/memfree\s+=\s+\d+\s+/ and next;
		push @cleanbuf, $_;
	}

	# process all the lines in the STDOUT buffer
	my $txtbuf = \@cleanbuf;
	my $numlines = scalar @$txtbuf; 

	# NOTE: The linpack output file can have multiple results within it.
	#       We want to grab the maximum PASSED result from the file. We
	#       will only record the linpack data into the final data hash
	#       if all results within the file PASSED residual checks.
    my $status = 'NOTSTARTED';
    my $found_result = 0;
	my $found_endrecord = 0;
    my $i = 0;
	my $gflops = 'NODATA';
	my $numpassed = 0;
	my $numfailed = 0;
	my $local_max_gflops = 0.0;
	my $local_total_tests = 'nodata1';
	my $local_passed_tests = 'nodata2';
	my $local_failed_tests = 'nodata3';
	my $total_time = 0;
    while ($i < $numlines) {
        ($txtbuf->[$i] =~ /matrix A is randomly generated/) and $status = 'STARTED';
        
        ($txtbuf->[$i] =~ /CBENCH NOTICE/) and $status = $txtbuf->[$i];

		#HPL ERROR from process # 0, on line 170 of function HPL_pdtest:
		#>>> [39,47] Memory allocation failed for A, x and b. Skip. <<<
        ($txtbuf->[$i] =~ /Memory allocation failed/) and $status = 'ALLOCFAILURE';

		#HPL ERROR from process # 0, on line 621 of function HPL_pdinfo:
		#>>> Illegal input in file HPL.dat. Exiting ... <<<
        #($txtbuf->[$i] =~ /Illegal input/) and $status = 'INPUTFAILURE';
        ($txtbuf->[$i] =~ /Illegal input in/) and $status = "INPUTFAILURE\n" ;


		($txtbuf->[$i] =~ /T\/V\s+N\s+NB.*$/) and $found_result = 1 and
			$status = 'FOUND A RESULT';

		($txtbuf->[$i] =~ /Finished.*$/) and $found_endrecord = 1 and do {
			$status = 'FINISHED' unless $status =~ /ALLOC/;
		};

		$found_endrecord and goto xhplendrecord;

		if (!$found_result) {
			$i++;
			next;
		}

        # we need at least 4 more lines in the buffer to make
        # a determination for this chunk of results. we do
        # this check to keep from overflowing our buffer as
        # we parse....
		if (($i + 5) > $numlines) {
			main::debug_print(2,"DEBUG:$shortpackage.parse() parsing ended, buffer would overflow\n");
			last;
		}

		# the beginning of a result record was found, the actual
		# result gigaflops number is 2 lines down in the buffer
		$i += 2;
        my $l =  $txtbuf->[$i];
        chomp $l;
		# matches a result line with Gflops in exponent notation
		# WR00C2L4       98092    80     3     3            2164.52              2.907e+02
        if ($l =~ /(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+\.\d+)\s+(\S+)/) {
			$total_time += $6;
			$gflops = $7;
        }

		# check for the PASSED or FAILED status of the result
		$i += 2;
		my $pass = 0;
		$pass = ($txtbuf->[$i++] =~ /PASSED/);

		# if the parsed Gigaflops result passed and if the result is the max
		# of any previous results from this file, then record it locally
		# pending the determination whether the overall output file is deemed
		# to pass (this check is done further down)
		if ($pass == 1) {
			$numpassed++;
			if ($gflops > $local_max_gflops) {
				$local_max_gflops = $gflops;
			}
		}
		else {
			$numfailed++;
		}

		main::debug_print(2,"DEBUG:$shortpackage.parse() RESULT, $gflops, $total_time, $pass, $status, numpass $numpassed, fail $numfailed\n");

		# we finished parsing a test result, prime the loop for finding the next
		# result in case there are multiple results in the output
		$found_result = 0;
		$i++;
		next;

xhplendrecord:
        $l =  $txtbuf->[$i];
        chomp $l;
        if ($l =~ /Finished\s+(\d+)\s+tests with the following.*$/) {
			$local_total_tests = $1;
		}
		elsif ($l =~ /\s+(\d+)\s+tests completed and passed.*$/) {
			$local_passed_tests = $1;
		}
		elsif ($l =~ /\s+(\d+)\s+tests completed and failed.*$/) {
			$local_failed_tests = $1;
		}			
        
		$i++;
	}

	main::debug_print(2,
		"ENDPARSE, $local_max_gflops, $local_total_tests, $local_passed_tests, ".
		"$local_failed_tests, $status, numpass $numpassed, fail $numfailed\n");

	# only if all tests in the output file PASSED do we flag this overall
	# linpack benchmark as having completed correctly
	if ($status =~ /FINISHED/ and $local_total_tests == $local_passed_tests) {
		$status = 'COMPLETED';
	}
	elsif ($status =~ /FOUND A RESULT/ and $numfailed == 0) {
		$status = 'COMPLETED';
        defined $main::diagnose and main::print_job_err($fileid,'PASSED','DID NOT FINISH CLEAN',"$numpassed PASSED results");
	}
	elsif ($status =~ /FAILURE/) {
		# noop
		$status = $status;
	}
    elsif ($status =~ /CBENCH NOTICE/) {
        $data{'STATUS'} = 'NOTICE';
        (my $tmp = $status) =~ s/CBENCH NOTICE://;
        defined $main::diagnose and main::print_job_err($fileid,'NOTICE',$tmp);
    }
	elsif ($status =~ /FINISHED/ and $local_passed_tests < $local_total_tests) {
		$status = 'FAILED RESIDUALS';
	}

	(defined $main::DEBUG and $main::DEBUG > 2) and print
		"ENDSTATUSCHECK, $status\n";

	if ($status =~ /COMPLETED/) {
		$data{'STATUS'} = 'PASSED';
		$data{gflops} = $local_max_gflops;
		$data{runtime} = $total_time / 60;
	}
	elsif ($status =~ /FAILED RESIDUALS/) {
		if ($local_max_gflops > 0) {
			$data{gflops} = $local_max_gflops;
			$data{runtime} = $total_time / 60;
			$data{'STATUS'} = "PARTIAL FAILED RESIDUALS";
		}
		else {
			$data{gflops} = 'NODATA';
			$data{'STATUS'} = "FAILED RESIDUALS";
		}
		my $tmp = "$local_passed_tests of $local_total_tests PASSED";
        defined $main::diagnose and main::print_job_err($fileid,'ERROR',$status,$tmp);
	}
	else {
		$data{'STATUS'} = "ERROR($status)";
		$data{gflops} = 'NODATA';
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
	@{$self->{FILE_LIST}} = qw/STDOUT/;

	# this is a KEY array... see the metric_units method above for
	# more info
	%{$self->{METRIC_UNITS}} = (
		'gflops' => 'GigaFlops',
		'runtime' => 'minutes',
	);
	
	return 1;
}


1;
