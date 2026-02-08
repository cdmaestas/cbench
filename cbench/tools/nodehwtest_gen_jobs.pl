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

# need to know where everything cbench lives!
BEGIN {
    # need to know where everything cbench lives!
    our $cbbasedir = undef;
    if (defined($ENV{CBENCHSTANDALONEDIR})) {
      $cbbasedir = $ENV{CBENCHSTANDALONEDIR};
    } elsif (defined($ENV{CBENCHTEST})) {
      $cbbasedir = $ENV{CBENCHTEST};
    } elsif (defined($ENV{CBENCHOME})) {
      $cbbasedir = $ENV{CBENCHOME};
    } else {
      die "Please define CBENCHOME or CBENCHTEST or CBENCHSTANDALONEDIR!\n"; 
    }
}

use lib $cbbasedir;
use lib "$cbbasedir/perllib";
require "cbench.pl";
$CBENCHOME = $BENCH_HOME = $cbbasedir;

use Getopt::Long;

GetOptions( 
	'nodelist=s' => \$nodelist,
	'ident=s' => \$ident,
	'debug:i' => \$DEBUG,
	'help' => \$help,
);

if (defined $help) {
	usage();
	exit;
}

if (!defined $nodelist) {
	print   "Must specify the list of nodes that belong to the test\n".
			"identifier with the --nodelist parameter.\n";
	usage();
	exit;
}

$testset = 'nodehwtest';
$bench_test = get_bench_test();
$testset_path = "$bench_test/$testset";
$DEBUG and print "DEBUG: $bench_test $testset_path\n";

(!defined $ident) and $ident = $cluster_name . "1";

# make sure the directory is there with the proper test identification
(! -d "$testset_path\/$ident") and mkdir "$testset_path\/$ident",0750;

# Generating jobs in the nodehwtest test set is quite a bit different
# than in other Cbench test sets. Primarily this is because nodehwtest
# is not a scaling study and thus doesn't need to generate a bunch of
# different testing scripts and different sizes.
#
# Right now all it really does is coordinate information. Specifically,
# it embeds information about what nodes belong to a given test identifier
# within the test identifier directory.


# save the node list information into the test ident directory
$outfile = "nodelist";
open (OUT,">$testset_path\/$ident\/$outfile") or die
	"Could not write $testset_path\/$ident\/$outfile ($!)";
print OUT "nodelist=$nodelist\n";
close(OUT);

sub usage {
    print "USAGE: $0 \n";
    print "Cbench script to generate jobs in the $testset test set\n".
		  "   --nodelist <list>  A list of nodes that will be correlated to\n".
		  "                      the test ident being generated. There are\n".
		  "                      no restrictions on the number of test ids\n".
		  "                      or which nodes belong to which test ids. The\n".
		  "                      nodelist information is used by the\n".
		  "                      nodehwtest_start_jobs.pl script to intelligently\n".
		  "                      manage nodehwtest work. This parameter uses the\n".
		  "                      common cluster node list syntax like pdsh. For\n".
		  "                      example:\n".
		  "                        --nodelist n[0-2,5,10-25]\n".
		  "                        --nodelist cluster[100-200,300,310,400-500]\n".
          "   --ident <name>     identifying string for the test\n".
		  "   --debug <level>    turn on debugging at the specified level\n";
}
