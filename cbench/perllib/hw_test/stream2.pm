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


package hw_test::stream2;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

streams

Cbench hw_test module that tests the performance of memory using
the new STREAM2 benchmark.

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
	my $path = "$main::bench_test/$main::TESTBINPATH/hwtests";
		
	my @buf = ();
	my @binlist = `cd $path;ls stream2-* | grep -v \\~`;

	if (defined $main::SMALL) {
		(defined $main::DEBUG) and print
				"DEBUG:$shortpackage\.run() doing SMALL mode runs\n";			
		# nothing to do differently
	}
	
	for my $i (1..$iterations) {
		for	(@binlist) {
			chomp $_;
			(/mpi/) and next;
			print $ofh "====> $_\n";
			main::run_single_process("$path/$_",\@buf);
			print $ofh @buf;
			# clear out the buffer for the next binary/iteration
			$#buf = -1;
		}
	}
	print $ofh "====> endofstreams\n";
}

sub parse {
	my $self = shift;
	my $bufref = shift;

	use Statistics::Descriptive;

	my %data;
	my $binary;
	my $fill = Statistics::Descriptive::Full->new();
	my $copy = Statistics::Descriptive::Full->new();
	my $dxapy = Statistics::Descriptive::Full->new();
	my $sum = Statistics::Descriptive::Full->new();

	# output sample...
	#
	# Smallest time delta is   9.53674316E-07
	# Size  Iter     FILL      COPY     DAXPY       SUM
	# 30    10   5890.8    9670.5   13937.3    3193.7      23.4
	# 43    10   6291.8   10116.5   14697.3    3331.9      17.4
	# 61    10   6597.9   10417.1   15257.4    3444.4      12.9
	# 88    10   6840.8   10645.3   15696.6    3508.7       9.3

	# parse the buffer
	# NOTE: streams runs a test process per cpu, so we have to
	#       parse the buffer as such and do some aggregation
	#       of data
	foreach (@$bufref) {
		if (/====> (\S+)/) {
			$binary = $1;
		}
		elsif (/\s+(\d+)\s+(\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)/) {
	    	$fill->add_data($3);
	    	$copy->add_data($4);
	    	$dxapy->add_data($5);
	    	$sum->add_data($6);
		}

		#(defined $main::DEBUG and $main::DEBUG > 2) and print
		#	"DEBUG:$shortpackage\.parse() process $binary, $copy_tmp, ".
		#	"$scale_tmp, $add_tmp, $triad_tmp\n";
	}

	# build the hash with the data retrieved from parsing
	my $key = "$self->{SHORTNAME}\_fill";
	$data{$key} = $fill->max();
	my $key = "$self->{SHORTNAME}\_copy";
	$data{$key} = $copy->max();
	my $key = "$self->{SHORTNAME}\_dxapy";
	$data{$key} = $dxapy->max();
	my $key = "$self->{SHORTNAME}\_sum";
	$data{$key} = $sum->max();

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


1;
