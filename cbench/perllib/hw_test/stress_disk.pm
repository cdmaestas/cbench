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


package hw_test::stress_disk;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

stress-disk

Cbench hw_test module that uses the 'stress' tool to impose certain types
of compute stress on UNIX-like operating systems.

http://weather.ou.edu/~apw/projects/stress/
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


sub run {
	my $self = shift;
	
	# grab the output file handle for the object
	my $ofh = $self->{outhandle};

	# path to the binaries
	my $path = "$main::bench_test/$main::TESTBINPATH/hwtests";
	
	# how many cpu cores
	my $numcores = main::linux_num_cpus();

	# do we test a physical disk? default to yes
	my $do_hdd = 1;

	# query Linux for how much total memory there is to test
	my $totalmem = main::linux_total_memory();
	# convert to Bytes from KB
	$totalmem = int ($totalmem * 1024);

	# how many test threads? basically a load of 1.0 per thread
	# this value should be EVEN please
	my $numthreads = $numcores;

	# how many seconds to run the testing? 
	my $numseconds = 30 * 60;

	if (defined $main::SMALL) {
		maind:debug_print(1,"DEBUG:$shortpackage\.run() doing SMALL mode runs\n");
		$numseconds = 5 * 60;
	}

	# We need to find one or more local filesystems to test.
	# We do this with the following heuristic:
	#   1. check if they are specified in the cluster.def variable
	#      @nodehwtest_local_filesystems
	#   2. use find_local_filesystems() to find local writeable
	#      filesystem(s) and use the result
	#   3. see if /tmp is local and if so try using it
	my %fslist = ();
	my $numfs = 0;
	if (defined @main::nodehwtest_local_filesystems and 
		($#main::nodehwtest_local_filesystems > -1)) {
		main::debug_print(1,"DEBUG:$shortpackage\.run() using \@nodehwtest_local_filesystems\n");
		for (@main::nodehwtest_local_filesystems) {
			if (main::path_is_on_localdisk($_) and main::path_is_writeable($_)) {
				main::debug_print(2,"DEBUG:$shortpackage\.run() $_ is writeable\n");
				$fslist{$_} = 1;
			}
			else {
				main::debug_print(2,"DEBUG:$shortpackage\.run() $_ is NOT writeable and/or local, ignoring...\n");
			}
		}
		$numfs = scalar keys(%fslist);
	}
	else {
		# get a list of local filesystems to test which will hopefully
		# stress test disk hardware local to this node
		%fslist = main::find_local_filesystems();
		$numfs = scalar keys(%fslist);
	}
	
	# if we still have no filesystems, try case #3
	if ($numfs == 0) {
		main::debug_print(1,"DEBUG:$shortpackage\.run() still no writeable local filesystems,".
			" trying /tmp\n");
		if (main::path_is_on_localdisk("/tmp") and main::path_is_writeable("/tmp")) {
				$fslist{"/tmp"} = 1;
		}
	}
	$numfs = scalar keys(%fslist);

	# if there are no filesystems we like, then we don't do hdd testing
	($numfs == 0) and $do_hdd = 0;
	
	# just pick a single filesystem
	my $tmpdir = '';
	for my $k (keys %fslist) {
		$tmpdir = $k;
	}

	# base the total size of file to use on the total memory of the node
	# and the number of filesystems to test. we want the total size
	# iozone is using for testing to be greater than physical memory
	# to help avoid caching effects.
	my $size = int ($totalmem * 1.25);

	my @buf = ();
	my $cmd = '';

	# Build the stress command line. We want to have half the worker threads
	# doing --io and half doing --hdd stressing where the total number of
	# worker threads is controlled by $numthreads.
	# The --hdd stress test can use a file size per thread option that we
	# make use of to overload physical memory and get out of caches
	my $worknum = int ($numthreads / 2);
	($worknum < 1) and $worknum = 1;
	(!$do_hdd) and $worknum = $numthreads;
	my $filesize = int ($size / $worknum);
	$cmd = "cd $tmpdir;$path/stress --io $worknum --timeout $numseconds ";
	#($do_hdd) and $cmd .= "--hdd $worknum --hdd-bytes $filesize ";
	($do_hdd) and $cmd .= "--hdd $worknum";

	(defined $main::DEBUG and $main::DEBUG > 1) and print
		"DEBUG:$shortpackage\.run() cmd=$cmd\n";

	my $start = time;
	main::run_single_process("$cmd",\@buf);
	my $end = time;

	print $ofh @buf;
	# clear out the buffer for the next binary/iteration
	$#buf = -1;

	# compute number of minutes the stress run took
	my $delta = ($end - $start) / 60;
	print $ofh "Stress Elapsed Time: $delta minutes\n";
}


sub parse {
	my $self = shift;
	my $bufref = shift;

	my %data;
	my $elapsed = -1;
	my $fail = 1;

	# parse the buffer
	foreach (@$bufref) {
		#stress: info: [1965] dispatching hogs: 4 cpu, 0 io, 4 vm, 0 hdd
		#stress: info: [1965] successful run completed in 301s

		if (/Stress Elapsed Time:\s+(\d+\.\d+)\s+minutes/) {
			$elapsed = $1;
		}
		elsif (/stress: info: \[\d+\] successful run completed in (\d+)s/) {
			$fail = 0;
		}
	}

	# build the hash with the data retrieved from parsing
	my $key = "$self->{SHORTNAME}\_fail";
	$data{$key} = $fail;
	my $key = "$self->{SHORTNAME}\_minutes";
	($elapsed != -1) and $data{$key} = $elapsed;

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
	$self->{TEST_CLASS} = 'disk';
	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;
	
	return 1;
}


1;
