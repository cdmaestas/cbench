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


package hw_test::omdiag;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

omdiag

Cbench hw_test module that uses the Dell OpenManage Online Diagnostic
command line interface tool, omdiag, to run diagnostics on Dell hardware.
This module relies on the Dell OpenManage tools being installed!

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
my $iterations = 1;

sub run {
	my $self = shift;
	
	# grab the output file handle for the object
	my $ofh = $self->{outhandle};

	# try to find the omdiag binary
	my $bin = main::find_bin('omdiag','/usr/bin','which');
	if (! defined $bin) {
		# couldn't find the omdiag binary
		print $ofh "ERROR: could not locate the omdiag binary!\n";
		return;
	}

	# buffer for command output
	my @buf = ();
	
	# hash of omdiag tests to run
	my %tests = (
		'chassis' => ['cmos','pci','network','memory'],
		'system' => ['cmos','pci','network','memory'],
	);

	# timeout in seconds
	my $timeout = 30 * 60;

	# omdiag uses Java and omdiag tends to throw several Java
	# errors over time and many iterations. So, change directory
	# to /tmp to hopefully contain the hs_err*.log file spew
	chdir "/tmp";

	foreach my $class (keys %tests) {
		foreach my $test (@{$tests{$class}}) {
			print $ofh "====> $class $test\n";
			my $cmd = "$bin $class $test passes=$iterations";
		
			(defined $main::DEBUG and $main::DEBUG > 1) and print
				"DEBUG:$shortpackage\.run() cmd=$cmd\n";

			# omdiag seems to hang a lot so we'll try to trap
			# that behavior and avoid
			eval {
				local $SIG{ALRM} = sub { die "alarm" };
				alarm $timeout;
				# run_process_per_cpu using single process
				main::run_process_per_cpu($cmd,\@buf,0,1);
				alarm 0;
			};
			alarm 0;

			print $ofh @buf;
			if ($@ && $@ =~ /alarm/) {
				print $ofh "omdiag killed by alarm\n";
				main::kill_kids();
				(defined $main::DEBUG) and print
					"DEBUG:$shortpackage\.run() omdiag killed by alarm\n";
			}
			# clear out the buffer for the next binary/iteration
			$#buf = -1;
		
			if ($main::INTsignalled) {
				print "$shortpackage.run() exiting on SIGINT...\n";
				last;
			}
			sleep 2;
		}
		($main::INTsignalled) and last;
	}

	print $ofh "====> endofomdiag\n";
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
	my $testkey;
	
	# parse the buffer
	foreach (@$bufref) {
		(/====> process /) and next;
		if ($_ =~ /====>\s+(\S+)\s+(\S+)\s*/) {
			$testkey = "$shortpackage\_$1\_$2\_fail";
			$data{$testkey} = 0;
			$testkey = "$shortpackage\_hung";
			$data{$testkey} = 0;
			$testkey = "$shortpackage\_notloaded";
			$data{$testkey} = 0;
			$testkey = "$shortpackage\_notworking";
			$data{$testkey} = 0;

			(defined $main::DEBUG and $main::DEBUG > 1) and print
				"DEBUG:$shortpackage.parse() testkey=$testkey\n";
		}
#		elsif ($_ =~ /Result\s+:\s+Passed\s*/) {
		elsif ($_ =~ /Result\s+:\s+[Failed]\s*/) {
			$data{$testkey}++;
			
			(defined $main::DEBUG and $main::DEBUG > 1) and print
				"DEBUG:$shortpackage.parse() $testkey\=$data{$testkey}\n";
		}
		elsif ($_ =~ /could not locate the omdiag binary/) {
			$testkey = "$shortpackage\_notloaded";
			$data{$testkey} = 1;
		}
		elsif ($_ =~ /killed by alarm/) {
			$testkey = "$shortpackage\_hung";
			$data{$testkey}++;
		}
		elsif ($_ =~ /Error! Invalid XSL path/) {
			$testkey = "$shortpackage\_notworking";
			$data{$testkey} = 1;
		}
	}

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
	$self->{TEST_CLASS} = 'dell';
	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;
	
	return 1;
}


1;
