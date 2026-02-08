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


package hw_test::memtester;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

memtester

Cbench hw_test module that uses the Memtester user-space
memory testing utility to test memory.
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

The output from testing should be sent to the output file
handle for the object, $self->{outhandle}.

The implementation of the run() routine/method for a hw_test
module encompasses the first 50% of the work in creating a new
hw_test module.

=cut

sub run {
	my $self = shift;
	
	# grab the output file handle for the object
	my $ofh = $self->{outhandle};

	# path to the binaries
	my $path = "$main::bench_test/$main::TESTBINPATH/hwtests";
	
	# query Linux for how much useable memory there is to test
	my $useable = main::linux_useable_memory();
	# convert to MB from KB
	$useable = int ($useable * 0.95 / 1024);

	main::debug_print(2,"DEBUG:$shortpackage\.run() useable memory $useable MB\n");

	# divide up total useable memory per cpu
	$useable = int ($useable / main::linux_num_cpus());
	if (defined $main::SMALL) {
		main::debug_print(1,"DEBUG:$shortpackage\.run() doing SMALL mode runs\n");
		$useable = 64;
	}

	main::debug_print(2,"DEBUG:$shortpackage\.run() useable memory $useable MB per CPU\n");
	
	my @buf = ();
	my $cmd = '';

	# Build memtester command line. Memtester requires priveleges to lock
	# lots of memory.  This can be granted via ulimit/limits or by running
	# as root priveleges. Otherwise memtester spews oodles of useless
	# mlock failures lines bloating the output files.
	# The $main::run_as_root configs in cluster.def control one way of running
	# as root.
	# Otherwise, we probe ulimit to see if we can run effectively.
	if (defined $main::run_as_root and ($< != 0) and
		($main::run_as_root or $main::run_as_root eq 'true')) {
		if (!defined $main::run_as_root_cmd) {
			print "ERROR: $shortpackage\.run() run_as_root is enabled but ".
				"run_as_root_cmd is not defined, check cluster.def\n";
			return 1;
		}
		$cmd = "$main::run_as_root_cmd  $path/memtester $useable 1";
	}
	elsif ($< != 0) {
		# we are not root and can't escalate so check ulimit
		
		# build a temp bash script to run ulimit
		use File::Temp qw/ tempfile /;
		my ($fh, $tmpname) = tempfile();
		print $fh
			"\#\!/bin/bash\n".
			"ulimit -l\n";
		close($fh);
		system("/bin/chmod u+x $tmpname");
		(defined $main::DEBUG and $main::DEBUG > 1) and print
			"DEBUG: $shortpackage\.run() ulimit temp script is $tmpname\n";

		my $maxlocked = `$tmpname 2>&1`;
		chomp $maxlocked;
		system("/bin/rm -f $tmpname");
		(defined $main::DEBUG) and print
			"DEBUG: $shortpackage\.run() max locked memory is $maxlocked KB\n";

		# if we can't lock enough memory, warn and give up
		($maxlocked eq 'unlimited') and ($maxlocked = $useable * 4 * 1024);
		if (($useable * 1024) > $maxlocked) {
			my $tmp = "ERROR: $shortpackage\.run() we can only lock $maxlocked KB out ".
				"of $useable MB required for testing. This is not enough to make testing ".
				"worthwhile, giving up...\n";
			print $tmp;
			print $ofh $tmp;
			return;
		}

		# otherwise we can lock enough memory so go for it
		$cmd = "$path/memtester $useable 1";
	}
	else {
		# just run normally because we have root uid
		$cmd = "$path/memtester $useable 1";
	}

	my $start = time;
	main::run_process_per_cpu("$cmd",\@buf);
	my $end = time;

	print $ofh @buf;
	# clear out the buffer for the next binary/iteration
	$#buf = -1;

	# compute number of minutes the memtester run took
	my $delta = ($end - $start) / 60;
	print $ofh "Memtester Elapsed Time: $delta minutes\n";
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
	my $fail = 0;
	my $error = 0;
	my $fail_tmp = 0;
	my $incomplete = 0;
	my $incomplete_tmp = 0;
	my $exit = 0;
	my $loop = 0;
	my $elapsed = -1;

	my $thisproc = 0;
	my $totproc = 0;

	# parse the buffer
	foreach (@$bufref) {
		if (/====> process (\d+)\/(\d+) begin/) {
			# found the delimeter that tells us the output from
			# a different process in the multi-process run started
			$thisproc = $1;
			$totproc = $2;

			(defined $main::DEBUG and $main::DEBUG > 1) and print
					"DEBUG:$shortpackage\.parse() found process begin delimiter, ".
					"$thisproc/$totproc\n";
		}
		elsif (/====> process (\d+)\/(\d+) end/) {
			(defined $main::DEBUG and $main::DEBUG > 1) and print
					"DEBUG:$shortpackage\.parse() found process end delimiter, ".
					"$thisproc/$totproc\n";

			# check to see if we just finished parsing output from a
			# previous binary. if this is the last process, i.e.
			# process 2/2 or something,
			# then compare the final aggregated results from this multi-
			# process streams run
			if ($thisproc == $totproc and $thisproc != 0) {
				# not exiting a memory test normally is a failure
				if (!$exit) {
					$incomplete_tmp++;
					$exit = 0;
				}
				
	    		$fail = main::max($fail, $fail_tmp);
	    		$incomplete = main::max($incomplete, $incomplete_tmp);

				$fail_tmp = 0;
				$incomplete_tmp = 0;

				(defined $main::DEBUG and $main::DEBUG > 1) and print
					"DEBUG:$shortpackage\.parse() process group done $thisproc/$totproc, ".
					"$fail\n";
			}
		}
		elsif (/Loop/) {
			$loop++;
		}
		elsif (/Done\./) {
			$exit = 1;
		}
		elsif (/setting/) {
			$incomplete_tmp++ unless /ok/;
		}
		elsif (/FAILURE/) {
			$fail_tmp++;
		}
		elsif (/Memtester Elapsed Time:\s+(\d+\.\d+)\s+minutes/) {
			$elapsed = $1;
		}
		elsif (/^ERROR\:/) {
			$error = 1
		}
	}

	# build the hash with the data retrieved from parsing
	my $key = "$self->{SHORTNAME}\_fail";
	$data{$key} = $fail;
	my $key = "$self->{SHORTNAME}\_minutes";
	($elapsed != -1) and $data{$key} = $elapsed;
	my $key = "$self->{SHORTNAME}\_incomplete";
	$data{$key} = $incomplete;
	my $key = "$self->{SHORTNAME}\_error";
	($error) and $data{$key} = $error;

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
	$self->{TEST_CLASS} = 'memory';
	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;
	
	return 1;
}


1;
