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


package hw_test::hpcc;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /hw_test::(\S+)/;

=head1 NAME

hpcc

Cbench hw_test module that uses the HPC Challenge MPI system
benchmark on a single node to test out cpu and memory performance.
This module will only work if the Cbench local mpich version of
HPCC has been compiled and installed into the nodehwtest test
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

	# HPCC is very picky and wants to write its output to
	# a file named hpccoutf.txt. So, we have to create a
	# little sandbox for HPCC to run in. After HPCC has run,
	# we'll grab contents of the output file and write it into
	# our output buffer.
	use File::Temp;
	
	# get a temporary directory, automatically clean it up when done
	my $rundir = File::Temp::tempdir(CLEANUP => 1);
	my $pwd = `/bin/pwd`;

	(defined $main::DEBUG) and print
		"DEBUG:$shortpackage\.run() temp directory = $rundir\n";
	
	# build the requisite content in the directory for HPCC to run
	#
	chdir $rundir;
	# symlink the binary
	system("ln -s $path/hpcc.ch_shmem hpcc");
	
	# build the hpccinf.txt input file for HPCC
	# read in config file generation template
	my $file = "$main::testset_path\/hpccinf_txt.in";
	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	my $hpccinf = <IN>;
	close(IN);
	$/ = "\n";

	# search and replace 
	my @Nvals = main::compute_N(1,1);
	my $num_Nvals = @Nvals;
	my $outbuf = $hpccinf;	
	$outbuf =~ s/HPCC_NUM_N_HERE/$num_Nvals/gs;
	$outbuf =~ s/HPCC_N_HERE/@Nvals/gs;
    $outbuf =~ s/HPCC_P_HERE/1/gs;
    $outbuf =~ s/HPCC_Q_HERE/1/gs;

	# write out the generated hpccinf.txt file
	$file = "$rundir\/hpccinf.txt";
	open (OUT,">$file") or do {
		print "ERROR:$shortpackage.run() Could not write $file ($!)\n";
		return;
	};
	print OUT $outbuf;
	close(OUT);

	# need a simple hosts file for mpirun
	$file = "$rundir\/hostlist";
	open (OUT,">$file") or do {
		print "ERROR:$shortpackage.run() Could not write $file ($!)\n";
		return;
	};
	print OUT "$main::hn\n";
	print OUT "$main::hn\n";
	close(OUT);

	# since hpcc can link with optimized BLAS libs and the libs
	# usually get the best performance using multiple threads within
	# the lib as opposed to multiple process instances of nodeperf,
	# we will assume that we only need to start one instance of
	# nodeperf
	my $numcpus = main::linux_num_cpus();
	$ENV{'OMP_NUM_THREADS'} = $numcpus;

	#
	# Ok, should be ready to run HPCC
	my $cmd = "$mpirun -machine shmem ".
		"-machinefile $rundir\/hostlist -np 1 $path/hpcc.ch_shmem";
	$cmd = "$mpirun -machinefile $rundir\/hostlist -n 1 $path/hpcc" if defined($ENV{CBENCHSTANDALONEDIR});
	(defined $main::DEBUG) and print
		"DEBUG:$shortpackage\.run() cmd = $cmd\n";
	system("$cmd");
	
	# now we need to read the output of HPCC from its
	# output file
	my $file = "$rundir\/hpccoutf.txt";
	open (IN,"<$file") or do {
		print "ERROR:$shortpackage.run() Could not read $file ($!)\n";
		return;
	};
	@buf = <IN>;
	close(IN);

	print $ofh @buf;
	
	chdir $pwd;
}

sub parse {
	my $self = shift;
	my $bufref = shift;

	my %data;
	my $key;
	my $fail = 0;
	my $completed = 0;
	my $started = 0;

	# parse the buffer
	foreach (@$bufref) {
		if (/HPC Challenge Benchmark/) {
			$started = 1;
		}
		elsif (/Begin of Summary/) {
			$completed = 1;
		}
		elsif ($_ =~ /HPL_Tflops=(\d+\.\d+)/) {
			$key = "$self->{SHORTNAME}\_hpl_gflops";
			$data{$key} = $1 * 1000;
		}
		elsif ($_ =~ /StarDGEMM_Gflops=(\d+\.\d+)/) {
			$key = "$self->{SHORTNAME}\_dgemm_gflops";
			$data{$key} = $1;
		}
		elsif ($_ =~ /PTRANS_GBs=(\d+\.\d+)/) {
			$key = "$self->{SHORTNAME}\_ptrans_gbs";
			$data{$key} = $1;
		}
		elsif ($_ =~ /StarRandomAccess_GUPs=(\d+\.\d+)/) {
			$key = "$self->{SHORTNAME}\_randomaccess_gups";
			$data{$key} = $1;
		}
		elsif ($_ =~ /StarSTREAM_Triad=(\d+\.\d+)/) {
			$key = "$self->{SHORTNAME}\_stream_triad";
			$data{$key} = $1;
		}
		elsif ($_ =~ /StarFFT_Gflops=(\d+\.\d+)/) {
			$key = "$self->{SHORTNAME}\_fft_gflops";
			$data{$key} = $1;
		}
		elsif ($_ =~ /FAILED/) {
			$fail++;
		}
	}
	
	if ($started and $completed) {
		$key = "$self->{SHORTNAME}\_fail";
		$data{$key} = $fail;
	}
	elsif ($started and !$completed) {
		$key = "$self->{SHORTNAME}\_didnotfinish";
		$data{$key} = 1;
	}
	else {
		$key = "$self->{SHORTNAME}\_runerror";
		$data{$key} = 1;
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
