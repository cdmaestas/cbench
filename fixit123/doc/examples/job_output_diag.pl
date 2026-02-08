#!/usr/bin/perl

# pickup the custom parse filters from cbench
require "/apps/cbench/cluster.def";

use Data::Dumper;
use Time::localtime;
use File::stat;
use Getopt::Long;
use Term::ANSIColor qw(color :constants);

GetOptions(
    'nocustomparse' => \$nocustomparse,
    'debug' => \$debug,
);

my $file = $ARGV[0];


open(IN,"<$file") or exit 1;
undef $/;
my $bufraw = (<IN>);
close(IN);
$/ = "\n";

# remove any ansi color escape sequences
$bufraw =~ s/\033\[0m//g;

if (!defined $nocustomparse) {
	$stats = stat($file);
	$stamp = ctime($stats->mtime);
	print BOLD MAGENTA "File ";
	print BOLD GREEN "$file ";
	print BOLD MAGENTA "last modified: ";
	print BOLD GREEN "$stamp";
	print RESET "\n";
}

if ($bufraw =~ /VAPI/gs) {
	system("/projects/contrib/fixit/vapi_diag.pl $file");
}
if ($bufraw =~ /Catastrophic/gs) {
	system("/projects/contrib/fixit/vapi_diag.pl $file");
}

# remove extra unneeded junk from things like mpiexec -v-v-v
$bufraw =~ s/do_child\:.*\n//g;
$bufraw =~ s/aggregate_output\://g;
$bufraw =~ s/readsome\:\s+fd \d+ has \d+ bytes//g;
#$bufraw =~ s/fd \d+ has \d+ bytes//g;
$bufraw =~ s/readsome: release ownership, give to -1\n//g;
$bufraw =~ s/output to stream.*from 127.0.0.1\://g;
#$bufraw =~ s/output from process at .*select bits left//g;
$bufraw =~ s/env\s+\d+\s+\S+\=.*\n//g;

# convert to an array buffer
@buf = split('\n',$bufraw);

my $nodelist = mpiexec_ranktonode_parse(\@buf);
#print Dumper (%$nodelist);

$cmd = "grep --color=always -P \'MPI.*Internal\\s+MPI\\s+error\' $file ";
system($cmd);

if (!defined $nocustomparse) {
	# use the Cbench custom parse filters to find errors too
	# we will need a data structure to keep track of hits to
	# the custom parse filters, so well build a hash with
	# the same keys as the %parse_filters array (from
	# cluster.def)
	my %filterhits = ();
	foreach my $k (keys %parse_filters) {
		$filterhits{$k} = 0;
	}				

	foreach my $l (@buf) {
		(defined $debug) and print "$l\n";
		foreach my $filter (keys %parse_filters) {
			if ((@capture) = $l =~ /$filter/) {
				# currently, we only print out any information
				# about a custom parse filter hit on the 
				# first hit
				($filterhits{$filter} > 0) and next;
				
				# need to assign a scalar variable for each
				# capture variable
				foreach my $n (0..$#capture) {
					#print "$n = $capture[$n]\n";
					my $t = $n + 1;
					${"var\_$t"} = $capture[$n];
				}

				# now replace any capture variables in the
				# the parse filter output string
				my $temp = $parse_filters{$filter};
				$temp =~ s/\$(\w+)/${"var_$1"}/ge;
				
				print BOLD YELLOW, "**PARSEMATCH**";
				print BOLD WHITE, "=> ";
				print BOLD CYAN, "$temp";
				print RESET "\n";
				$filterhits{$filter}++;
			}
		}
	}
}

if ( $bufraw =~ /mpiexec.*warning/igs) {
	foreach my $l (@buf) {
		if ($l =~ /mpiexec:\s+Warning:\s+task\s+(\d+)\s+died\s+with\s+signal\s+(\S+)\s+\((.*)\)/) {
			$task = $1;
			$signal = $3;
			if (exists $nodelist->{$task}) {
				$node = $nodelist->{$task};
			}
			else {
				next;
			}
			print "MPIEXEC WARNING: TASK DIED, signal ($signal) from task $task (node $node)\n";
			
		}
	}
}

# routine used to parse the passed in buffer(s) for nodelist information,
# i.e. the rank-to-nodename mapping, for mpiexec
sub mpiexec_ranktonode_parse {
	# should be one or more buffer references passed in,
	# they are ordered according to the array returned
	# by the JOBLAUNCHMETHOD_nodelist_files() routine
	my @bufrefs = @_;
	
	my %nodelist = (
		'NUMPROCS' => 0,
	);

	foreach my $txtbuf (@bufrefs) {
		foreach my $l (@{$txtbuf}) {
			if ($l =~ /mpiexec\:.*start evt \d+ task (\d+) on (\S+)\./ or
            	$l =~ /mpiexec\: process_start_event: evt \d+ task (\d+) on (\S+)\./) {
				$nodelist{'NUMPROCS'}++;
				$nodelist{$1} = $2;
			}
		}
	}
	return \%nodelist;
}
