#!/usr/bin/perl
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
# vim: syntax=perl tabstop=4

# need to know where everything cbench lives!
BEGIN {
    die "Please define CBENCHOME!\n" if !defined($ENV{CBENCHOME});
}
use lib $ENV{CBENCHOME};
require "cbench.pl";
$CBENCHOME = $BENCH_HOME = $ENV{CBENCHOME};

use Getopt::Long;

GetOptions(
	'nproc=i'  => \$nproc,
	'ppn=i' => \$ppn,
	'utilization=s' => \$util,
	'memory=i' => \$mem,
	'help' => \$help,
);
(defined $help) and usage();
(!defined $nproc or !defined $ppn) and usage();

(defined $mem) and $memory_per_node = $mem;
$nodes = $nproc / $ppn;
$totmem = $nodes * $memory_per_node * 1024 *1024;
$totMB = $totmem / 1024;
print "total nodes = $nodes  total mem = $totMB MB\n";

(defined $util) and @memory_util_factors = split(',',$util);
print "memory_util_factors = @memory_util_factors\n";

#@Nval = test_N($nproc,$ppn);
#print "test Nvals = " . join(' ',@Nval) . "\n";

@Nval = compute_N($nproc,$ppn);
print "cbench Nvals = " . join(' ',@Nval) . "\n";



sub test_N {
	my $np = shift;
	my $ppn = shift;

	my $nodes = $np / $ppn;
	my $totmem = $nodes * $memory_per_node * 1024 *1024;
	my $totMB = $totmem / 1024;
	print "total nodes = $nodes  total mem = $totMB MB\n";
	$totmem = $totmem / 8;
	my @Nvals = ();

	foreach (@memory_util_factors) {
		my $temp = $totmem * $_;
		$temp = int sqrt($temp);
		push @Nvals, $temp;
	}
	return @Nvals;
}

sub usage {
	print "USAGE: $0 --nproc <np> --ppn <num> [--util <frac1,frac2,..>] [--memory <num MB>] \
	--nproc		number of proceses, i.e. mpi ranks \
	--ppn		processes per node \
	--util		memory utilization factors, e.g. \
					--util 0.5,0.6,0.7 \
	--memory	memory per node in MB \
";
	exit 0;
}
