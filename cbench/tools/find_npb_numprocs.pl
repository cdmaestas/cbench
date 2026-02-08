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

# Simple utility to find the number of processors that are
# <= to the specified number which are a perfect square and
# a power of two.  This is useful for figuring out the closest
# number processors to use for a NAS Parallel Benchmark run in
# a script.


use Getopt::Long;

GetOptions( 'nproc=i'  => \$nproc,
);

(!defined $nproc) and die
	"--nproc <numprocs> param required";

$tmpprocs = $nproc;
$found_pof2 = 0;
$found_square = 0;

while ((!$found_pof2 or !$found_square) and $tmpprocs > 0) {
	if (power_of_two($tmpprocs) and !$found_pof2) {
    	$found_pof2 = $tmpprocs;
    }

	if (perfect_square($tmpprocs) and !$found_square) {
    	$found_square = $tmpprocs;
    }
    $tmpprocs--;
}

print "closest power of two =$found_pof2\n";
print "closest perfect square =$found_square\n";

# return true if the scalar is a perfect square
sub perfect_square {
    my $nprocs = shift;

    my $root = int sqrt($nprocs);
    (($root * $root) == $nprocs) and return 1;
    return 0;
}

# return true if the scalar is a power of two
sub power_of_two {
    my $nprocs = shift;

    my $power = log2($nprocs);
    ((2 ** $power) == $nprocs) and return 1;
    return 0;
}

# return the base 2 logarithm of a scalar as an Integer
sub log2 {
    my $n = shift;

    my $power = log($n)/log(2);
    return int $power;
}
