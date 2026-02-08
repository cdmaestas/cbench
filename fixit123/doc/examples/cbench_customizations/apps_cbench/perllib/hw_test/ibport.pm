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


package hw_test::ibport;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

topspin

Cbench hw_test module that uses tools from the Topspin Infiniband
stack to test as much of the HCA and IB link(s) to a given node
as possible.  This module relies on Topspin tools being installed!

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

my $upport_wait = 600;  # in seconds

sub run {
	my $self = shift;
	
	my $passed = 0;
	my $portstat;

	# grab the output file handle for the object
	my $ofh = $self->{outhandle};
	
	if (defined  $self->{RUNONCE}) {
		print $ofh "STATUS: $shortpackage already run once...skipping\n";
		return;
	}

	# find the state of the IB port
	if (_ib_port_status($self,\$portstat)) {
		# port is UP UP, so we know the ib port comes online ok,
		# thus the test has mostly passed
		$passed = 1;
		print $ofh "STATUS: IB port was UP/UP in initial check\n";
	}
	else {
		# port is NOT in the UP UP state
		print $ofh "STATUS: IB port was not UP/UP in initial check: $portstat\n";

		# try to bring the port up
		_upport($self);

		# wait for the configured amount of seconds and then check the port to
		# see if it onlined correctly
		(defined $main::DEBUG and $main::DEBUG > 1) and print
			"DEBUG:$shortpackage\.run(): waiting after upport for $upport_wait seconds...\n";
		my $wait = $upport_wait;
		my $wait_quanta = 20;
		while ($wait > 0) {
			if ($wait > $wait_quanta) {
				sleep $wait_quanta;
				$wait -= $wait_quanta;
			}
			else {
				sleep $wait;
				$wait = 0;
			}

			if (_ib_port_status($self,\$portstat)) {
				$passed = 1;
				print $ofh "STATUS: IB port went UP/UP after upporting\n";
				$wait = 0;
			}
			else {
				$passed = 0;
				print $ofh "STATUS: IB port failed to go UP/UP after upporting: $portstat\n";
			}
		}
	}

	# now we want to make sure the port goes offline
	for my $i (1..3) {
		_downport($self);
		sleep 15;
		(! _ib_port_status($self,\$portstat)) and last;
	}

	if (_ib_port_status($self,\$portstat)) {
		$passed = 0;
		print $ofh "STATUS: IB port failed to DOWN/DOWN after downporting: $portstat\n";
	}
	else {
		$passed = 1;
		print $ofh "STATUS: IB port went DOWN/DOWN after downporting\n";
	}

	($passed) and print $ofh "RESULT: PASSED\n";
	(!$passed) and print $ofh "RESULT: FAILED\n";

	# we only want to run this test module once per node_hw_test invocation
	$self->{RUNONCE} = 1;
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

	my $key = "$self->{SHORTNAME}\_fail";

	# parse the buffer
	foreach (@$bufref) {
		if ($_ =~ /RESULT.*PASSED/) {
			$data{$key} = 0;
		}
		elsif ($_ =~ /RESULT.*FAILED/) {
			$data{$key} = 1;
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
	$self->{TEST_CLASS} = 'topspin';
	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;
	
	return 1;
}


my $check_port_cmd = "/apps/contrib/check_node_ib_port.sh $main::hn";
my $upport_cmd = "/apps/contrib/upport-node.sh $main::hn";
my $downport_cmd = "/apps/contrib/downport-node.sh $main::hn";
my @buf = ();
my $timeout = 30;

sub _ib_port_status {
	my $self = shift;
	my $stat = shift;

	# grab the output file handle for the object
	my $ofh = $self->{outhandle};

	$#buf = -1;

	eval {
		local $SIG{ALRM} = sub { die "alarm" };
		alarm $timeout;
		main::run_process_per_cpu($check_port_cmd,\@buf,0,1);
		alarm 0;
	};
	alarm 0;

	if ($@ && $@ =~ /alarm/) {
		print $ofh "check_node_ib_port.sh killed by alarm\n";
		main::kill_kids();
	}

	(defined $main::DEBUG and $main::DEBUG > 1) and print
		"DEBUG:$shortpackage\._ib_port_status(): @buf\n";

	my @f;
	foreach my $l (@buf) {
		($l !~ /iblsw/) and next;
		@f = split(/\s+/,$l);
		$$stat = $f[3] ." ". $f[4];
	}

	($f[3] eq 'up' and $f[4] eq 'up') and return 1;
	return 0;
}

sub _downport {
	my $self = shift;

	# grab the output file handle for the object
	my $ofh = $self->{outhandle};

	eval {
		local $SIG{ALRM} = sub { die "alarm" };
		alarm $timeout;
		main::run_process_per_cpu($downport_cmd,\@buf,0,1);
		alarm 0;
	};
	alarm 0;

	if ($@ && $@ =~ /alarm/) {
		print $ofh "downport-node.sh killed by alarm\n";
		main::kill_kids();
	}
}

sub _upport {
	my $self = shift;

	# grab the output file handle for the object
	my $ofh = $self->{outhandle};

	eval {
		local $SIG{ALRM} = sub { die "alarm" };
		alarm $timeout;
		main::run_process_per_cpu($upport_cmd,\@buf,0,1);
		alarm 0;
	};
	alarm 0;

	if ($@ && $@ =~ /alarm/) {
		print $ofh "upport-node.sh killed by alarm\n";
		main::kill_kids();
	}
}


1;
