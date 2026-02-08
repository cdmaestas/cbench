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


package hw_test::stress_cpu;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

stress-cpu

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

	# query Linux for how much useable memory there is to test (in KB)
	my $useable = main::linux_useable_memory();
	# leave a little more memory freedom
	$useable = int ($useable * 0.95 / 1024);

	(defined $main::DEBUG and $main::DEBUG > 1) and print
		"DEBUG: $shortpackage\.run() useable memory $useable MB\n";

	# how many test threads? basically a load of 1.0 per thread
	# this value should be EVEN please
	my $numthreads = $numcores;

	# how many seconds to run the testing? 
	my $numseconds = $main::nodehwtest_stress_minutes * 60;
	
	if (defined $main::SMALL) {
		(defined $main::DEBUG) and print
				"DEBUG:$shortpackage\.run() doing SMALL mode runs\n";			
		$numseconds = 5 * 60;
	}

	my @buf = ();
	my $cmd = '';

	# Build stress command line. We want to have half the worker threads
	# doing --cpu and half doing --vm stressing where the total number of
	# worker threads is controlled by $numthreads.
	# The --vm stress test can use a specified amount of memory per thread.
	# We set this to useable/numcores/2 basically per vm worker.
	my $worknum = int ($numthreads / 2);
	my $workermem = int (($useable * 1024 * 1024) / $worknum);
	# --vm-keep might also be a useful option, but load seems to be harder
	# w/o it in the cmd line
	$cmd = "$path/stress --cpu $worknum --vm $worknum --vm-bytes $workermem ".
		"--timeout $numseconds";
	(defined $main::DEBUG and $main::DEBUG > 1) and print
		"DEBUG: $shortpackage\.run() cmd=$cmd\n";

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
	$self->{TEST_CLASS} = 'cpu';
	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;
	
	return 1;
}


1;
