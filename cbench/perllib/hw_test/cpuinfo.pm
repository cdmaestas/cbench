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


package hw_test::cpuinfo;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

cpuinfo

Cbench hw_test module that gathers basic info about a nodes
CPU(s) from Linux
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
	
	my @buf = ();
	
	@buf = `/bin/cat /proc/cpuinfo 2>&1`;
	print $ofh @buf;
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
	my $numcpus = 0;
	my $bogomips = 0.0;
	my $cpumhz = 0.0;

	# parse the buffer
	foreach (@$bufref) {
		if (/bogomips\s+:\s*(\d+.\d+)\s*\S*/i) {
			$numcpus++;
			$bogomips += $1;
		}	
		elsif (/cpu\sMHz\s+:\s*(\d+.\d+)\s*\S*/i) {
			$cpumhz += $1;
		}	
	}

	# build the hash with the data retrieved from parsing
	my $key = "$self->{SHORTNAME}\_num";
	$data{$key} = $numcpus;
	$key = "$self->{SHORTNAME}\_bogomips_total";
	$data{$key} = $bogomips;
	$key = "$self->{SHORTNAME}\_cpumhz_total";
	$data{$key} = $cpumhz;

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
