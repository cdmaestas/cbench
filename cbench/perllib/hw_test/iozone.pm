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


package hw_test::iozone;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

iozone

Cbench hw_test module that uses the iozone filesystem benchmarking
tool. This module attempts to test all the local filesystems it finds
that are common filessytems such as ext2, ext3, reiser, etc.

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

	# path to the binaries
	my $path = "$main::bench_test/$main::TESTBINPATH";
		
	my @buf = ();
	
	# query Linux for how much total memory there is to test
	my $totalmem = main::linux_total_memory();
	# convert to MB from KB
	$totalmem = int ($totalmem / 1024);

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

	# if there are no local filesystems or no local filesystems we
	# have write permission on, then we have nothing to test
	if ($numfs == 0) {
		print "ERROR:$shortpackage\.run() no local filesystems to test or ".
			"possibly none are writeable by user id $<\n";
		return;
	}
	main::debug_print(2,"DEBUG:$shortpackage\.run() found $numfs local filesystems\n");

	my $stripe = '1m';
	
	# base the size of file to use on the total memory of the node
	# and the number of filesystems to test. we want the total size
	# iozone is using for testing to be greater than physical memory
	# to help avoid caching effects.
	my $size = int ($totalmem * 1.25);
	$size = int ($size / $numfs);
	if (defined $main::SMALL) {
		main::debug_print(1,"DEBUG:$shortpackage\.run() doing SMALL mode runs\n");
		$size = 64;
	}

	# Build the iozone command line.
	my $cmd = "$path/iozone -i 0 -i 1 -i 2 -I -e -T -K -r $stripe -s $size\m -t $numfs -F ";

	# tack on the list of filesystems to iozone command line
	my $i = 1;
	foreach (keys %fslist) {
		$cmd .= "$_/iozone_$i.dat ";
		$i++;
	}

	main::debug_print(1,"DEBUG:$shortpackage\.run() cmd=$cmd\n");
		
	for my $i (1..$iterations) {
		print $ofh "====> iozone\n";
		@buf = `$cmd`;
		print $ofh @buf;
		# clear out the buffer for the next binary/iteration
		$#buf = -1;
	}
	print $ofh "====> endofiozone\n";
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
	my $read = 0;
	my $write = 0;
	my $randomread = 0;
	my $randomwrite = 0;
		
	# parse the buffer
	foreach (@$bufref) {
		if ($_ =~ /\s+Parent sees throughput for.* random writers\s+=\s+(\d+\.\d+).*/) {
			$randomwrite = main::max($1 / 1000, $randomwrite);
		}
		elsif ($_ =~ /\s+Parent sees throughput for.* random readers\s+=\s+(\d+\.\d+).*/) {
			$randomread = main::max($1 / 1000, $randomread);
		}
		elsif ($_ =~ /\s+Parent sees throughput for.* writers\s+=\s+(\d+\.\d+).*/) {
			$write = main::max($1 / 1000, $write);
		}
		elsif ($_ =~ /\s+Parent sees throughput for.* readers\s+=\s+(\d+\.\d+).*/) {
			$read = main::max($1 / 1000, $read);
		}
	}

	# build the hash with the data retrieved from parsing
	my $key = "$self->{SHORTNAME}\_read";
	$data{$key} = $read;
	my $key = "$self->{SHORTNAME}\_write";
	$data{$key} = $write;
	my $key = "$self->{SHORTNAME}\_randomread";
	$data{$key} = $randomread;
	my $key = "$self->{SHORTNAME}\_randomwrite";
	$data{$key} = $randomwrite;

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
	$self->{TEST_CLASS} = 'disk';
	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;
	
	return 1;
}


1;
