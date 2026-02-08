#!/usr/bin/perl
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


# Top-level script in the Cbench test set tree to recursively call
# the *_gen_jobs.pl script for each test set.

# need to know where everything cbench lives!
BEGIN {
	die "Please define CBENCHOME!\n" if !defined($ENV{CBENCHOME});
}
use lib $ENV{CBENCHOME};
require "cbench.pl";
$CBENCHOME = $BENCH_HOME = $ENV{CBENCHOME};

use Getopt::Long;

# pass_through lets "non options" stay in ARGV w/o raising an error
Getopt::Long::Configure("pass_through");

GetOptions( 'debug:i' => \$DEBUG,
            'dryrun' => \$dryrun,
			'tsetexclude|texclude=s' => \$tsetexclude,
			'tsetinclude|tinclude=s' => \$tsetinclude,
            'help' => \$help,
);


if (defined $help) {
        usage();
        exit;
}
$bench_test = get_bench_test();

$pwd = `pwd`;
chomp $pwd;
$totaljobs = 0;

for $f (`/bin/ls -1`) {
	chomp $f;
	next if ($f eq "." || $f eq "..");
	(! -d $f) and next;
	# ignore certain directories because they are not test sets or are
	# uniquely behaving test sets like nodehwtest
	($f =~ /nodehwtest|perllib|bin|sbin|mpich|tools|templates/) and next;
	(defined $tsetexclude and $f =~ /$tsetexclude/) and next;
	(defined $tsetinclude) and next unless $f =~ /$tsetinclude/;

	print "Generating jobs in ". uc($f) . " testset\n";
	
	chdir $f;
	
	# build the command line
	$cmd = "./$f\_gen_jobs.pl ";
    (defined $DEBUG) and $cmd .= " --debug $DEBUG ";
    $cmd .= join(' ',@ARGV);
	
	debug_print(1, "DEBUG: cmd=$cmd\n");
	($dryrun) and print "$cmd\n";
	system("$cmd | tee /tmp/cbench.tmp$$") unless $dryrun;
	my @tmp = `cat /tmp/cbench.tmp$$` unless $dryrun;
	foreach (@tmp) {
		(/Generated (\d+) jobs in the (\S+) testset/) and $totaljobs += $1;
	}
	
	chdir $pwd;
}

print "Total jobs generated: $totaljobs\n";
unlink "/tmp/cbench.tmp$$";

sub usage {
    print "USAGE: $0 \n";
    print "Cbench script to generate jobs in the all test sets\n".
          "   --tsetinclude <regex>  This limits the starting up of jobs to jobs\n" .
		  "                          in testsets with names that match the regex.\n" .
		  "                          e.g.\n".
		  "                            --tsetinclude \'mpisanity|bandwidth\'\n".
		  "                          only starts jobs in the MPISANITY and BANDWIDTH\n".
		  "                          testsets.\n".
          "   --tsetexclude <regex>  This limits the starting up of jobs to jobs\n" .
		  "                          in testsets with names that DO NOT match the regex.\n" .
		  "                          e.g.\n".
		  "                            --tsetexclude \'mpisanity|bandwidth\'\n".
		  "                          only starts jobs in testsets other than the MPISANITY\n".
		  "                          and BANDWIDTH testsets.\n".
		  "                          testsets.\n".
          "   --dryrun               Show what would be done without doing it\n".
          "   --debug <level>        Turn on debugging at the specified level\n\n".
          "   All other command-line options are passed on to the\n".
          "   specific *_gen_jobs.pl scripts\n";
}

