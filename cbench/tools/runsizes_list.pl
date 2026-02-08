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

# Simple utility to generate a comma separated list of runsize suitable for
# passing to the --runsizes parameter of a gen_jobs script. Allow filtering
# common types of values like power of two for instance

# need to know where everything cbench lives!
BEGIN {
    die "Please define CBENCHOME!\n" if !defined($ENV{CBENCHOME});
}
use lib $ENV{CBENCHOME};
require "cbench.pl";
$CBENCHOME = $BENCH_HOME = $ENV{CBENCHOME};

use Getopt::Long;

GetOptions(
	'powof2|pof2' => \$pof2,
	'square' => \$square,
	'cube' => \$cube,
	'maxprocs=i' => \$max,
	'minprocs=i' => \$min,
	'mult=i' => \$mult,
	'mult256' => sub { $mult = 256 },
	'mult100' => sub { $mult = 100 },
	'mult3' => sub { $mult = 3 },
	'addr=i' => \$addr,
	'tryall' => \$tryall,
	'help' => \$help,
);

if (defined $help) {
    usage();
    exit;
}

(defined $max) and $max_procs = $max;

@list = ();

if (defined $tryall) {
	$m = $max_procs;
	for (1..$m) {
		push @sizes, $_;
	}
}
else {
	@sizes = @run_sizes;
}

foreach $n (@sizes) {
	($n > $max_procs) and next;
	(defined $min and $n < $min) and next;
	(defined $pof2 and power_of_two($n)) and (push @list, $n and next);
	(defined $square and perfect_square($n)) and (push @list, $n and next);
	(defined $cube and int_cube_root($n)) and (push @list, $n and next);
	(defined $mult and multiple_of_N($n,$mult)) and (push @list, $n and next);
}

#Look at max possible run size and do the addr thing to it
addr_of_N() if $addr;

print join(',',@list), "\n";


sub multiple_of_N {
	my $nprocs = shift;
	my $N = shift;
	
	my $mult = int ($nprocs/$N);
#	print "$nprocs $N $mult\n";
	(($mult * $N) == $nprocs) and return 1;
	return 0;
}

#
# routine to generate a sequence w/ N as the addition term
#	e.g. N=2, minprocs=4, manxprocs=90 => 2+4*0, 2+4*1, 2+4*2, ...., 
#
sub addr_of_N {
	my $M=0;
	if ($max) {
		$M=$max;
	} else {
		$M=$sizes[-1];
	}
	for (my $i=1; $i*$addr <= $M; $i++) {
		my $rn= $i*$addr;
		(defined $min and $rn < $min) and next;
		push @list, $rn;
	}
}


sub usage {
    print "USAGE: $0\n" .
          "    --pof2      Include powers of two\n".
		  "    --square    Include perfect squares\n".
		  "    --cube      Include perfect cubes\n".
		  "    --maxprocs  Max procssor count\n".
		  "    --minprocs  Min procssor count\n".
		  "    --mult256   Include multiples of 256\n".
		  "    --mult3   Include multiples of 3\n".
		  "    --mult100   Include multiples of 100\n".
		  "    --mult=M    Include multiples of M\n".
		  "    --tryall    Try all values between 1 and maxprocs\n";
		  "    --addr=N    From minprocs value add N to it until you reach max procs\n";
}

