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

#
# This script is helps in parsing the summarized data reported
# by the nodehwtest_output_parse.pl script and generating
# simple "reports"
#

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
use Statistics::Descriptive;

GetOptions(
	'file=s' => \$file,
	'test=s' => \$testmatch,
	'gtabspercent=s' => \$gtabspercent,
	'negpercent=s' => \$negpercent,
	'text=s' => \$text,
	'ltactual=s' => \$ltactual,
	'gtactual=s' => \$gtactual,
	'brief' => \$brief,
	'debug:i' => \$DEBUG,
	'help' => \$help,
);

#
# process the command-line options
#
if (defined $help) {
    usage();
    exit;
}

(!defined $testmatch) and $testmatch = '.*';
(!defined $text) and $text = "BAD?";

@buf = ();


if (defined $file) {
	open(IN,"<$file") or die
		"Could not open $file for read ($!)";
	@buf = <IN>;
	close (IN);
}
else {
	@buf = <>;
}

(defined $DEBUG) and print "DEBUG: read in ".scalar(@buf)." lines from $file\n";

$parse = 1;
for $line (@buf) {
	$line =~ s/\033\[0m//g;
	($line =~ /Loaded characterized/) and next;
	if ($line =~ /Cbench nodehwtest output parser/) {
		$parse = 0;
	}
	if (!$parse) {
		($line =~ /Nodes with tests exceeding two standard deviations/) and $parse = 1;
		next;
	}

	if ($line =~ /Parsed \d+ iterations/) {
		$parse = 0;
		next;
	}

	next unless $line =~ /actual=/;
	chomp $line;
	(defined $DEBUG) and print "DEBUG: line=$line\n";
	($node,$test,$actual,$good,$delta,$deltasign,$deltapercent,$stddev,$samples) = $line =~
		/(\S+)\s+(\S+)\:\s+actual=(\d+\.\d+)\s+good=(\d+\.\d+)\s+delta=(\d+\.\d+)\s+\(([-+])(\d+\.\d+)\%\)\s+stddev=(\d+\.\d+)\s+\((\d+)\s+samples\)/;

	$tmp = "$test";
	next unless $tmp =~ /$testmatch/;

	(defined $DEBUG) and print "$node,$test,$actual,$good,$delta,$deltasign,$deltapercent\%,$stddev,$samples\n";

	if (defined $text) {
		$note = $text;
	}

	if (defined $gtabspercent) {
		$note .= " (test=$test, delta is $deltasign"."$deltapercent\% from std. deviation,".
				"actual=$actual,good=$good)" unless $brief;
		if ($deltapercent > $gtabspercent) {
			print "$node: $note\n";
		}
	}
	elsif (defined $negpercent) {
		$note .= " (test=$test, delta is $deltasign"."$deltapercent\% from std. deviation,".
				"actual=$actual,good=$good)" unless $brief;
		if ($deltapercent > $negpercent and $deltasign eq '-') {
			print "$node: $note\n";
		}
	}
	elsif (defined $ltactual) {
		$note .= " (test=$test, actual is $actual which is less than $ltactual)"
			unless $brief;
		if ($actual < $ltactual) {
			print "$node: $note\n";
		}
	}
	elsif (defined $gtactual) {
		$note .= " (test=$test, actual is $actual which is greater than $gtactual)"
			unless $brief;
		if ($actual > $gtactual) {
			print "$node: $note\n";
		}
	}
}

sub usage {
	print "USAGE: $0 \n" .
		"Cbench utility to help generate simple reports from data generated\n" .
		"by the nodehwtest_output_parse.pl script.\n" .
		"    --file <filename>    Parse the data from a file instead of STDIN\n".
		"    --text <string>      Descriptive text to printout with data points\n".
		"    --test <regex>       Parse data points from tests with names matching the\n".
		"                         given regext\n".
		"    --ltactual <num>     Flag tests if their actual value is less than <num>\n".
		"    --gtactual <num>     Flag tests if their actual value is greater than <num>\n".
		"    --negpercent <num>   Flag tests if their percent delta from standard deviation\n".
		"                         is NEGATIVE (i.e. the actual value is lower than the mean\n".
		"                         and the absolute value of the percent difference is greater\n".
		"                         than <num>\n".
		"    --gtabspercent <num> Flag tests if the absolute value of their percent delta from\n".
		"                         standard deviation is greater than <num>\n".
		"    --brief              Do not print out details, just node names basically\n".
		"    --debug <level>      Turn on debugging at the specified level\n";
}
