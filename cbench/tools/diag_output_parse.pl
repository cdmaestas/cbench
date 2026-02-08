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

# Utility to read in from output_parse_customparse.pl and parse the data

# need to know where everything cbench lives!
BEGIN {
    die "Please define CBENCHOME!\n" if !defined($ENV{CBENCHOME});
}
use lib $ENV{CBENCHOME};
require "cbench.pl";
$CBENCHOME = $BENCH_HOME = $ENV{CBENCHOME};

# add Cbench perl library to the Perl search path
use lib "$ENV{CBENCHOME}\/perllib";

# enable/disable color support appropriately
detect_color_support();

use Getopt::Long;
use Term::ANSIColor qw(:constants color);
$Term::ANSIColor::AUTORESET = 1;

my $threshold = 1;
my $debug = 0;

GetOptions(
	'sourceonly'  => \$sourceonly,
	'destonly'  => \$destonly,
	'sourcedestonly'  => \$sourcedestonly,
	'threshold=i'  => \$threshold,
	'debug'  => \$debug,
);

# read in from stdout pipe
while (defined ($_ = <STDIN>)) {
	s/\033\[0m//g;	# cleanup color crap
	next if /^$/;	#Skip blank lines
	chomp;

	$dest = "null";
	# OMPI Parse matching
#**PARSEMATCH**(vasp.out) =>  OMPI error 'WORK REQUEST FLUSHED ERROR ' with status 5 (an966 to bn274)
	if (/\*\*PARSEMATCH\*\*\((\S+)\) =>  OMPI error 'WORK REQUEST FLUSHED ERROR ' with status (\d+) \((.n\d+) to (.n\d+)\)/) {
		$parse_message = "OMPI_ERROR_WORK_REQUEST_FLUSHED_ERROR";
		$outputfile = $1;
		$src = $3;
		$dest = $4;
#**PARSEMATCH**(vasp.out) =>  OMPI error 'RETRY EXCEEDED ERROR ' with status 12 (an966 to bn274)
	} elsif (/\*\*PARSEMATCH\*\*\((\S+)\) =>  OMPI error 'RETRY EXCEEDED ERROR ' with status (\d+) \((.n\d+) to (.n\d+)\)/) {
		$parse_message = "OMPI_ERROR_RETRY_EXCEEDED_ERROR";
		$outputfile = $1;
		$src = $3;
		$dest = $4;
	} else {
		#print "NEW UNMATCHED ERROR from CBENCH OUTPUT PARSER!\n";
		#print "====$_====\n";
		print "$_\n";
	}

print "$src -- $dest -- $outputfile -- $parse_message\n" if $debug;
	# setup a hash where parse_message is key and has an array of source dest ndoes
	my $vsource = "SOURCE:$src" if $src;
	if ($dest ne "null") {
		my $vdest = "DEST:$dest" if $dest ne "null";
		my $vsd = "SOURCE::$src<->DEST::$dest";
		# check if vdest and vsd is defined
		if (!defined $output_parser_messages{$parse_message}{$vdest}) {
			$output_parser_messages{$parse_message}{$vdest} = 1;
		} else {
			$output_parser_messages{$parse_message}{$vdest}++;
		}
		if (!defined $output_parser_messages{$parse_message}{$vsd}) {
			$output_parser_messages{$parse_message}{$vsd} = 1;
		} else {
			$output_parser_messages{$parse_message}{$vsd}++;
		}
	}

	if ($src) {
		if (!defined $output_parser_messages{$parse_message}{$vsource}) {
			$output_parser_messages{$parse_message}{$vsource} = 1;
		} else {
			$output_parser_messages{$parse_message}{$vsource}++;
		}
	}
}

# https://www.linuxnotes.net/perlcd/prog/ch09_04.htm
foreach my $vm (sort keys %output_parser_messages) {
	print BOLD RED "$vm\n";
	my ($nd,$cnt);
	foreach $nd (sort keys %{$output_parser_messages{$vm}}) {
		print "$output_parser_messages{$vm}{$nd} < $threshold\n" if $debug >= 5;
		next if $output_parser_messages{$vm}{$nd} < $threshold;
		next if ($nd =~ /SOURCE/) and $destonly;
		next if ($nd =~ /DEST/) and $sourceonly;
		next if ($nd !~ /SOURCE/ or $nd !~ /DEST/) and $sourcedestonly;
		print RESET "NODE: ";
		print BOLD BLUE "$nd ";
		print RESET "COUNT: ";
		print BOLD YELLOW ON_BLUE "$output_parser_messages{$vm}{$nd}";
		print RESET "\n";
	}
}


sub usage {
    print   "USAGE: output_parse_customparse.pl | $0 --threshold <num>\n";
    print   "Cbench script to analyze a job parse data printed from output parsers\n".
            "   --threshold <num>   Print when threshold is reached (default 1)\n".
            "   --sourcedestonly    Print source and dest data only\n".
            "   --sourceonly        Print source data. only\n".
            "   --destonly          Print destination data. only\n";
}
