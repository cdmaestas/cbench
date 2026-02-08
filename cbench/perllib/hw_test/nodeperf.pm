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


package hw_test::nodeperf;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

nodeperf

Cbench hw_test module that uses 'nodeperf' tool from Greg Henry at Intel.
It is available for download from Intel as part of the Intel MPI package.
Nodeperf uses DGEMM calls to an external library to test the performance
of a node.
.

=head1 Cbench hw_test SYNOPSIS

This is a module for the Cbench hw_test framework. The Cbench hw_test
framework uses simple Perl object modules like this to provide "plug-in"
hardware testing functionality.  Each module encapsulates the intelligence
to run a certain hardrware test or closely related tests and also 
analyze the output from the tests and summarize the data. Cbench utilities
like node_hw_test use these modules.

These hw_test modules are written as Perl objects simply because it was
a good clean way to deal with the dynamic "plug-in"  type model the Cbench
hw_test framework is using.  One shouldn't be scared by the fact that they
are objects.  The object oriented usage is very basic.  Most of the methods
are generic and won't need to be changed for any new hw_test modules that
are written.

See doc/README.hw_test for more information on the Cbench hardware
testing framework.

=cut

###############################################################
#
# Public methods
#


=head1 PUBLIC METHODS

=over 4

=item B<new()> - Create a new hw_test object

Should be called with a parameter that is an open filehandle.

  $obj = hw_test::cpuinfo->new(*FH);

The filehandle parameter is where output from the testing encapsulated
in this hw_test object is printed to. If no parameter is given,
STDOUT is assumed.

=cut

sub new {
	my $type = shift;
	my $self = {};
	bless $self, $type;
	$self->_init(@_) or return;

	return $self;
}


=item B<run()> - Responsible for actually running the test(s)
that this hw_test module encapsulates.

  $obj = hw_test::cpuinfo->new(*FH);
  $obj->run();

The output from tesstreamsting should be sent to the output file
handle for the object, $self->{outhandle}.

The implementation of the run() routine/method for a hw_test
module encompasses the first 50% of the work in creating a new
hw_test module.

=cut

# private variable, how many iterations do we run each time
# run() is called
my $iterations = 2;

sub run {
	my $self = shift;
	
	# grab the output file handle for the object
	my $ofh = $self->{outhandle};

	# path to the binaries
	my $path = "$main::bench_test/$main::TESTBINPATH";
		
	my @buf = ();
	my @binlist = ('nodeperf2-nompi');

	# query Linux for how much useable memory there is to test
	my $useable = main::linux_useable_memory();
	# convert to MB from KB
	$useable = int ($useable * 0.95 / 1024);
	
	# set the command line options for nodeperf
	my $opts = "-i 100 -s $useable";

	if (defined $main::SMALL) {
		(defined $main::DEBUG) and print
				"DEBUG:$shortpackage\.run() doing SMALL mode runs\n";			
		$iterations = 1;
		$useable = $useable / 2;
		$opts = "-s $useable";
	}
	
	# since nodeperf can link with optimized BLAS libs and the libs
	# usually get the best performance using multiple threads within
	# the lib as opposed to multiple process instances of nodeperf,
	# we will assume that we only need to start one instance of
	# nodeperf
	my $numcpus = main::linux_num_cpus();
	$ENV{'OMP_NUM_THREADS'} = $numcpus;
	for my $i (1..$iterations) {
		for	(@binlist) {
			chomp $_;
			#my $cmd = "export OMP_NUM_CPUS=$numcpus;$path/$_ 2>&1";
			my $cmd = "$path/$_ $opts 2>&1";

			# run nodeperf binary
			print $ofh "====> NORMAL $_\n";
			main::run_single_process($cmd,\@buf);
			print $ofh @buf;
			# clear out the buffer for the next binary/iteration
			$#buf = -1;
		}

		if ($main::INTsignalled) {
			print "$shortpackage.run() exiting on SIGINT...\n";
			last;
		}
	}
	print $ofh "====> endofnodeperf\n";
}

=item B<parse()> - Responsible for actually parsing the output
from the test(s) that this hw_test module encapsulates and 
returning a hash reference with the extracted data.

parse() takes a reference to a buffer (array) as the single input

  $obj = hw_test::cpuinfo->new(*FH);
  $obj->run();
  .
  read the output from run() in from the output file it
  went to and put it in @buf
  .
  $datahashref = $obj->parse(\@buf);
  for $k (keys %{$datahashref}) {
  print "$k => $datahashref->{$k}\n";
  }

The implementation of the parse() routine/method for a hw_test
module encompasses the second 50% of the work in creating a new
hw_test module.

=cut

sub parse {
	my $self = shift;
	my $bufref = shift;

	my %data;
	my $mflops = -10;
	my $error = 0;
	my $mflops_tmp = 0;
	my $mflops_taskset = 0;
	my $error_tmp = 0;
	
	# parse the buffer
	foreach (@$bufref) {
		if (/====> \S+\s+/) {
			# found a binary delimeter, i.e. start of a new nodeperf
			# binary that was run or another iteration
			if (/TASKSET/) {
				$mflops_taskset = main::max($mflops_taskset,$mflops_tmp);
			}
			else {
				$mflops = main::max($mflops,$mflops_tmp);
			}
			$error = main::max($error,$error_tmp);
			
			$error_tmp = 0;
			(defined $main::DEBUG and $main::DEBUG > 1) and print
					"DEBUG:$shortpackage\.parse() new binary, $mflops, $error\n";			
		}
		elsif (/\(0 of 1\):\s+\S+\s+lda=\s*\d+\s+ldb=\s*\d+\s+ldc=\s*\d+\s+\d+\s+\d+\s+\d+\s+(\d+\.\d+)\s*/) {
			$mflops_tmp = $1;
			(defined $main::DEBUG and $main::DEBUG > 1) and print
					"DEBUG:$shortpackage\.parse() $_\n";			
		}
		elsif (/Error at/) {
			$error_tmp++;
		}
		elsif (/Number of errors found=(\d+) Total/) {
			($1 > 0) and $error_tmp++;
		}
	}

	# build the hash with the data retrieved from parsing
	my $key = "$self->{SHORTNAME}\_mflops";
	($mflops > 0) and $data{$key} = $mflops;
	my $key = "$self->{SHORTNAME}\_taskset_mflops";
	($mflops_taskset > 0) and $data{$key} = $mflops_taskset;
	my $key = "$self->{SHORTNAME}\_error";
	$data{$key} = $error;

	return \%data;
}

=item B<name()> - Return the name of the hw_test module

For example: hw_test::cpuinfo

=cut

sub name {
	my $self = shift;
	return $self->{NAME};
}

=item B<test_class()> - Return the test_class of the hw_test module

For example: cpu, memory, disk, ...

=cut

sub test_class {
	my $self = shift;
	return $self->{TEST_CLASS};
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
