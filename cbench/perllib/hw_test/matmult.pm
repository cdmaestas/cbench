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


package hw_test::matmult;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

matmult

Cbench hw_test module that uses the LLNL Matmult test

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


sub run {
	my $self = shift;
	
	# grab the output file handle for the object
	my $ofh = $self->{outhandle};

	# path to the binaries
	my $path = "$main::bench_test/$main::TESTBINPATH";
	
	# how many cpu cores and sockets
	my $numcores = main::linux_num_cpus();
	my $numsockets = main::linux_num_sockets();
	my $cores_per_socket = int ($numcores / $numsockets);

	# build an array encoding the test cases we want to do with respect to
	# numactl options. encode test cases for each physical socket and running
	# on any core Linux sees fit
	#
	# FIXME: i'm just making this up as i go right now, but it might be good
	# to have an encoding scheme or something more formal. for now i just
	# need to get something working and see how it goes.
	my @numacases = ();
	for (0..$numsockets-1) {
		push @numacases,"socket$_";
	}
	push @numacases,"anycore";

	# build an array of thread counts
	my @threadcases = ();
	# one way is all powers of two up through total core count
	for (1..$numcores) {
		main::power_of_two($_) and push @threadcases, $_;
	}
	# another way is pick some interesting counts
	@threadcases = ($cores_per_socket, $numcores);

	my @buf = ();

	# the following parameters and logic were ported from the runit.{mmc,mmf}
	# scripts of matmult
	my $maxrep = 5000;
	my @size_list = qw/128 256 1024 2048/;

	if (defined $main::SMALL) {
		main::debug_print(1,"DEBUG:$shortpackage\.run() doing SMALL mode runs\n");
		$maxrep = 1000;
	}

	foreach my $size (@size_list) {
		my $nrep = int ($maxrep / $size);
		# make sure nrep is nonzero
		($nrep == 0) and $nrep = 1;

		foreach my $nthreads (@threadcases) {
			# matmult is an OpenMP dependent test fundamentally
			$ENV{'OMP_NUM_THREADS'} = $nthreads;

			foreach my $numacode (@numacases) {
				foreach my $mm (qw/mmc mmf/) {
					# check for the binary since it isn't necessarily built
					if (! -x "$path/$mm") {
						print $ofh "ERROR: $path/$mm does not exist\n";
						next;
					}

					# make a string to identify this test case
					my $casename = "$nthreads"."threads_$numacode"."_$mm"."$size";

					# test for overallocation conditions w.r.t. numactl and sockets
					# and cores per socket and such
					if ($numacode =~ /socket/ and ($nthreads > $cores_per_socket)) {
						# for now we are skipping the overallocation cases... they
						# might be useful though i suppose
						main::debug_print(1,"DEBUG: $shortpackage\.run($casename) skipping ".
							"due to core overallocation");
						next;
					}

					# build the command line we'll run
					# start with numactl stuff 
					my $cmd = numactl_cmdline($numacode);
					# now append the actually running of the test binary
					$cmd .= " $path/$mm $nthreads $nrep $size $size $size";
					main::debug_print(2,"DEBUG: $shortpackage\.run($casename) cmd=$cmd\n");

					# run the actual testcase
					my $start = time;
					main::run_single_process("$cmd 2>&1",\@buf);
					my $end = time;

					testcase_add_output($ofh,$casename,\@buf);

					# clear out the buffer for the next binary/iteration
					$#buf = -1;

					# compute number of minutes the matmult run took
					my $delta = ($end - $start) / 60;
					print $ofh "$mm Elapsed Time: $delta minutes\n";

					# check for SIGINT
					if ($main::INTsignalled) {
						main::debug_print(1,"DEBUG:$shortpackage\.run() SIGINT seen...exiting\n");
						return;
					}
				}
			}
		}
	}
}


sub parse {
	my $self = shift;
	my $bufref = shift;

	my %data = ();

	# parse the buffer
	# NOTE: matmult runs a number of different testcases so we use
	#       a helper routine,parse_testcases_inbuf, to iterate over the
	#       testcase in the output buffer. we give parse_testcases_inbuf()
	#       a ref to a subroutine to do the real parsing of data points
	_parse_testcases_inbuf($bufref,\&_parse,\%data);

	return \%data;
}


sub name {
	my $self = shift;
	return $self->{NAME};
}


sub test_class {
	my $self = shift;
	return $self->{TEST_CLASS};
}



###############################################################
#
# "Private" methods
#

sub _init {
	my $self = shift;
	if (@_ == 0) {
		$self->{outhandle} = *STDOUT;
	}
	elsif (@_ == 1) {
		# Single parameter, better be a filehandle.
		# save the handle in the object
		$self->{outhandle} = shift;
	} else {
		my %args = @_;
		map { $self->{$_} = $args{$_}; } keys %args;
	}

	# this defines the Cbench hw_test test class (i.e. cpu, memory, etc.)
	# for this dude
	$self->{TEST_CLASS} = 'memory';
	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;
	
	return 1;
}

###############################################################
#
# some utility internal subroutines
#

sub numactl_cmdline {
	my $code = shift;

	my $cmdline = '';
	my $numactl = '/usr/bin/numactl';

	# check for numactl supporting the cpunodebind option
	undef $/;
	my $tmp = `$numactl 2>&1 | grep cpunodebind`;
	$/ = "\n";
	my $have_cpunodebind = ($tmp =~ /cpunodebind/);

	if ($code =~ /^socket(\d+)/) {
		($have_cpunodebind) and $cmdline .= "$numactl --preferred=$1 --cpunodebind=$1 ";
		(!$have_cpunodebind) and $cmdline .= "$numactl --preferred=$1 --cpubind=$1 ";
	}
	if ($code eq 'anycore') {
		# just let linux do what it wants
	}

	return $cmdline;
}

sub testcase_add_output {
	my $ofh = shift;
	my $name = shift;
	my $bufref = shift;

	my $date = `/bin/date`;
	chomp $date;

	print $ofh "==testcase==> $name at $date\n";
	print $ofh @{$bufref};
}

sub _parse_testcases_inbuf {
	my $bufref = shift;
	my $parsesub = shift;
	my $data = shift;

	my @tmpbuf = ();
	my $linegrab = 0;
	my $case = '';
	foreach my $l (@$bufref) {
		if ($l =~ /==testcase==> (\S+)\sat\s/ and !$linegrab) {
			# start grabbing lines for the first test case
			$case = $1;
			$linegrab = 1;
			main::debug_print(3,"DEBUG:$shortpackage\.parse_testcases_inbuf() found case $case\n");
		}
		elsif ($l =~ /==testcase==> (\S+)\sat\s/ and $linegrab) {
			# reached the next test case... so parse the lines
			# we've been grabbing using the supplied parse
			# subroutine reference
			main::debug_print(3,"DEBUG:$shortpackage\.parse_testcases_inbuf() parsing case $case\n");
			&$parsesub(\@tmpbuf,$data,$case);

			# clear out the temp line buffer for the next binary/iteration
			$#tmpbuf = -1;

			$case = $1;
			$linegrab = 1;
			main::debug_print(3,"DEBUG:$shortpackage\.parse_testcases_inbuf() found case $case\n");
		}
		elsif ($linegrab) {
			push @tmpbuf, $l;
		}
	}

	if ($linegrab) {
		# reached the end... so parse the lines
		# we've been grabbing using the supplied parse
		# subroutine reference
		main::debug_print(3,"DEBUG:$shortpackage\.parse_testcases_inbuf() parsing last case $case\n");
		&$parsesub(\@tmpbuf,$data,$case);

		# clear out the temp line buffer for the next binary/iteration
		$#tmpbuf = -1;
	}

}



# internal parse subroutine 
sub _parse {
	my $bufref = shift;
	my $data = shift;
	my $name = shift;

	foreach (@$bufref) {
		if (/Average speedup is\s+(\S+)/) {
			my $tmp = $1;
			my $key = "$shortpackage\_$name\_speedup";
			main::debug_print(3,"DEBUG:$shortpackage\.parse() $name speedup $tmp, $key");
			$$data{$key} = main::max($$data{$key},$tmp);

		}
		elsif (/Elapsed Time:\s+(\d+[\.\d+]*)\s+minutes/) {
			my $tmp = $1;
			my $key = "$shortpackage\_$name\_elapsed";
			main::debug_print(3,"DEBUG:$shortpackage\.parse() $name elapsed $tmp, $key");
			$$data{$key} = main::max($$data{$key},$tmp);
		}
	}
}


1;
