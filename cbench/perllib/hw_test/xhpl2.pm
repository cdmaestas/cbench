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


package hw_test::xhpl2;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

hpcc

Cbench hw_test module that uses the HP Linpack benchmark on a single
node to test out cpu and memory performance.
This module will only work if the Cbench local mpich version of
Linpack (xhpl2) has been compiled and installed into the nodehwtest test
set.

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


# private variable, how many iterations do we run each time
# run() is called
my $iterations = 1;

sub run {
	my $self = shift;
	
	# grab the output file handle for the object
	my $ofh = $self->{outhandle};

	# path to the binaries
	my $path = "$main::bench_test/$main::TESTBINPATH";
		
	my @buf = ();
	
	# find the appropriate mpirun to use
	my $mpirun = main::find_bin('mpirun',"$main::bench_test/mpich/bin","$main::BENCH_HOME/opensource/mpich/bin");
	$mpirun = main::find_bin('mpirun',"$main::bench_test/openmpi/bin") if defined($ENV{CBENCHSTANDALONEDIR});
	(!defined $mpirun) and do {
		print "$shortpackage\.run() Couldn't find mpirun...exiting\n";
		return 1;
	};

	# We have to create a little sandbox for linpack to run in.
	use File::Temp;
	
	# get a temporary directory, automatically clean it up when done
	my $rundir = File::Temp::tempdir(CLEANUP => 1);
	my $pwd = `/bin/pwd`;

	main::debug_print(1,"DEBUG:$shortpackage\.run() temp directory = $rundir\n");
	
	# build the requisite content in the directory for HPCC to run
	#
	chdir $rundir;
	
	# build the HPL.dat input file for linpack
	# read in config file generation template
	my $file = "$main::testset_path\/xhpl_dat.in";
	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	my $xhpldat = <IN>;
	close(IN);
	$/ = "\n";

	# we need to honor the --maxmem command line param
	if (defined $main::MAXMEM) {
		main::debug_print(2,
			"DEBUG:$shortpackage.run() overriding by MAXMEM var, num=$main::MAXMEM\n");
		$main::memory_per_node = $main::MAXMEM;
		$main::memory_per_processor = $main::memory_per_node / $main::procs_per_node;
	}

	# need a simple hosts file for mpirun with enough entries for the core
	# count on the node
	$file = "$rundir\/hostlist";
	open (OUT,">$file") or do {
		print "ERROR:$shortpackage.run() Could not write $file ($!)\n";
		return;
	};
	for (1..$main::procs_per_node) {
		print OUT "$main::hn\n";
	}
	close(OUT);

	# Determine the ppn values we will run the test at.
	# FIXME: for the time being we will just run at a single value
	#        until the parse() sub gets updated with better logic 
	#        to handle multiple runs
	my @ppnlist = ($main::nodehwtest_xhpl_ppn);

	# loop to run linpack
	foreach my $ppn (@ppnlist) {
		# need to setup the HPL.dat appropriately
		my @Nvals = main::compute_N($ppn,$ppn);
		my ($P, $Q) = main::compute_PQ($ppn);
		my $num_Nvals = @Nvals;
		my $outbuf = $xhpldat;	
		$outbuf =~ s/XHPL_NUM_N_HERE/$num_Nvals/gs;
		$outbuf =~ s/XHPL_N_HERE/@Nvals/gs;
		$outbuf =~ s/XHPL_P_HERE/$P/gs;
		$outbuf =~ s/XHPL_Q_HERE/$Q/gs;

		# write out the generated hpccinf.txt file
		$file = "$rundir\/HPL.dat";
		open (OUT,">$file") or do {
			print "ERROR:$shortpackage.run() Could not write $file ($!)\n";
			return;
		};
		print OUT $outbuf;
		close(OUT);

		# setup OMP_NUM_THREADS
		my $threads = main::calc_num_threads($ppn,$ppn);
		main::debug_print(1,"DEBUG:$shortpackage.run() setting OMP_NUM_THREADS=$threads for ppn=$ppn\n");
		$ENV{'OMP_NUM_THREADS'} = $threads;

		#
		# Ok, should be ready to run Linpack
		my $cmd = "$mpirun -machine shmem ".
			"-machinefile $rundir\/hostlist -np $ppn $path/xhpl2.ch_shmem";
		$cmd = "$mpirun -machinefile $rundir\/hostlist -n $ppn $path/xhpl2" if defined($ENV{CBENCHSTANDALONEDIR});
		main::debug_print(1,"DEBUG:$shortpackage\.run() cmd = $cmd\n");
		print $ofh "====> $ppn"."ppn\n";
		main::run_single_process("$cmd",\@buf);

		# save output
		print $ofh @buf;
		# clear out the buffer for the next binary/iteration
		$#buf = -1;
	}

	chdir $pwd;
}

sub parse {
	my $self = shift;
	my $bufref = shift;

	my %data;
	my $key;
	my $fail = 0;

	# strip the buffer of stderr output that can show up non-deterministically
	# in the output stream and confuses the assumptions during parsing
	my @cleanbuf = ();
	foreach (@{$bufref}) {
		/memfree\s+=\s+\d+\s+/ and next;
		push @cleanbuf, $_;
	}

	# prepare to parse the buffer
	my $txtbuf = \@cleanbuf;
	my $numlines = scalar @{$txtbuf}; 

	# NOTE: The linpack output file can have multiple results within it.
	#       We want to grab the maximum PASSED result from the file. We
	#       will only record the linpack data into the final data hash
	#       if all results within the file PASSED residual checks.
    my $status = 'NOTSTARTED';
    my $found_result = 0;
	my $found_endrecord = 0;
    my $i = 0;
	my $gflops = 'NODATA';
	my $local_max_gflops = 0.0;
	my $local_total_tests = 'nodata1';
	my $local_passed_tests = 'nodata2';
	my $local_failed_tests = 'nodata3';
	my $resultsok = 0;
	my $resultsfound = 0;
	my $total_time = 0;
    while ($i < $numlines) {
        ($txtbuf->[$i] =~ /matrix A is randomly generated/) and $status = 'STARTED';

		#HPL ERROR from process # 0, on line 170 of function HPL_pdtest:
		#>>> [39,47] Memory allocation failed for A, x and b. Skip. <<<
        ($txtbuf->[$i] =~ /Memory allocation failed/) and $status = 'ALLOCFAILURE';

		($txtbuf->[$i] =~ /T\/V\s+N\s+NB.*$/) and $found_result = 1 and
			$status = 'FOUND A RESULT';

		($txtbuf->[$i] =~ /Finished.*$/) and $found_endrecord = 1 and do {
			$status = 'FINISHED' unless $status =~ /ALLOC/;
			main::debug_print(3,"DEBUG:$shortpackage.parse() ENDRECORD");
		};

		$found_endrecord and goto xhplendrecord;

		if (!$found_result) {
			$i++;
			next;
		}

        # we need at least 6 more lines in the buffer to make
        # a determination for this chunk of results. we do
        # this check to keep from overflowing our buffer as
        # we parse....
		if ($i + 6 > $numlines) {
			main::debug_print(3,"DEBUG:$shortpackage.parse() ".
				"parsing ended, buffer would overflow\n");
			last;
		}

		# the beginning of a result record was found, the actual
		# result gigaflops number is 2 lines down in the buffer
		$i += 2;
        my $l =  $txtbuf->[$i];
        #chomp $l;
		my ($exp, $mantissa, $exp_str);
		# matches a result line with Gflops in exponent notation
        if ($l =~ /(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)e\+(\d+)/) {
			$total_time += $6;
			$exp = $8;
			$mantissa = $7;
			$exp_str = 'e+';
			$gflops = $mantissa * (10 ** $exp);
			$resultsfound++;
        }
		# matches a result line without exponent notation
        elsif ($l =~ /(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)/) {
			$total_time += $6;
			$mantissa = $7;
			$exp = 'noexp';
			$gflops = $mantissa;
			$exp_str = 'noexp';
			$resultsfound++;
        }
		else {
			main::debug_print(3,"DEBUG:$shortpackage.parse() Warning, expected result line, found $l");
		}


		# check for the PASSED or FAILED status of the result
		$i += 2;
		my $pass = 0;
		#main::debug_print(1,"$txtbuf->[$i]");
		#main::debug_print(1,"$txtbuf->[$i+1]");
		#main::debug_print(1,"$txtbuf->[$i+2]");
		$pass = ($txtbuf->[$i++] =~ /Ax-b.*eps.*PASSED/);

		# if the parsed Gigaflops result passed and if the result is the max
		# of any previous results from this file, then record it locally
		# pending the determination whether the overall output file is deemed
		# to pass (this check is done further down)
		if ($pass == 1) {
			if ($gflops > $local_max_gflops) {
				$local_max_gflops = $gflops;
			}
			main::debug_print(3,"DEBUG:$shortpackage.parse() RESULTCHECK $pass of 1 PASSED, $local_max_gflops\n");
			$resultsok++;
		}

		main::debug_print(3,"DEBUG:$shortpackage.parse() RESULT, $gflops, $mantissa, $exp, $exp_str, $pass, $status\n");

		# we finished parsing a test result, prime the loop for finding the next
		# result in case there are multiple results in the output
		$found_result = 0;
		$i++;
		next;

xhplendrecord:
        $l =  $txtbuf->[$i];
        #chomp $l;
        if ($l =~ /Finished\s+(\d+)\s+tests with the following.*/) {
			$local_total_tests = $1;
		}
		elsif ($l =~ /\s+(\d+)\s+tests completed and passed.*/) {
			$local_passed_tests = $1;
		}
		elsif ($l =~ /\s+(\d+)\s+tests completed and failed.*/) {
			$local_failed_tests = $1;
		}			

		$i++;
	}
	
	# zero our temp buffer for hopeful memory reclaimation
	$#cleanbuf = -1;

	main::debug_print(3,"DEBUG:$shortpackage.parse() ".
		"ENDPARSE, $local_max_gflops, $local_total_tests, $local_passed_tests, ".
		"$local_failed_tests, $status\n");

	# only if all tests in the output file PASSED do we flag this overall
	# linpack benchmark as having completed correctly
	if ($status =~ /FINISHED/ and $local_total_tests == $local_passed_tests) {
		$status = 'COMPLETED';
	}
	elsif ($status =~ /ALLOCFAILURE/) {
		$status = 'ALLOCFAILURE';
	}
	elsif ($status =~ /FINISHED/ and $local_passed_tests < $local_total_tests) {
		$status = 'FAILED RESIDUALS';
	}
	elsif (!$found_endrecord) {
		$status = 'FAILED';
		$local_failed_tests = $resultsfound;
		$key = "$self->{SHORTNAME}\_noendrecord";
		$data{$key} = 1;
		main::debug_print(1,"DEBUG:$shortpackage.parse() WARNING: no end record found");
		main::debug_print(3,"DEBUG:$shortpackage.parse() NOENDRECORD resultsfound=$resultsfound resultsok=$resultsok");
	}
	else {
		$status = 'FAILED';
	}

	main::debug_print(3,"DEBUG:$shortpackage.parse() ENDSTATUSCHECK, $status\n");

	if ($status =~ /COMPLETED/) {
		$key = "$self->{SHORTNAME}\_gflops";
		$data{$key} = $local_max_gflops;
		$key = "$self->{SHORTNAME}\_runtime";
		$data{$key} = $total_time / 60;
	}
	else {
		$key = "$self->{SHORTNAME}\_fail";
		$data{$key} = $local_failed_tests;
	}

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
	$self->{TEST_CLASS} = 'cpu';
	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;
	
	return 1;
}


1;
