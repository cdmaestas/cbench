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
# This script is responsible for parsing all the output files from
# the Cbench node_hw_test utility and then doing something helpful
# with the data!  There could be a lot of output data to parse
# potentially.  There could be many test identifier groupings, many
# runs for each node within each identifier, and several iterations
# within each run.
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

# enable/disable color support appropriately
detect_color_support();

use Getopt::Long;
use Statistics::Descriptive;
use Data::Dumper;
use Term::ANSIColor qw(color :constants);

GetOptions(
	'quiet' => \$quiet,
	'noerrors' => \$noerrors,
	'class=s' => \$class,
	'characterize' => \$characterize,
	'iterationanalyze' => \$iterationanalyze,
	'savetargets:s' => \$savetarget,
	'loadtargets:s' => \$loadtarget,
	'lastnruns=i' => \$lastnruns,
	'onlyrun=i' => \$onlyrun,
	'ident|multiident=s' => \$ident,
	'match=s' => \$match,
	'dplot=s' => \$dplot,
	'usecwd' => \$usecwd,
	'warn' => \$warn,
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

if (defined $onlyrun and defined $lastnruns) {
	print BOLD RED "Cannot use --onlyrun and --lastnruns parameters together.\n\n";
	usage();
	exit;
}

if (defined $savetarget and ! defined $characterize) {
	print BOLD RED "Cannot use --savetarget without --characterize\n\n";
	usage();
	exit;
}

# if dplotting was requested, parse the params
if (defined $dplot) {
	@dplotparams = split(',',$dplot);
	(defined $DEBUG) and print "DEBUG:dplotparams=@dplotparams\n";
}

if (!defined $class) {
	# no work specified, process anything we find!
	$class = '.*'
}

# check if a list of idents was specified
if (defined $ident and $ident =~ /\,/) {
	@identlist = split ',',$ident;
	$ident = $identlist[0];
}
elsif (defined $ident) {
	push @identlist, $ident;
}
elsif (!defined $ident) {
	$ident = $cluster_name . "1";
	push @identlist, $ident;
}

(!defined $iterations) and $iterations = 1;

$testset = 'nodehwtest';
$bench_test = get_bench_test();
$testset_path = "$bench_test/$testset";
(defined $usecwd) and $testset_path = $ENV{PWD};
$DEBUG and print "DEBUG: $bench_test $testset_path\n";

# hash to hold gathered data organized by node name
my %nodehash;
my $nodehashref = \%nodehash;

# hash to hold references to Statistics::Descriptive stats
# variable objects
my %statvars = ();	

# hash to hold statistical target value data that is either read in
# from a target values file or is calculated using Statistics::Descriptive
# from parsed data
my %target = ();

# hash to hold strings from parsed data
my %stringvars = ();

# string of tests that fall into the "pass/fail" category
my $passfail = '(streams_failed)|(fpck_fail)|(hpcc_fail)|(memtester_fail)|(memtester_incomplete)|(nodeperf_error)|(npb_error)|(stress_disk_fail)|(stress_cpu_fail)|(ctcs_memtst_fail)|(ctcs_memtst_incomplete)';

# if we aren't running in a characterize mode of operation, then 
# attemp to load target values from the target values file
if (!defined $characterize) {
	if (load_target_values()) {
		# loading target values failed for some reason, turn on
		# characterize mode
		$characterize = 1;
	}
}

# hash to hold some summary data about work that was done during the run
my %summary = (
	'files' => 0,
	'iterations' => 0,
);

# Print out a summary of what work is going to be done based on
# the command-line parameters
if (!defined $quiet) {
    print GREEN "Cbench nodehwtest output parser:\n";
	print RESET, "  Parsing test identifiers: ";
	print BOLD WHITE, join(' ',@identlist);
	print RESET "\n";
    if (defined $characterize) {
	    print "  Running CHARACTERIZE mode\n";
	    if (defined $savetarget) {
		    print "  Characterized target values will be saved to file\n";
	    }
	    else {
		    print "  Characterized target values will NOT be saved to file\n";
	    }
    }
    if (defined $iterationanalyze) {
	    print "  Analyzing number of iterations run per node\n";
    }
    if (defined $onlyrun) {
	    print "  Parsing ONLY run number $onlyrun from each node\n";
    }
    elsif (defined $lastnruns) {
	    print "  Parsing the last $lastnruns runs from each node\n";
    }
    else {
	    print "  Parsing only the latest run from each node\n";
    }
    print "\n";
}

# we want to do this after we print out the run conditions just above
(!defined $lastnruns) and $lastnruns = 1;

my $start = time;

# load all the hw_test modules, we'll need them for parsing
# chunks of the outputs
my %test_modules;
load_hwtest_modules(\%test_modules,*STDOUT);

#
# DO THE WORK OF PARSING ALL THE OUTPUT!
$| = 1;

# parse new data
foreach (@identlist) {
	parse_ident($_);
}

#print Dumper (%nodehash);
#print Dumper (%statvars);

if (defined $characterize) {
	# compute the stats that characterize the pool of test data
	# that was parsed
	for $k (keys %statvars) {
		$target{$k}{'mean'} = $statvars{$k}->mean();
               $target{$k}{'min'} = $statvars{$k}->min();
		$target{$k}{'max'} = $statvars{$k}->max();
		$target{$k}{'stddev'} = $statvars{$k}->standard_deviation();
		$target{$k}{'count'} = $statvars{$k}->count();
	}

	# print out the computed characterization parameters
	print GREEN "\n\nCHARACTERIZED TARGET VALUES:";
	print RESET "\n";
	for $k (sort {$a cmp $b} keys %target) {
		my $tmpstr = "";

		$tmpstr .= color('bold magenta') . "$k: ";

		for $val (('mean','max','min','stddev')) {
			$tmpstr .= color('bold white') . "$val=";
			$tmpstr .= color('bold cyan') . sprintf("%0.4f ",$target{$k}{$val});
		}
		print "$tmpstr";
		print RESET " \(";
		print BOLD, WHITE, "sample count=";
		print BOLD, CYAN, "$target{$k}{'count'}";
		print RESET "\)\n";
	}
	print "\n\n";
	
	# save the characterized target parameters to the target values file
	(defined $savetarget) and save_target_values();
}

#print Dumper (%target);

#
# Here is the guts of using the statistics that characterize the tests
# on a set of nodes to flag nodes that fall outside some statistical
# heuristic.
#
# Nodes are flagged based on test values differing from the test mean
# by greater than two standard deviations.

# First we'll flag nodes with test values that exceed twice the standard
# deviation. If I'm understanding my basic statistics correctly, test
# values that differ from the mean by greater than 2*stddev have a
# 95% chance of truly indicating a bad value.
if (! defined $noerrors) {
	print BOLD RED, "\nNodes with tests exceeding two standard deviations (95% probability):" unless defined $quiet;
	print RESET "\n" unless defined $quiet;
	for $node (sort {$a cmp $b} keys %nodehash) {
		for $k (sort {$a cmp $b} keys %{$nodehashref->{$node}}) {

			($k =~ /maxrunid|iterations/) and next;
			# the node's value for the given test may be a mean of a set of
			# values, so compute that. clear any previous stats data first though
			my $tmpstat = Statistics::Descriptive::Full->new();
			$tmpstat->add_data(@{$nodehashref->{$node}->{$k}});
			my $val = $tmpstat->mean();
			
			# if a target value does not exist for this datapoint, don't
			# compute anything, just warn
			if (! exists $target{$k}) {
				(defined $DEBUG or defined $warn) and print BOLD RED "WARNING: ";
				(defined $DEBUG or defined $warn) and print RESET "data point \'$k\' not in target values...ignoring\n";
				next;
			}

			# now compute how the node's data for this data point
			# compares to the the statistical characteristics for this
			# test
			my $delta = abs($val - $target{$k}{'mean'});
			my $deltasign;
			if ($val < $target{$k}{'mean'}) {
				$deltasign = '-';
			}
			else {
				$deltasign = '+';
			}
			($delta > 0) or next;
			if ($delta >= (2*$target{$k}{'stddev'})) {
				my $delta_percent = ($target{$k}{'stddev'} == 0) ?
					$delta : $delta / $target{$k}{'stddev'};
				$delta_percent *= 100;

				print BOLD MAGENTA "$node ";
				print BOLD CYAN "$k";
				print RESET ": ";
				print RESET "actual=";
				printf ("%s%0.4f",color('bold red'),$val);
				print RESET " good=";
				printf ("%s%0.4f",color('bold green'),$target{$k}{'mean'});
				print RESET " delta=";
				printf ("%s%0.4f",color('bold red'),$delta);
				print RESET " ($deltasign";
				printf ("%s%0.1f%%",color('bold yellow'),$delta_percent);
				print RESET ") stddev=";
				printf ("%s%0.4f",color('bold yellow'),$target{$k}{'stddev'});
				printf (" %s(%d samples)\n",color('reset'),$tmpstat->count());
	#				$val,$target{$k}{'mean'},
	#				$delta,$deltasign,$delta_percent,$target{$k}{'stddev'},$tmpstat->count());
			}
			$tmpstat = undef;
		}
	}
}


my $end = time;
my $delta = ($end - $start) / 60;

if (!defined $quiet) {
	# print out summary data about the run
	my $totalnodes = keys %{$summary{'nodelist'}};
	print RESET GREEN "\nSummary:\n";
	print RESET "Parsed $summary{'iterations'} iterations in $summary{'files'} files".
		" for $totalnodes nodes ";
	printf "in %0.1f minutes", $delta;
	print RESET "\n";
}

# If specified, do a bit of analysis on the number of iterations run on
# each node
if (defined $iterationanalyze) {
	print RESET GREEN "\nAnalyzing the number of test iterations run on each node:\n";
	# run stats on the number of iterations over all recorded nodes
	my $iter_statvar = Statistics::Descriptive::Full->new();
	for $node (sort {$a cmp $b} keys %nodehash) {
    	# if --match used, make sure we honor it
    	(defined $match and $node !~ /$match/) and next;
    	$iter_statvar->add_data($nodehashref->{$node}->{'iterations'});
    }
	my $iter_mean = $iter_statvar->mean();
	my $iter_min = $iter_statvar->min();
	my $iter_max = $iter_statvar->max();
	my $iter_stddev = $iter_statvar->standard_deviation();

	printf "Mean number of test iterations per node: %0.4f\n",$iter_mean;
	printf "Max number of test iterations per node: %0.4f\n",$iter_max;
	printf "Min number of test iterations per node: %0.4f\n",$iter_min;
	printf "Std. deviation for number of test iterations per node: %0.4f\n\n",
    	$iter_stddev;

    for $node (sort {$a cmp $b} keys %nodehash) {
    	# if --match used, make sure we honor it
    	(defined $match and $node !~ /$match/) and next;
		my $val = $nodehashref->{$node}->{'iterations'};

		# now compute how the node's data for this data point
		# compares to the the statistical characteristics for this
		# test
		my $delta = abs($val - $iter_mean);
		($delta > 0) or next;
		if ($delta >= (1*$iter_stddev)) {
			my $delta_percent = ($iter_stddev == 0) ?
				$delta : $delta / $iter_stddev;
			$delta_percent *= 100;

			print "$node iterations: ";
			printf("actual=%0.4f good=%0.4f delta=%0.4f (%0.1f%%) stddev=%0.4f\n",
				$val,$iter_mean,$delta,$delta_percent,$iter_stddev);
		}
    }
}

#if (defined $DEBUG) {
#	$num = keys(%nodehash);
#	print "DEBUG: $num keys in \%nodehash\n";
#}


# dplot the data if asked
if (defined $dplot) {
	open (PLOT, ">dplot-in.dat");
	for $node (sort {$a cmp $b} keys %nodehash) {
		for $k (sort {$a cmp $b} keys %{$nodehashref->{$node}}) {
                    ($k =~ /maxrunid|iterations/) and next;
                    ($dplotparams[0] !~ /$k/) and next;
			for $dat (@{$nodehashref->{$node}->{$k}}) {

                            # prevent plot of bogus "0" value by dplot
                            if ($dat eq 0.0 and $k !~ /$passfail/) {
                                debug_print(2,"DEBUG: prevented dplot of datapoint "
                                        . $dat . " for $node in $k\n");
                            }
                            else {
                                print PLOT "$dat\t$k\-$node\n";
                            }
			}
		}
	}
	close(PLOT);

	# if the --dplot params on the command line had arguments for dplot,
	# use them, otherwise default to a set
	my $cmd = '';
	if ($#dplotparams > 0) {
		$cmd = "$bench_test/bin/dplot a dplot-in.dat ";
		for my $i (1..$#dplotparams) {
			$cmd .= "$dplotparams[$i] ";
		}
	}
	else {
		$cmd = "$bench_test/bin/dplot a dplot-in.dat -n -std";
	}

	(defined $DEBUG) and print "DEBUG:results_to_dplot() cmd=$cmd\n";
	exec "$cmd";
}

if (defined %stringvars) {
    print "\n";
    my $num_nodes = 0;
    my $node_col_width = 25;
    my $value_col_width = 10;

    print sprintf("%-${node_col_width}s\t\t\t%-${value_col_width}s\n", "Node(s)", "Value");
    print "-------------------------------------------------------------------\n";

    for my $value (sort {$a cmp $b} keys %stringvars) {
        my @node_vals = split(',', $stringvars{$value});
        $num_nodes = @node_vals;

        if ($num_nodes > 1) {
            print sprintf("%-${node_col_width}s\t\t\t%-${value_col_width}s\n", "$num_nodes nodes", $value);
        }
        else {
            print sprintf("%-${node_col_width}s\t\t\t%-${value_col_width}s\n", $stringvars{$value}, $value);
        }
    }
    print "\n";
}


# Responsible for parsing and generating statistics for all output
# files in a single test identifier
sub parse_ident {
	my $ident = shift;

	my @nodelist = ();	

	# path to the test identifier
	my $output_path ="$testset_path/$ident";
	
	# grab a list of all node_hw_test output files in this test
	# identifier
	#@allrunfiles = `cd $output_path; ls -1 \*\.node_hw_test\.run???? 2>&1`;
	@allrunfiles = `cd $output_path; ls -1 2>&1`;
	
	# we need to parse the list of output files and figure out all
	# the node names we find. while we are doing that we can figure
	# out what the highest run id number is for each node
	for (@allrunfiles) {
		chomp $_;
		(/no such/i) and next;
		next unless (/\.node_hw_test\.run/);
		my ($node,$runid) = $_ =~ /^(\S+)\.node_hw_test\.run(\d+)$/;
		
        if (! exists $nodehashref->{$node}) {
            my %newhash;
            $nodehashref->{$node} = \%newhash;
			$nodehashref->{$node}->{"maxrunid:$ident"} = 0;
			$nodehashref->{$node}->{'iterations'} = 0;
			push @nodelist, $node;
            (defined $DEBUG and $DEBUG > 1) and print
				"DEBUG:parse_ident($ident) adding node $node to nodehash\n";			
        }
		elsif (! exists $nodehashref->{$node}->{"maxrunid:$ident"}) {
			push @nodelist, $node;
			$nodehashref->{$node}->{"maxrunid:$ident"} = 0;
		}
		
		if ($runid > $nodehashref->{$node}->{"maxrunid:$ident"}) {
			$nodehashref->{$node}->{"maxrunid:$ident"} = $runid;
		}
		
		(defined $DEBUG and $DEBUG > 1) and print
			"DEBUG:parse_ident($ident) $_,$node,$runid,".$nodehashref->{$node}->{"maxrunid:$ident"}."\n";
	}
	
	# our default behavior is to parse the latest test run from each
	# node, i.e. the file for each node with the highest run id number.
	# Various command-line parameters will change this behavior.
#	for $node (sort {$a cmp $b} keys %nodehash) {
	foreach $node (@nodelist) {
		
		my $output_file;
		for (my $i = 0; $i < $lastnruns; $i++) {
			# build a string with path and filename for the node's output
			# file we want to parse
			if (defined $onlyrun) {
				$output_file = sprintf "%s/%s\.node_hw_test\.run%04d",
					$output_path,$node,$onlyrun;
			}
			else {
				my $rid = $nodehashref->{$node}->{"maxrunid:$ident"} - $i;
				($rid <= 0) and next;
				
				$output_file = sprintf "%s/%s\.node_hw_test\.run%04d",
					$output_path,$node,$rid;
					
				# make sure the file looks like it exists
				(! -f $output_file) and next;
			}

			# if --match was used, only parse output files that match
			# the regex
			(defined $match and $output_file !~ /$match/) and next;

			# update summary data
			$summary{'nodelist'}{$node} = 1;

			defined $DEBUG and print
				"Parsing $output_file...\n";

			parse_output_file($output_file,$node);
		}

		# give some visual output we are doing work every so often
		if (!defined $quiet and !defined $debug and
			(($summary{'files'} % 32) == 0) and
			 $summary{'files'} != 0) {
			print ".";
		}
	}
}

# This routine is responsible for parsing a single node_hw_test output
# file.
sub parse_output_file {
	my $file = shift;
	my $node = shift;
	
	open (FILE,"<$file") or (print "Could not open $file ($!)" and
		return 1);
	my @txtbuf = <FILE>;
	close(FILE);
	my $numlines = @txtbuf;
	(defined $DEBUG and $DEBUG > 1) and print
		"DEBUG: parse_output_file() numlines=$numlines\n";

	# update summary data
	$summary{'files'}++;
	
	my $iter = 0;
	my $tmod = '';
	my $lastmod ='';
	my $inheader = 1;
	my $linegrab = 0;
	my @buf = ();
	my $i = 0;
	my $elapsed1 = 0;
	my $elapsed2 = 0;
	my $timestamp = 0;

	while ($i < $numlines) {
		# look for Cbench markers in the output since they are
		# the keys to delimit the different sections of output
		if ($txtbuf[$i] =~ /$cbench_mark_prefix/) {
			($inheader) and $inheader = 0;

			(defined $DEBUG and $DEBUG > 1) and do {
				($mark) = $txtbuf[$i] =~
					/$cbench_mark_prefix\s+([\S*\s*]*)/;			
				print "DEBUG: parse_output_file() found cbench marker $mark, i=$i\n";
			};

			# If we are linegrab mode and we found a Cbench
			# marker, then this means we found the end of
			# a section of output. Thus, we need to parse
			# the temporary buffer of output (in @buf) that
			# we have been building
			if ($linegrab) {
				(defined $DEBUG and $DEBUG > 1) and print
					"DEBUG: parse_output_file() ending linegrab, i=$i\n";

				# the hw_test module responsible for
				# generating the output we have built in
				# @buf needs to parse the output. a
				# cbench marker at the beginning of this
				# output chunk told us what module was
				# responsible and was stored in $tmod
				parse_buf($tmod,\@buf,$node);

				# prime the loop for the next round of output
				$linegrab = 0;
			} 

			if ($txtbuf[$i] =~ /$cbench_mark_prefix\s+ITERATION\s+(\d+)/) {
				($iter) = $txtbuf[$i] =~
					/$cbench_mark_prefix\s+ITERATION\s+(\d+)/;			
				# update summary data
				$summary{'iterations'}++;
                # update node stats
                $nodehashref->{$node}->{'iterations'}++;
			}
			elsif ($txtbuf[$i] =~ /$cbench_mark_prefix\s+MODULE/) {
				$lastmod = $tmod;
				($tmod) = $txtbuf[$i] =~
					/$cbench_mark_prefix\s+MODULE\s+(\S+)/;	
			}
			elsif ($txtbuf[$i] =~ /$cbench_mark_prefix\s+TIMESTAMP elapsed=(\d+\.\d+)\s+min,/) {
				$elapsed2 = $1;
				my $delta = $elapsed2 - $elapsed1;
				$elapsed1 = $elapsed2;
				$timestamp++;

				# ignore the first timestamp in the file
				if ($timestamp == 1) {
					debug_print(2,"DEBUG: parse_output_file() first timestamp elapsed=$elapsed1 delta=$delta tmod=$tmod lastmod=$lastmod timestamp=$timestamp\n");
					$i++;
					next;
				}

				debug_print(2,"DEBUG: parse_output_file() elapsed=$elapsed1 delta=$delta tmod=$tmod lastmod=$lastmod timestamp=$timestamp\n");

				# record elapsed time data for this module
				($lastmod eq '') and $lastmod = $tmod;
				my $k = "$lastmod"."_elapsed";
				debug_print(3,"DEBUG: parse_output_file() $k => $delta\n");
				if (! exists $nodehashref->{$node}->{$k}) {
					my @newarray = ();
					$nodehashref->{$node}->{$k} = \@newarray;
				}
				push @{$nodehashref->{$node}->{$k}}, $delta;
				
				if (defined $characterize) {
					if (! exists $statvars{$k}) {
						$statvars{$k} = Statistics::Descriptive::Full->new();
					}
					$statvars{$k}->add_data($delta);
				}
			}

			$i++;
			next;
		}
		elsif ($inheader) {
			$i++;
			next;
		}
		else {
			if (! $linegrab) {
				# if we are here, we need to clean out
				# the temp buffers and start filling it with
				# the output lines that we'll pass to the
				# hw_test module parse() routine
				$#buf = 0;
				$linegrab = 1;

				(defined $DEBUG and $DEBUG > 1) and print
					"DEBUG: parse_output_file() starting linegrab, i=$i\n";
			}
			push @buf, $txtbuf[$i];
			$i++;
			
			# check for the special case that the end of the output file
			# was reached
			if ($i == $numlines) {
				(defined $DEBUG and $DEBUG > 1) and print
					"DEBUG: parse_output_file() ending linegrab ".
					"due to EOF, i=$i\n";
				parse_buf($tmod,\@buf,$node);
			}
			next;
		}
	
	}
	$#txtbuf = 0;
}

sub parse_buf {
	my $tmod = shift;
	my $bufref = shift;
	my $node = shift;

	(defined $DEBUG and $DEBUG > 1) and print
		"DEBUG:parse_buf() module=$tmod\n";

	# need to make sure we have a valid object reference
	# for a given module before trying to use it
	if (! defined $test_modules{$tmod}) {
		# nope, no object reference for the module output
		# we need to parse
		print "parse_buf() No valid hw_test object to parse $tmod output.\n";
		return;
	}
	
	my $tobj = $test_modules{$tmod};
	
	# only do parsing if we are parsing data for the test class
	# the data is from
	($tobj->test_class !~ /$class/) and return;

	# parse will return a hash reference
	my $data = $tobj->parse($bufref);

        # turn off characterization for dmidecode data
        ($tmod =~ /dmidecode/) and undef $characterize;

	#
	# Ok, now that we have true data, we need to store it away in
	# the appropriate places. First, store it away in the node hash
	# so that all data gathered will be organized by node. Second,
	# if we are running in a 'characterize' mode where new statistical
	# data will be generated based on the data currently being gathered,
	# then we need to add data points to the appropriated statistical
	# variable objects from Statistics::Descriptive
	
	for $k (keys %{$data}) {
		# adding to nodehash
		if (! exists $nodehashref->{$node}->{$k}) {
                    # handle non-numeric results a little differently (but don't classify decimal
                    # values ad non-numeric :)
                    if ($data->{$k} =~ /\D/ and $data->{$k} !~ /\d+\.\d+/){
                        $stringvars{$data->{$k}} .= "$node,";
                    }
                    else {
                        my @newarray = ();
                        $nodehashref->{$node}->{$k} = \@newarray;
                    }
		}
		push @{$nodehashref->{$node}->{$k}}, $data->{$k};
		
		if (defined $characterize) {
			if (! exists $statvars{$k}) {
				$statvars{$k} = Statistics::Descriptive::Full->new();
			}

                        # check for bogus data values of 0.0000 (ignore such values when they
                        # make sense for certain tests)
                        if ($data->{$k} eq 0.0000 and $k !~ /$passfail/) {
                            debug_print(2,"DEBUG: prevented storage of datapoint " 
                            . $data->{$k} . " for $node in $k\n");
                        }
                        else {
                            $statvars{$k}->add_data($data->{$k});
                        }
		}
		(defined $DEBUG and $DEBUG > 2) and print
			"DEBUG:parse_buf() $k => $data->{$k}\n";
	}
}

# Read target values from a file into the target hash
sub load_target_values {
	# check to see if a specific filename was passed on the command
	# line to save values to
	my $tfile;
	if ($loadtarget ne '') {
		if ($loadtarget =~ /\//) {
			$tfile = $loadtarget;
		}
		else {
			$tfile = "$testset_path/$ident/$loadtarget";	
		}
	}
	else {
		$tfile = "$testset_path/$ident/target_hw_values";	
	}
	
	open (FILE,"<$tfile") or (print BOLD RED
		"Could not open $tfile for read ($!)\n\n" and return 1);
	
	# read in each line
	while (<FILE>) {
		# skip comments
		$_ =~ (/^\s*#/) and next;
		my ($key, $mean, $max, $min, $stddev) = $_ =~
			/^(\S+), (\S+), (\S+), (\S+), (\S+),.*$/;
		$target{$key}{'mean'} = $mean;
		$target{$key}{'max'} = $max;
		$target{$key}{'min'} = $min;
		$target{$key}{'stddev'} = $stddev;
		
		(defined $DEBUG and $DEBUG > 1) and print
			"DEBUG:load_target_values() $key, $mean, $max, $min, $stddev\n";
	}
	close(FILE);

	print BOLD CYAN "Loaded characterized target values from $tfile.\n\n" unless defined $quiet;
	
	return 0;
}

# write out in a nice formatted way the target values that are contained
# in the %target hash which should have been populated by characterizing
# a set of data
sub save_target_values {
	# check to see if a specific filename was passed on the command
	# line to save values to
	my $tfile;
	if ($savetarget ne '') {
		$tfile = "$testset_path/$ident/$savetarget";	
	}
	else {
		$tfile = "$testset_path/$ident/target_hw_values";	
	}
	
	open (FILE,">$tfile") or die
		"Could not open $tfile for write ($!)\n";
	
	my $totalnodes = keys %{$summary{'nodelist'}};
	print FILE
			"# This is a Cbench nodehwtest target value file generated\n" .
			"# by nodehwtest_output_parse.pl\n".
			"#\n" .
			"# The target value data was generated from parsing $summary{'iterations'}\n".
			"# iterations from $totalnodes nodes\n".
			"#\n".
			"# The format is:\n".
			"# TESTNAME, MEAN, MAX, MIN, STDDEVIATION, SAMPLECOUNT\n";

	for $k (sort {$a cmp $b} keys %target) {
		print FILE "$k, ";
		for $val (('mean','max','min','stddev','count')) {
			printf FILE "%0.4f, ",$target{$k}{$val};
		}
		print FILE "\n";
	}
	close(FILE);

	print BOLD CYAN "Saved characterized target values to $tfile.\n\n" unless defined $quiet;
}


sub usage {
	print "USAGE: $0 \n" .
		"Cbench utility to parse node-level hardware test data from node_hw_test\n" .
		"   --class <regex>   Run only tests whose test class matches the\n".
		"                      provided regex string. For example:\n".
		"                       --class 'cpu|disk|memory'\n".
		"                      explicitly specifies the default behavior\n".
		"                      of node_hw_test\n".
		"   --characterize    Parse run output data and then statistically\n".
		"                      characterize it. The target values calculated\n".
		"                      by the characterization process can be saved to\n".
		"                      a target values file using --savetarget\n".
		"   --savetarget name Save characterized performance data to a target\n".
		"                      values file. The name is optional.\n".
		"   --loadtarget name Load characterized performance data from a specific\n".
		"                      target values file.\n".
        "   --iterationanalyze Do additional analysis on the number of test iterations\n".
        "                       run per node\n".
		"   --lastnruns <num> Parse the last N number of runs from each node\n".
		"   --onlyrun <num>   Parse only runs labeled with number N\n".
		"   --ident name      Test identifier to parse (optional).\n" .
		"                     Can also have the form of a list:\n".
		"                       --ident test1,test2,test3\n".
		"   --noerrors        Do not print any information about tests that exceed\n".
		"                     std. deviation tolerances\n".
		"   --match regex     Only parse test output files that match the supplied\n" .
		"                      regular expression. Fo example:\n".
		"                         --match \'n11|n20\'\n" .
		"                      would only parse output for nodes n11 and n20\n" .
		"   --dplot metric,dplotarams  Use the STAB dplot utility to plot the\n".
		"                    the statistical distribution of data for the test metric\n".
		"                    specificied. Dplotting can only be used for a single\n".
		"                    metric.  For example:\n".
		"                        --dplot hpcc_hpl_gflops\n".
		"                    would request a dplot for all data from the hpcc_hpl_gflops\n".
		"                    test. You can optionally pass arguments to dplot as well.\n".
		"                    For example:\n".
		"                        --dplot hpcc_hpl_gflops,-bi,-std\n".
		"                    would pass the -bi and -std command line parameters to\n".
		"                    dplot\n".
		"   --warn            Turn on additional warnings\n".
		"   --quiet           Only output probable errors\n".
		"   --usecwd          Override the path to the nodehwtest that is determined\n".
		"                     and use the currend working directory\n".
		"   --debug <level>   Turn on debugging at the specified level\n";
}
