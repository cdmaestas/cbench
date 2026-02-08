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

use Getopt::Long;

GetOptions( 'nproc=i'  => \$nproc,
);

(!defined $nproc) and die
	"--nproc <numprocs> param required";

#$nproc = 1017;
$start = int sqrt($nproc);
print "sqrt of $nproc = ".sqrt($nproc)."\n";
$delta = 60;

print "NPROCS=$nproc\n";
$adjdelta = $delta;
if ($start - $delta < 0) {
	$adjdelta = $start - 2;
}

for ($q=$start-$adjdelta;$q<=$start+$delta;$q++) {
    ($q == 0.0) and next;
    $p = $nproc / $q;
    if (($nproc % $q) == 0) {
	$ratio = $q/$p;
    	print "P=$p Q=$q   ratio=$ratio";
        
        if ($ratio >= 1.0 and $ratio <= 4.0) {
        	print "    * DECENT RATIO\n";
        }
        else {
        	print "\n";
        }
    }
}
