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

# need to know where everything cbench lives!
use lib ($ENV{CBENCHOME} ? $ENV{CBENCHOME} : "$ENV{HOME}\/cbench");
$BENCH_HOME = $ENV{CBENCHOME} ? $ENV{CBENCHOME} :
	"$ENV{HOME}\/cbench";
require "cbench.pl";

# add Cbench perl library to the Perl search path
use lib ($ENV{CBENCHOME} ? "$ENV{CBENCHOME}\/perllib" :
	"$ENV{HOME}\/cbench\/perllib");

# enable/disable color support appropriately
detect_color_support();

use File::Find;
use Getopt::Long;
use Statistics::Descriptive;
use Data::Dumper;
use Term::ANSIColor qw(color :constants);
$Term::ANSIColor::AUTORESET = 1;

GetOptions( 'ident=s' => \$ident,
			'debug:i' => \$DEBUG,
			'logx' => \$logx,
			'logy' => \$logy,
			'gnuplot' => \$gnuplot,
			'help' => \$help,
			'meta' => \$meta,
			'diagnose' => \$diagnose,
			'successstats' => \$successstats,
			'nodediagnose' => \$nodediag,
			'nodata' => \$nodata,
			'customparse' => sub {$customparse = 1; $diagnose = 1},
			'errorsonly' => sub { $diagnose = 1; $customparse = 1; $nodata = 1 },
			'metric=s' => \$metricstr,
			'match=s' => \$match,
			'exclude=s' => \$exclude,
			'minprocs=i' => \$minprocs,
			'maxprocs=i' => \$maxprocs,
);

# cbench test set name
my $testset = 'longstress';

if (defined $help) {
    usage();
    exit;
}

my $num_data_columns = 2;

# hash to hold all the raw data that is returned by the
# parsing modules
my %data = ();

# hash to hold summary data of the statuses returned from
# parsing each job output
my %statusdata = ();

# some statistics vars
my $total_files_parsed = 0;
my $total_jobs_parsed = 0;


# load all theh hw_test modules, we'll need them for parsing
# the output files
my %parse_modules;
load_parse_modules(\%parse_modules);

# ask each parse module what files it will want parsed. each
# module should return a reference to an ordered array of filenames. there
# are certain keyword filenames we recognize like STDOUT and
# STDERR.
my %parse_modules_files;
foreach $k (keys %parse_modules) {
	$parse_modules_files{$k} = $parse_modules{$k}->file_list();
}
if (defined $DEBUG and $DEBUG > 2) {
	print "====================================================================\n";
	print "DEBUG: Dumping \%parse_modules_files hash:\n";
	print Dumper (%parse_modules_files);
}

# Each parse module has the option of having an alias_spec member
# function which returns a regex specification of benchmark names
# that the module will also handle. By default, only the benchmark
# that matches the parse module name will be parsed, i.e. the xhpl
# module only parses output from the xhpl benchmark, e.g. a jobname
# like xhpl-2ppn-32 would be parsed. This is has issues for test
# suites like the NAS Parallel Benchmarks which generate many different
# benchmark names, i.e. spA, spB, cgC, etc. The %bench_aliases hash
# stores any alias specs found in any output parsing modules
my %bench_aliases;
foreach $k (keys %parse_modules) {
	eval {
		$parse_modules{$k}->alias_spec();
	};
	if ($@ =~ /Can't locate object method/) {
		(defined $DEBUG and $DEBUG > 1) and print "DEBUG: ".
			"No alias_spec method in $k module\n";
	}
	else {
		(defined $DEBUG and $DEBUG > 1) and print "DEBUG: ".
			"Found alias_spec method in $k module\n";
		$bench_aliases{$k} = $parse_modules{$k}->alias_spec();
	}
}


# This a mapping hash that will be built as we parse output files.
# It maps  a given metric to the units it is using which is 
# critical for graphing... we need to know what to put on the Y axis
# label!!!...and we have to figure it out dynamically
my %metrics_to_units;

# This hash will be used to group metrics that use identical units
# together. Metrics that use identical units (i.e. MB/s) can be
# graphed on the same graph! Metrics with differing units (i.e.
# MB/s versus seconds) have to be on separate graphs or at the very
# least have two Y axes on the graph
my %unit_groupings;

# This hash is used to hold job failure data as it relates to the
# number of processes in a job
my %jobdiag_data;

# This hash is used to hold job success rate data organized by the
# number of processes in the job
my %success_data;

# This hash is used to hold data about nodes that are involved in
# failed jobs
my %nodediag_data;


# HERE IS WHERE THE REAL PARSING WORK GETS KICKED OFF...
#
# Recursively process all files from the current directory and
# below. If the --ident parameter is given, only process the
# directory tree indicated.
my $metaset;
if (defined $meta) {
	my $pwd = `pwd`;
	chomp $pwd;

	opendir(DH, ".");

	while( defined ($file = readdir(DH)) ) {
		($file =~ /nodehwtest/) and next; # the nodehwtest test set is special
		(! -d $file) and next;
		next if ($file eq "." || $file eq "..");
		chdir $file;
		$metaset = $file;

		(defined $DEBUG) and print	
			"DEBUG:meta: parsing ". uc($file). " test set\n";

		$basepath = ".";
		(defined $ident) and $basepath = ".\/$ident";
		find(\&parse_output_file, $basepath);

		chdir $pwd;
	}
	closedir(DH);
}
else {
	$basepath = ".";
	if (defined $ident and $ident =~ /\,/) {
		# looks like a list of idents was specified
		my @identlist = split(',',$ident);
		(defined $DEBUG) and print	
			"DEBUG: found list of idents: ". join(' ',@identlist). " \n";
		foreach (@identlist) {
			$basepath = ".\/$_";
			find(\&parse_output_file, $basepath);
		}
	}
	elsif (defined $ident) {
		$basepath = ".\/$ident";
		find(\&parse_output_file, $basepath);
	}
	else {
		find(\&parse_output_file, $basepath);
	}
}

if (defined $DEBUG and $DEBUG > 2) {
	print "====================================================================\n";
	print "DEBUG: Dumping \%data hash:\n";
	print Dumper (%data);
	print "====================================================================\n";
	print "DEBUG: Dumping \%metrics_to_units hash:\n";
	print Dumper (%metrics_to_units);
	print "====================================================================\n";
	print "DEBUG: Dumping \%unit_groupings hash:\n";
	print Dumper (%unit_groupings);
	print "====================================================================\n";
	print "DEBUG: Dumping \%jobdiag_data hash:\n";
	print Dumper (%jobdiag_data);
	print "====================================================================\n";
	print "DEBUG: Dumping \%success_data hash:\n";
	print Dumper (%success_data);
	print "====================================================================\n";
	print "DEBUG: Dumping \%nodediag_data hash:\n";
	print Dumper (%nodediag_data);
}

# We need to run through the raw data hash once to get a list of all the
# possible metrics we'll need to deal with.  This is dynamic with each run
# because the output parsing modules can choose to send new/different data,
# parse different runs, etc.
%metrics = ();
for $testid (keys %data) {
    for $ppn (keys %{$data{$testid}}) {
		for $bench (keys %{$data{$testid}{$ppn}}) {
			for $np (keys %{$data{$testid}{$ppn}{$bench}}) {
				for $k (keys %{$data{$testid}{$ppn}{$bench}{$np}}) {
					if ($k =~ /^DATA/) {
						$metrics{$k}++;
					}
				}
			}
		}
	}
}
(defined $DEBUG and $DEBUG > 2) and do {
	print "====================================================================\n";
	print "DEBUG: Dumping \%metrics hash:\n";
	print Dumper (%metrics);
};

# We are going to build a 2D hash. The first dimension is the number of
# processors. The second dimension is an ordered list of column data
# where each column corresponds to a jobname, eg. cgC-2ppn
my %outhash = ();
my $column1 = 1;
my $column2 = 0;
my $column3 = 0;
$outhash{'0'}{'0'} = "NP";
$outhash{'UNITS'}{'0'} = "UNITS";
$outhash{'META'}{'0'} = "META";

my$numtestids = keys %data;
for $testid (keys %data) {
    for $ppn (keys %{$data{$testid}}) {
		for $bench (keys %{$data{$testid}{$ppn}}) {
			for $rawmetric (keys %metrics) {
				$metric = $rawmetric;
				$metric =~ s/DATA_//;
 
				# There are a small set of keywords that can be used in metric
				# names (as a prefix) that will signal us to behave differently:
				#   min_   just compute the minimum of the list of data
				#   max_   just compute the max of the list of data
				#   ave_   just compute the average of the list of data
				# So we need to watctbird8/hpcc-1ppn-9/hpcc-1ppn-9.pbs.o12671h for them and react accordingly
				my $special_metric = 0;
				if ($metric =~ /^min_|^max_|^ave_/) {
					$special_metric = 1;
            		# key zero, which would be 0 processors, in the first dimension
            		# of the hash is the 'legend' line that records which column
            		# corresponds to which job series
            		$outhash{'0'}{"$column1"} .= "$testid-$bench-$ppn-$metric";
					# correlate the metric to its units in the 2D hash
					$outhash{'UNITS'}{"$column1"} = $metrics_to_units{$metric};
				}
				else {
					$special_metric = 0;
            		# key zero, which would be 0 processors, in the first dimension
            		# of the hash is the 'legend' line that records which column
            		# corresponds to which job series
            		$outhash{'0'}{"$column1"} .= "$testid-$bench-$ppn-$metric-ave";
					$column2 = $column1 + 1;
					$outhash{'0'}{"$column2"} .= "$testid-$bench-$ppn-$metric-min";
					$column3 = $column1 + 2;
					$outhash{'0'}{"$column3"} .= "$testid-$bench-$ppn-$metric-max";

					# correlate the metric to its units in the 2D hash
					$outhash{'UNITS'}{"$column1"} = $metrics_to_units{$metric};
					$outhash{'UNITS'}{"$column2"} = $metrics_to_units{$metric};
					$outhash{'UNITS'}{"$column3"} = $metrics_to_units{$metric};
				}

				my $found_some_data = 0;
            	for $np (sort {$a <=> $b} (keys %{$data{$testid}{$ppn}{$bench}}) ) {
                	if (exists $data{$testid}{$ppn}{$bench}{$np}{'PASSED'} and
						$data{$testid}{$ppn}{$bench}{$np}{'PASSED'} >= 1) {
                    	# if at least one test passed, we have data to report
						if (exists $data{$testid}{$ppn}{$bench}{$np}{$rawmetric}) {
							$found_some_data = 1;
							my $statvar = Statistics::Descriptive::Full->new();
							$statvar->add_data(@{$data{$testid}{$ppn}{$bench}{$np}{$rawmetric}});

                    		my $num = $statvar->mean();
                    		$outhash{$np}{"$column1"} = sprintf("%25.4f",$num);

							# if there are multiple data values, we need to compute min and max
							# as well as mean
							if ($statvar->count() > 1 and !$special_metric) {
                    			my $num = $statvar->min();
                    			$outhash{$np}{"$column2"} = sprintf("%25.4f",$num);
                    			$num = $statvar->max();
                    			$outhash{$np}{"$column3"} = sprintf("%25.4f",$num);								
							}
							elsif (!$special_metric) {
								# if there are not multiple data values, set min and max
								# to the average value
                    			$outhash{$np}{"$column2"} = sprintf("%25.4f",$num);
                    			$outhash{$np}{"$column3"} = sprintf("%25.4f",$num);															
							}
							elsif ($special_metric) {
								my $num;
								($metric =~ /^min_/) and $num = $statvar->min();
								($metric =~ /^max_/) and $num = $statvar->max();
								($metric =~ /^ave_/) and $num = $statvar->mean();

                    			$outhash{$np}{"$column1"} = sprintf("%25.4f",$num);
							}
						}
						else {
							$outhash{$np}{"$column1"} = "NODATA";
						}
                	}
                	else {
                    	$outhash{$np}{"$column1"} = "NODATA";
                	}
            	}
				
				if ($special_metric) {
					if (!$found_some_data) {
						$outhash{'META'}{"$column1"} = "no datapoints";
					}
					$column1 += 1;
				}
				else {
					if (!$found_some_data) {
						$outhash{'META'}{"$column1"} = "no datapoints";
						$outhash{'META'}{"$column2"} = "no datapoints";
						$outhash{'META'}{"$column3"} = "no datapoints";
					}
					$column1 += 3;
				}
        	}
		}
    }
}
cleanup_output_hash(\%outhash);
(defined $DEBUG and $DEBUG > 2) and do {
	print "====================================================================\n";
	print "DEBUG: Dumping \%outhash hash:\n";
	print Dumper (%outhash);
};

# print results to stdout
(!defined $nodata) and results_to_stdout(\%outhash);

(defined $successstats) and dump_success_stats(\%success_data);

(defined $diagnose) and dump_jobdiag_stats(\%jobdiag_data);

(defined $nodediag) and dump_nodediag_stats(\%nodediag_data);

print GREEN "\nParse Summary:\n--------------\n";
print "Total Files Parsed = $total_files_parsed\n";
print "Total Jobs Parsed = $total_jobs_parsed\n";
print GREEN "\nJob Status Summary:\n-------------------\n";
foreach $k (keys %statusdata) {
	print "$k = $statusdata{$k}\n";
}
my $temp = 0;
my $temp2 = $total_jobs_parsed - $statusdata{'NOTICE'};
$temp = $statusdata{'PASSED'}/$temp2 unless ($total_jobs_parsed == 0);
printf "Overall Job Success = %0.2f%%\n",$temp*100;

# build a gnuplot if asked, but we can only do one gnuplot per invocation right now...
(defined $gnuplot) and results_to_gnuplot(\%outhash) unless (defined $successstats);


# this is the guts of the output file parsing
sub parse_output_file {
	(defined $DEBUG and $DEBUG > 3) and print "DEBUG:parse_output_file: $File::Find::name\n";

    if ($File::Find::name =~ /(\S+)\-(\d)ppn.*\.o(\d+)/) {
		# Found an output file for stdout for a job.

        # Extract information we want from the name of the file we
        # are going to parse. We can do this because the file name
        # includes path and the directories in the path have 
        # embedded information for us.
        my @patharray = split '/',$File::Find::name;
        my $stdout_file = $patharray[$#patharray];
		my ($bench, $extra, $jobid) = $stdout_file =~ /(\S+)\-\dppn\-\d+[\.]*([pbs]*)\.o(\d+)/;
        my ($jobname) = $stdout_file =~ /(\S+\-\dppn\-\d+)\../;

		(defined $DEBUG and $DEBUG == 1) and print "DEBUG: parsing $stdout_file\n";

		# fileid just helps us with debug and status output
		my $fileid = '';

		# if the Cbench jobs are contained inside directories, like linpack,
		# the test ident is in a slightly different place in the path string
		my $testident;
		#print "DEBUG: ". scalar @patharray ." path components\n";
		if (scalar @patharray == 4) {
        	$testident = $patharray[$#patharray-2];
			(defined $meta) and $fileid = "$metaset\/";
			$fileid .= "$testident\/$patharray[$#patharray-1]\/$patharray[$#patharray]";
		}
		else {
        	$testident = $patharray[$#patharray-1];
			(defined $meta) and $fileid = "$metaset\/";
			$fileid .= "$testident\/$patharray[$#patharray]";
		}

		(defined $DEBUG and $DEBUG > 1) and print
			"DEBUG:parse_output_file() bench=$bench extra=$extra jobid=$jobid ident=$testident stdoutfile=$stdout_file\n";

		# NOTE: Some batch systems may truncate filenames which can
		#		cause erroneous information to be parsed from the 
		#		output filename. Newer Cbench job templates try to embed
		#		the job information inside the output file as well so
		#		we check for the existence of this information. If we
		#		find it, we trust it over the filename.
		undef $/;
		my $embedded_info_buf = `head -100 $stdout_file | /bin/grep -P \"Cbench \\S+:\" `;
		$/ = "\n";
		if ($embedded_info_buf =~ /Cbench \S+\:/) {
			# found embedded Cbench job info
			my ($tmpjob) = $embedded_info_buf =~ /\nCbench jobname: (\S+)\n/;
			if ($tmpjob =~ /ppn/) {
				# looks like we grabbed a jobname
				(defined $DEBUG and $DEBUG > 1) and print
					"DEBUG: using embedded jobname $tmpjob for $stdout_file\n";
				$jobname = $tmpjob;
			}
		}
        
        # if --match param was used, only process files matching the regex
        if (defined $match) {
            $matchstr = "$match";
            next unless ($File::Find::name =~ /$matchstr/);
        }
        # if --exclude param was used, only process files NOT matching
        if (defined $exclude) {
            $matchstr = "$exclude";
            next unless ($File::Find::name !~ /$matchstr/);
        }

        # parse the jobname to get important characteristics of the job
        ($bench, $ppn, $np) = ($jobname =~ /^(\S+)\-(\d)ppn[\-|\.](\d+)$/);
        $ppnstr = $ppn . "ppn";

		(defined $minprocs and $np < $minprocs) and next;
		(defined $maxprocs and $np > $maxprocs) and next;

		# the default parse module to use for parsing this benchmark is the
		# module that matches the benchmark name
		my $parsemod = $bench;

		# now see if we have an output parser module available to parse this
		# particular benchmark/test
		if (! defined $parse_modules{$parsemod}) {
			# doesn't look like this is a benchmark we know how to parse, but
			# we need to check if any output parsing modules alias specs match
			foreach my $k (keys %bench_aliases) {
				if ($bench =~ /$bench_aliases{$k}/) {
					# we have an alias hit!
					$parsemod = $k;
					(defined $DEBUG and $DEBUG > 1) and print "DEBUG:".
						"$bench matched parse module $k via the alias_spec $bench_aliases{$k}\n";
				}
			}
			
			if (! defined $parse_modules{$parsemod}) {
				# nope, no parse module available for the output we need to parse
				print "parse_output_file() No valid parse object to parse $bench output.\n";
				return;
			}
		}

		# yep, we have a module to parse with...onward
		$total_jobs_parsed++;

		# catalog the information about the units that correspond to the metrics
		# returned by the output parser module. this is critical information later
		# on if we want to graph things
		my $tmphash = $parse_modules{$parsemod}->metric_units();
		foreach $m (keys %{$tmphash} ) {
			if (! exists $metrics_to_units{$m}) {
				$metrics_to_units{$m} = $tmphash->{$m};
			}
			$unit_groupings{$tmphash->{$m}}{$bench} = 1;
		}
		
		# now read in all files that the parse module
		# says it wants to look at. we save each file in a local buffer (array) and
		# then stick a reference to the buffur array into an array of buffer references
		# that is ordered according to the file_list array retrieved from the parse
		# module (stored in %parse_modules_files). also keep track of which files we
		# have read in and the buffer ref in a hash so that we NEVER have to read
		# something twice (processing further down may need to look at files as well).
		my @output_bufrefs = ();
		my %files_sucked_in = ();
		foreach $f (@{$parse_modules_files{$parsemod}}) {
			my $file;
			# look for keywords
			if ($f eq 'STDOUT') {
				$file = $stdout_file;
			}
			elsif ($f eq 'STDERR') {
				$file = $stdout_file;
				$file =~ s/\.o$jobid/\.e$jobid/;
			}
            elsif ($f =~ /JOBID/) {
            	($file = $f) =~ s/JOBID/$jobid/;
            }
			else {
				$file = $f;
			}

        	# open and slurp the output file
			my @txtbuf;
			open_and_slurp($file,\@txtbuf) or do {
            	print "parse_output_file() Could not open $file for read ($!)\n";
				next;
			};

			# save references to this buffer
			push @output_bufrefs, \@txtbuf;
			$files_sucked_in{$f} = \@txtbuf;

			$total_files_parsed++;
        
        	(defined $DEBUG and $DEBUG > 1) and print
            	"DEBUG:parse_output_file() Reading file $file,job $jobname,ident $testident " .
            	"(np=$np ppn=$ppn benchmark=$bench)\n";
		}

		(defined $DEBUG and $DEBUG > 2) and print
			"DEBUG:parse_output_file() Starting core buffer parsing...\n";

		# we have all the buffers we need, so call the parse() method of the appropriate
		# parse module and pass the array of output buffer references
		my $filedata = $parse_modules{$parsemod}->parse("$fileid",@output_bufrefs);
		#print Dumper (%{$filedata});

		# try to help with memory reclaimation
		@output_bufrefs = undef;

		my @keylist = keys %{$filedata};
		foreach my $k (@keylist) {
			# is this the STATUS key returned by the parse module?
			if ($k eq 'STATUS') {
				my $status = $filedata->{$k};
				(!exists $data{$testident}{$ppnstr}{$bench}{$np}{$status}) and
					$data{$testident}{$ppnstr}{$bench}{$np}{$status} = 0;

				$data{$testident}{$ppnstr}{$bench}{$np}{$status}++;
				
				# update the overall status summary data
				(!exists $statusdata{$status}) and $statusdata{$status} = 0;
				$statusdata{$status}++;

				# updated job failure diagnostic data
				($status ne 'PASSED') and $jobdiag_data{$np}{$filedata->{$k}}++;
				
				# update job success data
				($status eq 'PASSED') and $success_data{$np}{'PASSED'}++;
				$success_data{$np}{'TOTAL'}++;
				
				next;
			}

			# otherwise this is a key with a datapoint. if the datapoint
			# is 'NODATA', there is no good data...
			if ($filedata->{$k} eq 'NODATA') {
				my $key = "NODATA_$k";
				(!exists $data{$testident}{$ppnstr}{$bench}{$np}{$key}) and
					$data{$testident}{$ppnstr}{$bench}{$np}{$key} = 0;

				$data{$testident}{$ppnstr}{$bench}{$np}{$key}++;
			}
			else {
				my $key = "DATA_$k";
				push @{$data{$testident}{$ppnstr}{$bench}{$np}{$key}}, $filedata->{$k};
			}
		}

		(defined $DEBUG and $DEBUG > 2) and print
			"DEBUG:parse_output_file() Finished core buffer parsing...\n";

		# if the custom parse filters are enabled, then we need to look at both
		# the STDOUT, and STDERR files for matches to the custom parse filters
		if (defined $customparse) {
        	(defined $DEBUG and $DEBUG > 2) and print
            	"DEBUG:parse_output_file() Starting customparse work...\n";

			my @files_to_grok = ();
			my @files_to_grok_bufrefs = ();

			push @files_to_grok, 'STDOUT';
			push @files_to_grok, 'STDERR';

			foreach my $f (@files_to_grok) {
				my $file;
				# look for keywords
				if ($f eq 'STDOUT') {
					$file = $stdout_file;
				}
				elsif ($f eq 'STDERR') {
					$file = $stdout_file;
					$file =~ s/\.o$jobid/\.e$jobid/;
				}

				# check the files_sucked_in cache, we may already have the
				# file in a buffer
				if (!exists $files_sucked_in{$f}) {
					# open and slurp the output file
					my @txtbuf;
					open_and_slurp($file,\@txtbuf) or do {
						print "parse_output_file() Could not open $file for read ($!)\n";
						next;
					};

					# save references to this buffer
					push @files_to_grok_bufrefs, \@txtbuf;
					$files_sucked_in{$f} = \@txtbuf;

					$total_files_parsed++;

        			(defined $DEBUG and $DEBUG > 1) and print
            			"DEBUG:parse_output_file(customparse) Reading file $file,job $jobname,ident $testident " .
            			"(np=$np ppn=$ppn benchmark=$bench)\n";
				}
				else {
					# already have the file, just grab the buffer reference
					push @files_to_grok_bufrefs, $files_sucked_in{$f};
				}
			}

			# we will need a data structure to keep track of hits to
			# the custom parse filters, so well build a hash with
			# the same keys as the %parse_filters array (from
			# cluster.def)
			my %filterhits = ();
			foreach my $k (keys %parse_filters) {
				$filterhits{$k} = 0;
			}				
			
			foreach my $bufref (@files_to_grok_bufrefs) {
				foreach my $l (@{$bufref}) {
					# skip the "whitespace" output generated by the 
					# 'stress' benchmark since it can generate a TON of
					# useless output
					($l =~ /\.\.\.\.\.\.\.\.\+$/) and next;
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
							print RESET "(";
							print GREEN, "$fileid";
							print RESET ")";
							print BOLD WHITE, "=> ";
                            print BOLD CYAN, "$temp";
							print RESET "\n";
							$filterhits{$filter}++;
						}
					}
				}
			}			

			# try to help with memory reclaimation
			@files_to_grok_bufrefs = undef;
		}
		
		# if job failure node diagnosis is enabled, we need to do more work
		if (defined $nodediag and ($filedata->{'STATUS'} ne 'PASSED')) {
        	(defined $DEBUG and $DEBUG > 2) and print
            	"DEBUG:parse_output_file() Starting nodediag work...\n";

			my @files_to_grok = ();
			my @files_to_grok_bufrefs = ();
			my $joblaunchmethod = 'NADA';
			# The first thing we need to figure out what joblaunch method,
			# and thus what kind of output to look for, was used for the job.
			# We do this by three checks:
			#   1) Cbench embedded job info
			#   2) look at both STDOUT and STDERR and guess (worst, slow, inefficient)
			if ($embedded_info_buf =~ /\nCbench joblaunchmethod: (\S+)\n/) {
				(defined $DEBUG and $DEBUG > 1) and print
					"DEBUG: nodediagnose using embedded joblaunchmethod $1\n";

				$joblaunchmethod = $1;

				# build function name to use for ranktonode support
				my $filelist_func_name = "$1_ranktonode_files";
				*filelist_func = \&$filelist_func_name;
				push @files_to_grok, filelist_func();
			}
			else {
				push @files_to_grok, 'STDOUT';
				push @files_to_grok, 'STDERR';
			}

			foreach my $f (@files_to_grok) {
				my $file;
				# look for keywords
				if ($f eq 'STDOUT') {
					$file = $stdout_file;
				}
				elsif ($f eq 'STDERR') {
					$file = $stdout_file;
					$file =~ s/\.o$jobid/\.e$jobid/;
				}

				# check the files_sucked_in cache, we may already have the
				# file in a buffer
				if (!exists $files_sucked_in{$f}) {
					# open and slurp the output file
					my @txtbuf;
					open_and_slurp($file,\@txtbuf) or do {
						print "parse_output_file() Could not open $file for read ($!)\n";
						next;
					};

					# save references to this buffer
					push @files_to_grok_bufrefs, \@txtbuf;
					$files_sucked_in{$f} = \@txtbuf;

					$total_files_parsed++;

        			(defined $DEBUG and $DEBUG > 1) and print
            			"DEBUG:parse_output_file(nodediag) Reading file $file,job $jobname,ident $testident " .
            			"(np=$np ppn=$ppn benchmark=$bench)\n";
				}
				else {
					# already have the file, just grab the buffer reference
					push @files_to_grok_bufrefs, $files_sucked_in{$f};
				}
			}
			
			# if we don't know the joblaunch method, we now need to look at
			# the output files and take an educated guess
			if ($joblaunchmethod eq 'NADA') {
				foreach my $bufref (@files_to_grok_bufrefs) {
					foreach my $l (@{$bufref}) {
						if ($l =~ /mpiexec:.*start evt/ or
                        	$l =~ /mpiexec: process_start_event: evt.*task/) {
							$joblaunchmethod = 'mpiexec';
							(defined $DEBUG and $DEBUG > 1) and print
								"DEBUG: nodediagnose guessed joblaunchmethod mpiexec\n";

							last;
						}
					}
					($joblaunchmethod ne 'NADA') and last;
				}
			}

			# if we haven't found a joblaunch method, we have to give up
			if ($joblaunchmethod eq 'NADA') {
            	(defined $DEBUG and $DEBUG > 1) and print "DEBUG:" .
                	"nodediag: COULD NOT determine joblaunch method\n";
            	last;
            }
			
			# OK... now we have all the output file data in buffers that
			# we need to look at and we have a joblaunch method
			my $ranktonode_parse_func_name = "$joblaunchmethod\_ranktonode_parse";
			*ranktonode_parse_func = \&$ranktonode_parse_func_name;
			
			# parse the output for ranktonode information!
			my $nodelistdata = ranktonode_parse_func(@files_to_grok_bufrefs);
			
			foreach $k (keys %{$nodelistdata}) {
				if ($k eq 'NUMPROCS') {
					($nodelistdata->{$k} != $np) and print "WARNING:nodediagnose: ".
						"parsed rank-to-node map for only $nodelistdata->{$k} out of ".
						"$np processes\n";
				}
				else {
					my $node = $nodelistdata->{$k};
					(!exists $nodediag_data{$node}) and $nodediag_data{$node} = 0;
					$nodediag_data{$node}++;
				}
			}

			# try to help with memory reclaimation
			@files_to_grok_bufrefs = undef;
		}

        (defined $DEBUG and $DEBUG > 2) and print
           	"DEBUG:parse_output_file() Done with $File::Find::name\n";

		foreach $k (keys %files_sucked_in) {
        	(defined $DEBUG and $DEBUG > 3) and print
           		"DEBUG:parse_output_file() $files_sucked_in{$k} size ",scalar @{$files_sucked_in{$k}},"\n";
			*ref = $files_sucked_in{$k};
			$#ref = -1;
			delete $files_sucked_in{$k};
		}
		%files_sucked_in = undef;
	}
}


sub results_to_stdout {
	my $outhash = shift;
	
	# Now we can run through the 2D hash and generate the output to stdout
	my $firstrow = 0;
	my $lastrow = 0;
	my $column = 0;
	my $row = 1;
	my @output = ();

	my $numjobs = keys %{$outhash->{'0'}};
	(defined $DEBUG and $DEBUG > 1) and print "DEBUG:results_to_stdout(): ".
		"numjobs=$numjobs\n";

	$numjobs -= 1;
	my $jobindex = 1;
	for $job (sort {$a <=> $b} (keys %{$outhash->{'0'}}) ) {
    	($job == 0) and next;

		if ($column == 0 ){
			for $np (sort {$a <=> $b} (keys %{$outhash}) ) {
				($np =~ /UNITS|META/) and next;
    			($np == 0) and next;
				$output[$row] .= color('bold yellow');
				$output[$row] .= sprintf("%4d ",$np);
				$output[$row] .= color('reset');
				$lastrow = $row;
				$row++;
			}
			$output[$firstrow] = color('bold yellow');
			$output[$firstrow] .= sprintf("%4s ",'NP');
			$output[$firstrow] .= color('bold cyan');
			$output[$firstrow] .= sprintf("%25s ",$outhash->{'0'}{$job});
			$output[$firstrow] .= color('reset');
			#$column++;
			$row = $firstrow + 1;
		}
		else {
			if (($column % 2) == 0) {
				$output[$firstrow] .= color('bold cyan');
			}
			else {
				$output[$firstrow] .= color('bold magenta');
			}
			$output[$firstrow] .= sprintf("%25s ",$outhash->{'0'}{$job});
			$output[$firstrow] .= color('reset');
			$row = $firstrow + 1;
		}

		for $np (sort {$a <=> $b} (keys %{$outhash}) ) {
    		($np == 0) and next;

			if (defined $outhash->{$np}{$job}) {
				$output[$row++] .= sprintf("%25s ",$outhash->{$np}{$job});
			}
			else {
				$output[$row++] .= sprintf("%25s ",'NODATA');
			}
    	}

		if (($column == $num_data_columns - 1) or $jobindex == $numjobs) {
			for ($i = $firstrow; $i <= $lastrow; $i++) {
				$output[$i] .= "\n";
			}
			$column = 0;
			$output[$lastrow+1] = "\n";
			$firstrow = $lastrow + 2;
			$row = $firstrow + 1;
		}
		else {
			$column++;
		}
		(defined $DEBUG and $DEBUG > 1) and print "DEBUG:results_to_stdout(): ".
			"jobindex=$jobindex\n";
		$jobindex++;
	}
	print @output;

}


sub results_to_gnuplot {
	my $outhash = shift;

	open (PLOT, ">$testset.dat");
	open (CMD, ">$testset.cmd");

	(defined $logy) and print CMD "set log y\n";
	(defined $logx) and print CMD "set log x\n";

	# NOTE: for the moment, we assume that all the metrics we are graphic
	#       will use the same units. this will eventually be migrated to
	#       use the gnuplot multiplot capability.
	my $units ='';
	foreach my $u (keys %{$outhash->{'UNITS'}}) {
		if (defined $outhash->{'UNITS'}{$u} and $outhash->{'UNITS'}{$u} !~ /UNITS/){
			$units = $outhash->{'UNITS'}{$u};
			last;
		}
	}
	print CMD
		"set ylabel \"$units\"\n" .
		"set xlabel \"Number of Processors\"\n" .
		"set key top left\n".
		"set title \"Cbench $testset Test Set Output Summary\"\n".
		"plot ";

	$numkeys = keys %{$outhash->{'0'}};
	$keyindex = 0;
	for $job (sort {$a <=> $b} (keys %{$outhash->{'0'}}) ) {
    	$keyindex++;
    	print PLOT "$outhash->{'0'}{$job} ";
    	($job == 0) and next;

    	print CMD "\"$testset.dat\" using 1:$keyindex title \"$outhash->{'0'}{$job}\" with lp";
    	($keyindex != $numkeys) and print CMD ",";
	}
	print PLOT "\n";
	print CMD "\n";

	for $np (sort {$a <=> $b} (keys %{$outhash}) ) {
		($np =~ /UNITS|META/) and next;
    	($np == 0) and next;

    	print PLOT "$np ";
    	for $job (sort {$a <=> $b} (keys %{$outhash->{'0'}}) ) {
        	($job == 0) and next;
			my $tempstr;
        	if (defined $outhash->{$np}{$job}) {
            	$tempstr = "$outhash->{$np}{$job} ";
        	}
        	else {
            	$tempstr = "NODATA ";
        	}
			print PLOT $tempstr;
    	}
    	print PLOT "\n";
	}
	print CMD
		"pause -1 'Hit <return> to close plot...\n" .
		"set term postscript color\n" .
		"set output \"$testset.ps\"\n" .
		"replot\n" .
		"quit\n";
	close(CMD);
	close(PLOT);

	exec "gnuplot $testset.cmd";

};

# do cleanup on the 2D output hash like removing data columns that have
# no data
sub cleanup_output_hash {
	my $outhash = shift;

    my $matchstr = "$metricstr";

	for $np (sort {$a <=> $b} (keys %{$outhash}) ) {
		($np =~ /UNITS|META/) and next;
    	($np == 0) and next;

    	for $job (sort {$a <=> $b} (keys %{$outhash->{'0'}}) ) {
        	($job == 0) and next;

			if ($outhash->{'META'}{$job} =~ /no datapoints/) {
				delete $outhash->{$np}{$job};
				delete $outhash->{'UNITS'}{$job};

			}
			elsif (defined $metricstr and ($outhash->{'0'}{$job} !~ /$matchstr/)) {
				# remove the metric if the --metric param was specified and
				# the metric name does not pass the regex
				delete $outhash->{$np}{$job};
				delete $outhash->{'UNITS'}{$job};				
			}
    	}
	}

   	for $job (sort {$a <=> $b} (keys %{$outhash->{'0'}}) ) {
		if ($outhash->{'META'}{$job} =~ /no datapoints/) {
			delete $outhash->{'0'}{$job};
		}
		elsif ($outhash->{'0'}{$job} =~ /NP/) {
			next;
		}
		elsif (defined $metricstr and ($outhash->{'0'}{$job} !~ /$matchstr/)) {
			delete $outhash->{'0'}{$job};		
		}
	}
};

sub dump_success_stats{
	my $hash = shift;

	if (defined $gnuplot) {
		open (PLOT, ">$testset.dat");
		open (CMD, ">$testset.cmd");

		(defined $logy) and print CMD "set log y\n";
		(defined $logx) and print CMD "set log x\n";

		print CMD
			"set ylabel \"%\"\n" .
			"set yrange [0:100]\n" .
			#"set y2label \"Number of Jobs\"\n" .
			#"set y2tics\n" .
			"set sample 10000\n" .
			"set ytics nomirror\n" .
			"set xlabel \"Number of Processors\"\n" .
			"set key top right\n".
			"set title \"Cbench $testset Test Set Job Success Summary\"\n".
			"plot ";

	}
	
	print color('bold yellow');
	printf "%4s ",'NP';
	print color('bold magenta');
	printf "%15s","Job Success %";
	print RESET "\n";
	(defined $gnuplot) and printf PLOT "%s %s %s %s\n",'NP',"Job_Success_%","Successful_Job_Count",
		"Total_Job_Count";
	(defined $gnuplot) and print CMD "\"$testset.dat\" using 1:2 title \"Job Success\" with filledcurves axes x1y1\n";
	#(defined $gnuplot) and print CMD "\"$testset.dat\" using 1:3 title \"Successful Jobs\" with fsteps axes x1y2,";
	#(defined $gnuplot) and print CMD "\"$testset.dat\" using 1:4 title \"Total Jobs\" with steps axes x1y2\n";
	
	for $np (sort {$a <=> $b} (keys %{$hash}) ) {
		my $temp = 0;
		$temp = ($hash->{$np}{'PASSED'} / $hash->{$np}{'TOTAL'} * 100)
			unless ($hash->{$np}{'TOTAL'} == 0);
		
		print color('bold yellow');
		printf "%4d ",$np;
		print color('reset magenta');
		printf "%15.2f  (%d of %d successful)","$temp",$hash->{$np}{'PASSED'},
			$hash->{$np}{'TOTAL'};
		print RESET "\n";
    	printf PLOT "%d %0.2f %d %d\n",$np,$temp,$hash->{$np}{'PASSED'},$hash->{$np}{'TOTAL'};
	}

	if (defined $gnuplot) {
		print CMD
			"f(x) = a*x**4 + b*x**3 + c*x**2 + d*x + e\n" .
			"fit f(x) \"$testset.dat\" u 1:2 via a, b, c, d, e\n".
			"replot f(x) title \"Job Success Curve Fit\" w l\n" .
			"pause -1 'Hit <return> to close plot...\n" .
			"set term postscript color\n" .
			"set output \"$testset.ps\"\n" .
			"replot\n" .
			"quit\n";
		close(CMD);
		close(PLOT);

		print "Hit <return> to close plot...\n";
		system "gnuplot $testset.cmd 2> /dev/null";
	}
}


sub dump_jobdiag_stats {
	my $hash = shift;

	print GREEN "\nJob Failure Diagnostics:\n-----------------------------\n";
	printf "%4s  %s\n",'NP',"Failure Diagnoses";
	for $np (sort {$a <=> $b} (keys %{$hash}) ) {
		printf "%4d   ",$np;
		foreach $k (sort {$a <=> $b} (keys %{$hash->{$np}}) ) {
			printf "%s=>%d, ",$k,$hash->{$np}{$k};
		}
		print "\n";
	}

}


sub dump_nodediag_stats {
	my $hash = shift;
	
	# allocate a new statistics variable
	my $statvar = Statistics::Descriptive::Full->new();

	print GREEN "\nJob Failure Node Diagnostics:\n-----------------------------\n";
	
	# there may be no data to dump...
	if ((scalar keys %{$hash}) == 0 ) {
		print "  NO Rank-to-Node data found\n";
		return;
	}

	# first we need to fill an array with the number of failures counted
	# on each node. there will be no mapping from the array to the nodediag_data
	# hash, but we want to do stats on the overall data and then get specific
	my @data = ();
	foreach my $k (keys %{$hash}) {
		push @data, $hash->{$k};
	}
	
	# move the data array to the statistics package
	$statvar->add_data(@data);
	
	printf "Number of unique nodes involved in failed jobs = %d\n",
		$statvar->count();
	printf "Max number of failed jobs on any node = %d\n",
		$statvar->max();
	printf "Min number of failed jobs on any node = %d\n",
		$statvar->min();
	printf "Average number of failed jobs on any node = %0.1f\n",
		$statvar->mean();
	printf "Median number of failed jobs on any node = %0.1f\n",
		$statvar->median();

	my $numbins = 5;
	print "\nFailure count frequency distribution ($numbins bins):\n";
	my %f = $statvar->frequency_distribution($numbins);
	for (sort {$b <=> $a} keys %f) {
	  print "  $_ failures: count = $f{$_}\n";
	}

	# print out nodes that are the worst offenders
	print "\nNodes with max number of job failures (worst offenders):\n";
	my $maxerrs = $statvar->max();
	foreach my $k (keys %{$hash}) {
		($hash->{$k} == $maxerrs) and print "  node $k: $hash->{$k} failures\n";
	}

}


sub open_and_slurp {
	my $file = shift;
	my $txtbuf = shift;

	use File::stat;
    my $stats = stat($file);

	# If the file is "big enough", this can cause Perl + Glibc memory mgmt
	# issues (some Glibc versions seem to hang in malloc...). So we'll apply
	# some heuristics to trim file sizes down in memory based on known output
	# file bloat.
	if (defined $stats and ($stats->size > 1024*1024*50)) {
		(defined $DEBUG and $DEBUG > 1) and print
			"DEBUG:open_and_slurp() BIG FILE of ".$stats->size." bytes\n";
		open(FILE, "$file") or return 0;
		my $i = 0;
		while (<FILE>) {
			# skip the "whitespace" output generated by the 
			# 'stress' benchmark since it can generate a TON of
			# useless output
			($_ =~ /\.\.\.\.\.\.\.\.\+$/) and next;
			$$txtbuf[$i++] = $_;
		};
		close(FILE);
	}
	else {
		(!defined $stats) and print "open_and_slurp(): stat() of $file failed...\n";

		# just slurp the file normally
		open(FILE, "$file") or return 0;
		@{$txtbuf} = <FILE>;
		close(FILE);
	}

	#tie(@txtbuf, 'Tie::File', $file, dw_size => 0, memory => 0) or do {
    #        	print "parse_output_file() Could not open $file for read ($!)\n";
	#			next;
	#		};

	return 1;
}


sub usage {
    print   "USAGE: $0 \n";
    print   "Cbench script to analyze job output in the $testset test set\n".
            "   --ident          Test identifier to analyze (optional).\n".
			"                    Can also have the form of a list:\n".
			"                      --ident test1,test2,test3\n".
            "   --gnuplot        Generate a Gnuplot and display it\n".
			"   --logy           Use a logarithmic y axis\n".
			"   --logx           Use a logarithmic x axis\n".
			"   --metric         A regex to include only certain metrics\n".
			"   --nodata         Don't print out the data tables, just errors\n".
			"                    and/or statistics\n".
            "   --diagnose       Include more data concerning errors and\n".
            "                    failures in jobs\n".
			"   --successstats   Generate an analysis of the percentage of jobs\n".
			"                    at each job size (i.e. processor count) that succeed\n".
			"   --nodediagnose   Analyze failed jobs and generate a list of nodes\n".
			"                    and the number of job failurs on each node.\n".
			"                    NOTE: this requires that rank-to-node information, i.e.\n".
			"                          MPI rank-to-node mapping information, is present\n".
			"                          in the job launch output.\n".
			"   --errorsonly     Only printout the error information\n".
			"                    e.g. --custom --diagnose --nodata\n" .
            "   --match          This limits the processing of job outputs to\n" .
            "                    jobs with a jobname that matches the specified\n" .
            "                    regex string. For example,\n" .
            "                      --match 2ppn\n" .
            "                    would only process 2 ppn tests\n" .
            "   --exclude        This is just like the --match parameter except\n" .
            "                    that jobs matching are NOT processed\n" .
			"   --minprocs <num> Only parse jobs whose number of processors is\n" .
			"                    greater than or equal to this parameter\n".
			"   --maxprocs <num> Only parse jobs whose number of processors is\n" .
			"                    less than or equal to this parameter\n".
            "   --debug <level>  turn on debugging at the specified level\n";
}
