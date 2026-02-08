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

use File::Find;
use Getopt::Long;
use Statistics::Descriptive;
use Data::Dumper;
$Data::Dumper::Sortkeys = 1;
use Time::localtime;
use File::stat;
use Date::Manip;
use Storable;
use Term::ANSIColor qw(:constants color);

my $num_data_columns = 2;
our $testset = find_testset_identity($0);
my $xaxis_ppn = 0;
my $xaxis_ppn_nodeview = 0;
my $follow_symlinks = 0;
my $cache_file = '.cbench_parse_cache';

# these are globals that print_job_err() has to look at
our $SHOWNOTICES = 0;
our $JOBID;
our %batch_jobdata = ();

# this is a string buffer to hold interesting details of what output_parse
# was asked to do and what data it found. we'll use this later to possibly record
# in gnuplot files used to generate plots to leave a trail of how and where
# the data came from.
my @invocation_data = ("\n\n# output_parse_generic.pl invocation and run data\n");
my $datestamp = `date`;
chomp $datestamp;
push @invocation_data, "# invoked: $datestamp\n";
# save the command line
push @invocation_data, "# command line: $0 @ARGV\n";

GetOptions( 'ident=s' => \$ident,
			'debug:i' => \$DEBUG,
			'logx' => \$logx,
			'logy' => \$logy,
			'yrange=s' => \$yrange,
			'xrange=s' => \$xrange,
			'xlabel=s' => \$xlabel,
			'linewidth=i' => \$linewidth,
			'keyinside' => \$keyinside,
			'addplot=s' => \@addplot,
			'normalize=s' => \$normalize,
			'gnuplot' => \$gnuplot,
			'help' => \$help,
			'meta' => \$meta,
			'diagnose' => \$diagnose,
			'successstats' => \$successstats,
			'nodediagnose' => \$nodediag,
			'nodata' => \$nodata,
			'filestats' => \$filestats,
			'customparse' => sub {$customparse = 1; $diagnose = 1},
			'errorsonly' => sub { $diagnose = 1; $customparse = 1; $nodata = 1 },
			'metric=s' => \$metricstr,
			'match=s' => \$match,
			'exclude=s' => \$exclude,
			'minprocs=i' => \$minprocs,
			'maxprocs=i' => \$maxprocs,
			'procs=i' => \$procs,
			'minnodes=i' => \$minnodes,
			'maxnodes=i' => \$maxnodes,
			'nodes=i' => \$nodes,
			'collapse:s' => \$collapse,
			'dplot=s' => \$dplot,
			'statsmode|statistics' => \$statsmode,
			'mean|meandata|average' => \$mean,
			'maximum|maxdata' => \$max,
			'minimum|mindata' => \$min,
			'listfound' => \$listfound,
			'numcolumns=i' => \$num_data_columns,
			'y2units=s' => \$y2units,
			'usecwd' => \$usecwd,
			'grepable' => \$grepable,
			'testset=s' => \$testset,
			'xaxis_ppn' => \$xaxis_ppn,
			'xaxis_ppn_nodeview' => \$xaxis_ppn_nodeview, 
			'speedup' => \$speedup,
			'parallelefficiency|peff' => \$paralleleff,
			'scaledparallelefficiency|speff' => \$scaledpeff,
			'follow_symlinks' => \$follow_symlinks,
			'walltimedata|walldata' => \$walldata,
			'showpassed' => \$showpassed,
			'shownotices' => \$SHOWNOTICES,
			'jobid=i' => \$jobid_match,
			'gazebo' => \$gazebo,
			'report:s' => \$report,
			'usecache' => \$usecache,
			'pokejobstatusi=s' => \$pokejobstatus,
                        'csv' => \$csv,
);

if (defined $help) {
    usage();
    exit;
}
if (defined $collapse and $collapse eq '') {
    usage();
    exit;
}

(defined $dplot and defined $gnuplot) and 
	die "--dplot and --gnuplot cannot be used together...";

(defined $gazebo and !defined $jobid_match) and die "--gazebo requires --job";

(!defined $mean and !defined $max and !defined $min) and $mean = 1;

# if stats mode is requested, force a change in behavior from what may have
# been specified on the command line
if (defined $statsmode or defined $grepable) {
	(defined $gnuplot) and warning_print("--gnuplot cannot be used with --statsmode,".
		" ignoring --gnuplot");
	undef $mean;
	undef $max;
	undef $min;
	undef $gnuplot;
	$num_data_columns = 1;
}

# if dplotting was requested, parse the params
if (defined $dplot) {
	@dplotparams = split(',',$dplot);
	$procs = $dplotparams[0];
	(defined $DEBUG) and print "DEBUG:dplotparams=@dplotparams\n";
}

($xaxis_ppn_nodeview) and $xaxis_ppn=1;
(defined $procs) and ($maxprocs = $procs and $minprocs = $procs);
(defined $nodes) and ($maxnodes = $nodes and $minnodes = $nodes);

# deal with normalization options
(defined $speedup) and ($normalize = 'minprocdata');
(defined $paralleleff) and ($normalize = 'numprocs');
(defined $scaledpeff) and ($normalize = 'minprocdata');
my $normalize_const = 1;
my $normalize_dyn = "9999999999999";
if (defined $normalize) {
	if ($normalize =~ /const/) {
		my @tmp = split('=',$normalize);
		$normalize_const = $tmp[1];
		debug_print(1, "DEBUG:normalize by constant = $normalize_const\n");
	}
	elsif ($normalize =~ /numprocs/) {
		debug_print(1, "DEBUG:normalize by number of procs\n");
	}
	elsif ($normalize =~ /minprocdata/) {
		debug_print(1, "DEBUG:normalize by the datapoint for min process count found\n");
	}
}

if (defined @addplot) {
	foreach (@addplot) {
		(defined $DEBUG) and print "DEBUG: addplot $_\n";
	}
}

my $bench_test = get_bench_test();
my $testpath = "$bench_test/$testset";
(defined $usecwd) and $testpath = $ENV{PWD};
(defined $DEBUG) and print "DEBUG: test tree path = $testpath\n";

if (!chdir $testpath) {
	print "WARNING: chdir to $testpath returned \'$!\'\n";
	print "You might need to set the CBENCHTEST environment variable differently\n".
		"or add the --usecwd flag to process data from the current directory.\n";
}

# save what directory we actually parsed in
push @invocation_data, "# dir parsed: $ENV{PWD}\n";

# var for fstat data
my $fstat = undef;

# hash to hold all the raw data that is returned by the
# parsing modules
my %data = ();

# hash to hold summary data of the statuses returned from
# parsing each job output
my %statusdata = ();

# some statistics vars
my $total_files_parsed = 0;
my $total_files_examined = 0;
my $total_jobs_parsed = 0;

# in the --report modes, we need to store more data in different ways
#
# we want the walltime data in --report mode
my %reportdata = (
	'firstjob_stamp' => 9999999999,
	'lastjob_stamp' => 0,
	'accum_wallclock_minutes' => 0.0,
	'accum_nodehour_minutes' => 0.0,
);
if (defined $report) {
	$walldata = 1;
}


# load all theh hw_test modules, we'll need them for parsing
# the output files
my %parse_modules;
load_parse_modules(\%parse_modules);

# Load all theh parse_filter modules which define the %parse_filters
# hash, i.e. the custom parse filters feature. We'll need them for parsing
# the output files if the --customparse flag is given
my %parse_filters;
load_parse_filter_modules(\%parse_filters);

# ask each output parse module what files it will want parsed. each
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
	print Dumper (\%parse_modules_files);
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
my $spec = undef;
foreach $k (keys %parse_modules) {
	eval {
		$parse_modules{$k}->alias_spec();
	};
	if ($@ =~ /Can't locate object method/) {
		debug_print(2,"DEBUG: No alias_spec method in $k module\n");
		next;
	}
	
	(defined $spec) and $spec = undef;
	$spec = $parse_modules{$k}->alias_spec();
	if (defined $spec) {
		debug_print(2,"DEBUG: Found alias_spec method in $k module\n");
		$bench_aliases{$k} = $spec;
	}
	else {
		debug_print(2,"DEBUG: alias_spec method in $k module was UNDEF\n");
	}
}


# This a mapping hash that will be built as we parse output files.
# It maps  a given metric to the units it is using which is 
# critical for graphing... we need to know what to put on the Y axis
# label!!!...and we have to figure it out dynamically
my %metrics_to_units;
(defined $walldata) and $metrics_to_units{walltime} = 'minutes';

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

# This hash is used to hold aggregated data about custom parse filter
# hits.
my %customparse_hits;

# if --pokejobstatus <file> was given, we need to read the file into
# the %pokestatus hash. the purpose of this option is to allow a way
# to override the status (e.g. PASSED, ERROR(FOO), ERROR(BAR)) of jobs
# that are specified in the simple text file. this is mostly useful
# for massive use of Cbench, like in a synthetic workload sustained
# test which will run thousands of jobs, where some jobs need to be
# post processed with extra information correlation . for instance,
# many real world applications run as many simulation timesteps as
# they can fit in before a batch scheduler kills them. then, they
# continue from the last set of restart files. Cbench includes jobs like
# this in testsets from the Openapps tree, i.e. the LAMMPS rhodolong.scaled
# job. the cbench output parser sees these jobs killed by walltime
# as errors since the application does not shutdown normally. 
# --pokejobstatus gives the ability to tell Cbench to assign any
# status to any jobid via a text file formatted like:
#
# job1 status1 comment
# job2 status2 comment
#
# each line in the file is a single jobid
my %pokestatus = ();
if (defined $pokejobstatus) {
	if (open(POKE,"<$pokejobstatus")) {
		while (<POKE>) {
			if (/^(\S+)\s+(\S+)\s+(.*)$/) {
				$pokestatus{$1} = $2;
				debug_print(2,"DEBUG: pokestatus job $1 status $2 comment \"$3\"");
			}
		}
	}
	else {
		error_print("Could not open $pokejobstatus with error ($!), ".
			"job status poking disabled\n");
		$pokejobstatus = undef;
	}
}

#
# HERE IS WHERE THE REAL PARSING WORK GETS KICKED OFF...
#
# Recursively process all files from the current directory and
# below. If the --ident parameter is given, only process the
# directory tree indicated.
my $metaset;
if (defined $meta and !defined $usecache) {
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
		if (defined $ident) {
			# looks like a list of idents was specified
			my @identlist = split(',',$ident);
			debug_print(1,"DEBUG: list of idents: ". join(' ',@identlist). " \n");
			foreach (@identlist) {
				$basepath = ".\/$_";
				find({wanted => \&parse_output_file, follow => $follow_symlinks}, $basepath);
			}
		}
		else {
			find({wanted => \&parse_output_file, follow => $follow_symlinks}, $basepath);
		}
		chdir $pwd;
	}
	closedir(DH);
}
elsif (!defined $usecache)  {
	$basepath = ".";
	if (defined $ident) {
		# looks like a list of idents was specified
		my @identlist = split(',',$ident);
		debug_print(1,"DEBUG: list of idents: ". join(' ',@identlist). " \n");
		foreach (@identlist) {
			$basepath = ".\/$_";
			find({wanted => \&parse_output_file, follow => $follow_symlinks}, $basepath);
		}
	}
	else {
		find({wanted => \&parse_output_file, follow => $follow_symlinks}, $basepath);
	}
}
elsif (defined $usecache) {
	my $href = undef;

	%data = %{retrieve("$cache_file-data")};
	%statusdata = %{retrieve("$cache_file-statusdata")};
	%success_data = %{retrieve("$cache_file-success_data")};
	%jobdiag_data = %{retrieve("$cache_file-jobdiag_data")};
	%nodediag_data = %{retrieve("$cache_file-nodediag_data")};
	%metrics_to_units = %{retrieve("$cache_file-metrics_to_units")};
	%unit_groupings = %{retrieve("$cache_file-unit_groupings")};
	%reportdata = %{retrieve("$cache_file-reportdata")};
}

#
# At this point, all the output files have been parsed and the data collected.
# All that follows below is analysis and output code.
#

if (defined $DEBUG and $DEBUG > 2) {
	print "====================================================================\n";
	print "DEBUG: Dumping \%data hash:\n";
	print Dumper (\%data);
	print "====================================================================\n";
	print "DEBUG: Dumping \%metrics_to_units hash:\n";
	print Dumper (\%metrics_to_units);
	print "====================================================================\n";
	print "DEBUG: Dumping \%unit_groupings hash:\n";
	print Dumper (\%unit_groupings);
	print "====================================================================\n";
	print "DEBUG: Dumping \%jobdiag_data hash:\n";
	print Dumper (\%jobdiag_data);
	print "====================================================================\n";
	print "DEBUG: Dumping \%success_data hash:\n";
	print Dumper (\%success_data);
	print "====================================================================\n";
	print "DEBUG: Dumping \%nodediag_data hash:\n";
	print Dumper (\%nodediag_data);
}

# We need to run through the raw data hash once to get a list of all the
# possible metrics we'll need to deal with.  This is dynamic with each run
# because the output parsing modules can choose to send new/different data,
# parse different runs, etc.
#
# We also find our dplot data in this loop as well.
%metrics = ();
%benchlist = ();
$matchstr = "$metricstr";
%dplotdata = ();
$didx = 0;
my %ppndata = ();
for $testid (keys %data) {
    for $ppn (keys %{$data{$testid}}) {
		for $bench (keys %{$data{$testid}{$ppn}}) {
			$benchlist{$bench} = 1;
			for $np (keys %{$data{$testid}{$ppn}{$bench}}) {
				for $k (keys %{$data{$testid}{$ppn}{$bench}{$np}}) {
					if ($xaxis_ppn_nodeview) {
						# store data for use when ppn is on the x-axis
						my $ppn_num = $ppn;
						$ppn_num =~ s/ppn//;
						my $tmpnodes = calc_num_nodes($np,$ppn_num);
						$ppndata{$testid}{"$tmpnodes"."node"}{$bench}{$ppn_num} = $data{$testid}{$ppn}{$bench}{$np};
					}
					elsif ($xaxis_ppn) {
						# store data for use when ppn is on the x-axis
						my $ppn_num = $ppn;
						$ppn_num =~ s/ppn//;
						$ppndata{$testid}{"np$np"}{$bench}{$ppn_num} = $data{$testid}{$ppn}{$bench}{$np};
					}

					if ($k =~ /^DATA/) {
						my $metric = $k;
						$metric =~ s/DATA_//;
						(defined $metricstr and ($metric !~ /$matchstr/)) and next;

						$metrics{$k} = $bench;

						if (defined $dplot) {
							next unless ($dplotparams[0] == $np);
							my $tag = "$testid\-$bench\-$ppn\-$np\-$metric";
							#print "$tag $k\n";
							foreach my $dat (@{$data{$testid}{$ppn}{$bench}{$np}{$k}}) {
								$dplotdata{$didx}{'tag'} = $tag;
								$dplotdata{$didx}{'dat'} = $dat;
								(defined $normalize) and $dplotdata{$didx}{'dat'} = normalize_value($dat);
								$didx++;
							}
						}
					}
				}
			}
		}
	}
}
(defined $DEBUG and $DEBUG > 2) and do {
	print "====================================================================\n";
	print "DEBUG: Dumping \%metrics hash:\n";
	print Dumper (\%metrics);
	print "====================================================================\n";
	print "DEBUG: Dumping \%dplotdata hash:\n";
	print Dumper (\%dplotdata);
};


# We are going to build a 2D hash. The first dimension is the number of
# processors. The second dimension is an ordered list of column data
# where each column corresponds to a jobname, eg. cgC-2ppn
my %outhash = ();
my $columnidx = 1;
$outhash{'0'}{'0'} = $xaxis_ppn ? "PPN" : "NP";
$outhash{'UNITS'}{'0'} = "UNITS";
$outhash{'META'}{'0'} = "META";

if ($xaxis_ppn) {
	# this could be a bit misleading based on the variable names used in the loops below.
	# %ppndata contains the same data as %data, only with PPN as the second hash key and
	# NP as the fourth
	%data = %ppndata;
}

my $numtestids = keys %data;
for $testid (keys %data) {
    for $ppn (keys %{$data{$testid}}) {
		for $bench (keys %{$data{$testid}{$ppn}}) {
			# if we are in --usecache mode the --match/--exclude parameters will not
			# work they normally do because we aren't actually parsing files. so we
			# apply them in this loop when we are operating out of cache
			if (defined $usecache) {
		    	my $tmpname = "$testid-$bench-$ppn\n";
				(defined $match and $tmpname !~ /$match/) and next;
				(defined $exclude and $tmpname =~ /$exclude/) and next;
			}

			my %columns = ();
			for $rawmetric (keys %metrics) {
				$metric = $rawmetric;
				$metric =~ s/DATA_//;

				# key zero, which would be 0 processors, in the first dimension
				# of the hash is the 'legend' line that records which column
				# corresponds to which job series
				if (defined $mean) { 
					$columns{'mean'} = $columnidx++;
					$outhash{'0'}{"$columns{'mean'}"} .= "$testid-$bench-$ppn-$metric-mean";
					# correlate the metric to its units in the 2D hash
					$outhash{'UNITS'}{"$columns{'mean'}"} = $metrics_to_units{$metric};
				} 
				if (defined $max) { 
					$columns{'max'} = $columnidx++;
					$outhash{'0'}{"$columns{'max'}"} .= "$testid-$bench-$ppn-$metric-max";
					# correlate the metric to its units in the 2D hash
					$outhash{'UNITS'}{"$columns{'max'}"} = $metrics_to_units{$metric};
				} 
				if (defined $min) { 
					$columns{'min'} = $columnidx++;
					$outhash{'0'}{"$columns{'min'}"} .= "$testid-$bench-$ppn-$metric-min";
					# correlate the metric to its units in the 2D hash
					$outhash{'UNITS'}{"$columns{'min'}"} = $metrics_to_units{$metric};
				} 
				if (defined $statsmode or defined $grepable or defined $csv) {
					$columns{'stats'} = $columnidx++;
					$outhash{'0'}{"$columns{'stats'}"} .= "$testid-$bench-$ppn-$metric";
					# correlate the metric to its units in the 2D hash
					$outhash{'UNITS'}{"$columns{'stats'}"} = $metrics_to_units{$metric};
				} 

				my $found_some_data = 0;
				my $first_np_loop_trip = 1;
            	for $np (sort {$a <=> $b} (keys %{$data{$testid}{$ppn}{$bench}}) ) {
                	if (exists $data{$testid}{$ppn}{$bench}{$np}{'PASSED'} and
						$data{$testid}{$ppn}{$bench}{$np}{'PASSED'} >= 1 and
						exists $data{$testid}{$ppn}{$bench}{$np}{$rawmetric}) {

                    	# if at least one test passed, we have data to report
						$found_some_data = 1;
						my $statvar = Statistics::Descriptive::Full->new();
						$statvar->add_data(@{$data{$testid}{$ppn}{$bench}{$np}{$rawmetric}});

						# if we are trying to normalize by the data found for 1 mpi
						# process we need to look for that and tuck it away
						if (defined $normalize and $normalize =~ /minprocdata/) {
							if ($first_np_loop_trip) {
								my $num = $statvar->mean();
								debug_print(2,"DEBUG: found minprocdata normalize data, ".
									"$testid-$ppn-$bench-$np $metric = $num");
								$normalize_dyn = $num;
								$first_np_loop_trip = 0;
							}
						}

						if (defined $mean) {
							my $num = $statvar->mean();
							if (defined $normalize) {
								$num = normalize_value($num,$np); 
							}
							$outhash{$np}{"$columns{'mean'}"} = sprintf("%25.4f",$num);
						}
						if (defined $max) {
							my $num = $statvar->max();
							if (defined $normalize) {
								$num = normalize_value($num,$np); 
							}
							$outhash{$np}{"$columns{'max'}"} = sprintf("%25.4f",$num);
						}
						if (defined $min) {
							my $num = $statvar->min();
							if (defined $normalize) {
								$num = normalize_value($num,$np); 
							}
							$outhash{$np}{"$columns{'min'}"} = sprintf("%25.4f",$num);
						}
						if (defined $statsmode) {
							my $mean = $statvar->mean();
							my $max = $statvar->max();
							my $min = $statvar->min();
							my $stddev = $statvar->standard_deviation();
							my $count = $statvar->count();
							$outhash{$np}{"$columns{'stats'}"} = sprintf("mean=%0.4f ",$mean) .
								sprintf("max=%0.4f ",$max) .
								sprintf("min=%0.4f ",$min) .
								sprintf("stddev=%0.4f ",$stddev) .
								sprintf("count=%d ",$count) . 
								sprintf("(%s) ",$metrics_to_units{$metric});
						}
						if (defined $grepable) {
							my $mean = $statvar->mean();
							my $max = $statvar->max();
							my $min = $statvar->min();
							my $stddev = $statvar->standard_deviation();
							my $count = $statvar->count();
							$outhash{$np}{"$columns{'stats'}"} = sprintf("%0.4f, ",$mean) .
								sprintf("%0.4f, ",$max) .
								sprintf("%0.4f, ",$min) .
								sprintf("%0.4f, ",$stddev) .
								sprintf("%d, ",$count) . 
								sprintf("%s ",$metrics_to_units{$metric});
						}
                	}
                	else {
						foreach (keys %columns) {
                    		$outhash{$np}{"$columns{$_}"} = "NODATA";
						}
                	}
            	}
				
				if (!$found_some_data) {
					foreach (keys %columns) {
						$outhash{'META'}{"$columns{$_}"} = "no datapoints";
					}
				}
				$column1 += 3;

				# reset the $normalize_data value if we are doing the 
				# minprocdata normalization, because this will change with
				# each metric, benchmark, etc....
				(defined $normalize and $normalize =~ /minprocdata/) and 
					$normalize_dyn = "9999999999999";
        	}
		}
    }
}
cleanup_output_hash(\%outhash);
(defined $DEBUG and $DEBUG > 2) and do {
	print "====================================================================\n";
	print "DEBUG: Dumping \%outhash hash:\n";
	print Dumper (\%outhash);
};

print "\n";

if (defined $gazebo) {
	# output specifically for running under Gazebo
	#
	# in gazebo mode we should only be dealing with a single job so we
	# do things a bit differently and restrict our output
	my $numkeys = keys %statusdata;
	($numkeys > 1) and 
		warning_print("Found more than one job status key in Gazebo mode...");

	my @output = ();
	for $job (sort {$a <=> $b} (keys %{$outhash{'0'}}) ) {
    	($job == 0) and next;

		for $np (sort {$a <=> $b} (keys %outhash) ) {
    		($np == 0) and next;

			# clean up the data series name to be just the data point name
			my $series = $outhash{'0'}{$job};
			$series =~ s/(\S+\-\d+ppn\-)//;
			$series =~ s/(-mean$)//;

			my $line = "<td> $series ";

			# print data
			if (defined $outhash{$np}{$job}) {
				my $str = sprintf("%s",$outhash{$np}{$job});
				$str =~ s/\s+//;
				$line .= $str;
			}

			# print units
			$line .= " $metrics_to_units{$series}";

			push @output, "$line\n" unless (!defined $outhash{$np}{$job});
    	}
	}
	print @output;
	print "\n";

	if ($statusdata{PASSED} == 1) {
		print "Job $jobid_match PASSED\n";
	}
	else {
		foreach my $k (keys %statusdata) {
			print "Job $jobid_match FAILED with $k\n";
		}
	}
	exit;
}

# Dump out the results in a grep happy table format if requested.
# This supersedes all other output dumping.
if (defined $grepable) {
	results_to_stdout_grephappy(\%outhash);
	exit;
}

if (defined $csv) {
    results_to_csv(\%outhash);
    exit;
}

# print results to stdout
(!defined $nodata) and results_to_stdout(\%outhash);

(defined $successstats) and dump_success_stats(\%success_data);

(defined $diagnose) and dump_jobdiag_stats(\%jobdiag_data);

(defined $customparse) and dump_customparse_hits(\%customparse_hits);

(defined $nodediag) and dump_nodediag_stats(\%nodediag_data);

if (defined $listfound) {
	print GREEN "\nList of key stuff found during parsing:\n";
	print GREEN "---------------------------------------\n";
	my $tmp = "";
	print "Test identifiers: ";
	$tmp .= "# Test identifiers: ";
	for $k (keys %data) {
		print  "$k ";
		$tmp .= "$k ";
	}
	print "\n";
	print "Benchmarks: ";
	$tmp .= "\n# Benchmarks: ";
	for $k (keys %benchlist) {
		print  "$k ";
		$tmp .= "$k ";
	}
	print "\n";
	print "Data metrics:\n";
	$tmp .= "\n# Data metrics:\n";
	foreach my $k (keys %metrics) {
		($ktrim = $k) =~ s/DATA_//;
		print "  \'$ktrim\' from benchmark \'$metrics{$k}\'\n";
		$tmp .= "#  \'$ktrim\' from benchmark \'$metrics{$k}\'\n";
	}
	print "\n";
	push @invocation_data, $tmp; 
}

(defined $report) and report_to_stdout();

print GREEN "\nParse Summary:\n--------------\n";
print "Total Files Parsed = $total_files_parsed\n";
push @invocation_data, "# Total Files Parsed = $total_files_parsed\n";
print "Total Jobs Parsed = $total_jobs_parsed\n";
push @invocation_data, "# Total Jobs Parsed = $total_jobs_parsed\n";

# print out a summary of job status with the ERRORs summed up
# and detailed, thus the double loop business...
print GREEN "\nJob Status Summary:\n-------------------\n";
my @tmpbuf = ();
my $tmperrs = 0;
foreach $k (keys %statusdata) {
	if ($k =~ /^ERROR/) {
		$tmperrs += $statusdata{$k};
		push @tmpbuf, "  $k = $statusdata{$k}\n";
	}
}
foreach $k (keys %statusdata) {
	($k =~ /^ERROR/) and next;
	print "$k = $statusdata{$k}\n";
}
print "FAILED = $tmperrs\n";
print join('',@tmpbuf) . "\n";

my $temp = 0;
my $temp2 = $total_jobs_parsed - $statusdata{'NOTICE'} - $statusdata{'RUNNING'};
$temp = $statusdata{'PASSED'}/$temp2 unless ($temp2 == 0);
printf "Overall Job Success = %0.2f%%\n",$temp*100;
push @invocation_data, sprintf "# Overall Job Success = %0.2f%%\n",$temp*100;

# write out a cache of the data structures we painstakingly built
if (!defined $usecache) {
	store \%data, "$cache_file-data";
	store \%statusdata, "$cache_file-statusdata";
	store \%success_data, "$cache_file-success_data";
	store \%jobdiag_data, "$cache_file-jobdiag_data";
	store \%nodediag_data, "$cache_file-nodediag_data";
	store \%metrics_to_units, "$cache_file-metrics_to_units";
	store \%unit_groupings, "$cache_file-unit_groupings";
	store \%reportdata, "$cache_file-reportdata";
}

# build a gnuplot if asked, but we can only do one gnuplot per invocation right now...
(defined $gnuplot) and results_to_gnuplot(\%outhash) unless (defined $successstats);

# build a dplot if asked
(defined $dplot) and results_to_dplot(\%outhash) unless (defined $successstats);



###############################################################
# subroutines
#


# this is the guts of the output file parsing
sub parse_output_file {
	my $filename = $_;

	debug_print(4,"DEBUG:parse_output_file: File::Find found $File::Find::name\n");

	if ($filename =~ /\.o(\d+)$/) {
		# Found an output file for stdout for a job.

	    debug_print(4,"DEBUG:parse_output_file: Entering output file block for $filename\n");

		my $jobid = $1;
		# save in global var for print_job_err()
		$JOBID = $jobid; 
		my ($bench, $extra, $jobname);

		# if the --jobid parameter was specified we are only looking for a single
		# jobid
		if (defined $jobid_match) {
			($jobid_match != $jobid) and next;
		}

        # Extract information we want from the name of the file we
        # are going to parse. We can do this because the file name
        # includes path and the directories in the path have 
        # embedded information for us.
        my @patharray = split '/',$File::Find::name;
        my $stdout_file = $patharray[$#patharray];

		# check to make sure the output file is really a file... sometimes a randomly
		# generated directory can have the form *.o12345 and it causes a non-fatal odd
		# error
		(! -f $stdout_file) and next;

		# fileid vars just help us with debug and status output
		my $fileid = '';
		my $fileid_path = '';

		# Cbench jobs are all contained inside directories now
		my $testident;
		$testident = $patharray[$#patharray-2];
		(defined $meta) and $fileid = "$metaset\/";
		$fileid_path = "$testident\/$patharray[$#patharray-1]";
		$fileid .= "$testident\/$patharray[$#patharray-1]\/$patharray[$#patharray]";

		$total_files_examined++;
		(! defined $DEBUG and ($total_files_examined % 50) == 0) and print ".";

		debug_print(1,"DEBUG:parse_output_file() Examining $stdout_file ident=$testident\n");

		(defined $collapse) and $testident = $collapse;

		# In the olden days, we started embedding info to avoid
		# batch systems filename truncatiion. Now we embed more info
		# that can be useful later on in parsing.
		# Read in the embedded Cbench info tags.
		undef $/;
		# protect the grep from chewing endlessly on a huge file with head and tail
		my $embedded_info_buf = `head -100 $stdout_file | egrep '\^Cbench \.\*\\:'`;
		$embedded_info_buf .= `tail -100 $stdout_file | egrep '\^Cbench \.\*\\:'`;
		$/ = "\n";
		if ($embedded_info_buf =~ /Cbench \S+\:/) {
			# found embedded Cbench info
			debug_print(3,"DEBUG:parse_output_file() dumping embedded info: $embedded_info_buf\n");

			# extract jobname
			my ($tmpjob) = $embedded_info_buf =~ /\nCbench jobname: (\S+)\n/;
			if ($tmpjob =~ /ppn/) {
				# looks like we grabbed a jobname
				(defined $DEBUG and $DEBUG > 1) and print
					"DEBUG:parse_output_file() using embedded jobname $tmpjob for $stdout_file\n";
				$jobname = $tmpjob;
			}
		}
		else {
			warning_print("parse_output_file() $fileid is missing embedded Cbench info..skipping");
			next;
		}

		# check for combobatch output files which are not parsed directly
		if ($embedded_info_buf =~ /Cbench benchmark:\s+combobatch/) {
			next;
		}
		
        # parse the jobname to get important characteristics of the job
        ($bench, $ppn, $np) = ($jobname =~ /^(\S+)\-(\d+)ppn[\-|\.](\d+)$/);
        $ppnstr = $ppn . "ppn";

		# build a string composed of the test identifier + jobname which
		# we'll use to match/exclude against. this ident+jobname string is the
		# prefix of and data series names we'll construct later on which are
		# ident+jobname+metric
		# actually the jobname isn't quite accurate, jobname minus the numprocs
		# count at the end
		my $ident_jobname = "$testident-$bench-$ppnstr";

        # if --match param was used, only process files matching the regex
        if (defined $match) {
            $matchstr = "$match";
            next unless ($ident_jobname =~ /$matchstr/);
        }
        # if --exclude param was used, only process files NOT matching
        if (defined $exclude) {
            $matchstr = "$exclude";
            next unless ($ident_jobname !~ /$matchstr/);
        }

		debug_print(1,"DEBUG:parse_output_file() PARSEing $stdout_file ident=$testident\n");

		debug_print(2,"DEBUG:parse_output_file() bench=$bench extra=$extra jobid=$jobid ident=$testident stdoutfile=$stdout_file\n");

		# filter out based on the --minprocs/--maxprocs flags
		(defined $minprocs and $np < $minprocs) and next;
		(defined $maxprocs and $np > $maxprocs) and next;
		# filter out based on the --minnodes/--maxnodes flags
		my $numnodes = calc_num_nodes($np,$ppn);
		(defined $minnodes and $numnodes < $minnodes) and next;
		(defined $maxnodes and $numnodes > $maxnodes) and next;
		
		# if the output file is from a slurm batch job, query Slurm for the current state
		# of running jobs and cache the result.  we'll use this cached data to cross reference
		# jobs with ERROR states and cull jobs that are running in slurm.  since slurm
		# spools job stdout/stderr continually, it is hard to tell the difference between
		# a running job which gets an error and a job that has finished but had an error.
		#
		# updated with support for detecting running jobs with Torque
		if ((!exists $batch_jobdata{TOTAL}) and ($filename =~ /slurm\.o/)) {
			debug_print(2,"DEBUG:parse_output_file: Found Slurm output file, querying Slurm for running jobs\n");
			%batch_jobdata = slurm_query();
		}
		elsif ((!exists $batch_jobdata{TOTAL}) and ($filename =~ /\.pbs\.o/)) {
			debug_print(2,"DEBUG:parse_output_file: Found Torque/PBS output file, querying Torque for running jobs\n");
			%batch_jobdata = batch_query();
		}

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
		my %bufref_to_files = ();
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

        	# open and slurp the output file unless the job is currently RUNNING
			my @txtbuf;
			if (exists $main::batch_jobdata{$JOBID} and $main::batch_jobdata{$JOBID} eq 'running') {
				$txtbuf[0] = "hi";
			}
			else {
				open_and_slurp($file,\@txtbuf) or do {
					# FIXME: this probably should be printed for non-STDERR files?
					debug_print(1,"parse_output_file() Could not open $file for read ($!)\n");

					# there was a problem opening the file for some reason, in this case
					# open_and_slurp() will return a valid array buffer that is empty
					# and we'll let this fall through to the code below which saves the
					# valid buffer reference to a trivially empty buffer
				};
			}

			# save references to this buffer
			push @output_bufrefs, \@txtbuf;
			$files_sucked_in{$f} = \@txtbuf;
			$bufref_to_files{\@txtbuf} = $file;

			$total_files_parsed++;

        	(defined $DEBUG and $DEBUG > 1) and print
            	"DEBUG:parse_output_file() Reading file $file,job $jobname,ident $testident " .
            	"(np=$np ppn=$ppn benchmark=$bench)\n";
		}

		debug_print(3,"DEBUG:parse_output_file() Starting core buffer parsing with $parsemod module for benchmark $bench\n");

		# we have all the buffers we need, so call the parse() method of the appropriate
		# parse module and pass the array of output buffer references
		my $filedata = $parse_modules{$parsemod}->parse("$fileid",@output_bufrefs);
		#print Dumper (\%{$filedata});

		# try to help with memory reclaimation
		@output_bufrefs = undef;

		# record the current testset we are in to facilitate the hash data
		# structure inserting that follows
		my $currtestset = $testset;
		(defined $meta) and $currtestset = $metaset;

		my $jobpassed = 1;
		my @keylist = keys %{$filedata};
		foreach my $k (@keylist) {
			# is this the STATUS key returned by the parse module?
			if ($k eq 'STATUS') {
				my $status = $filedata->{$k};

				# if the job was a Slurm batch job, check to see if it is still running
				# by querying the cached slurm_jobdata hash. a job that is still running
				# in Slurm looks like a job with an error to the output parsing logic due
				# to Slurm spooling stdout/stderr data from the job continually. if the
				# job is still running, update is $status appropriately.
				#
				# updated with more generic support for detecting running jobs
				if (exists $main::batch_jobdata{$JOBID} and $main::batch_jobdata{$JOBID} eq 'running') {
					$status = 'RUNNING';
					$filedata->{'STATUS'} = 'RUNNING';
				}

				# if --pokejobstatus was given, we need to possibly update the status of the job
				if (defined $pokejobstatus and exists $pokestatus{$jobid}) {
					$status = $pokestatus{$jobid};
					print BOLD GREEN "**POKED**";
					print RESET "(";
					print GREEN, "$fileid";
					print RESET ")";
					print BOLD WHITE " with status",BOLD MAGENTA . "$status";
					print RESET "\n";
					print "-------------------------------------------------------------\n";
				}

				# update the fine grained status data
				(!exists $data{$testident}{$ppnstr}{$bench}{$np}{$status}) and
					$data{$testident}{$ppnstr}{$bench}{$np}{$status} = 0;
				$data{$testident}{$ppnstr}{$bench}{$np}{$status}++;
				
				# update the overall status summary data
				(!exists $statusdata{$status}) and $statusdata{$status} = 0;
				$statusdata{$status}++;

				# updated job failure diagnostic data
				if ($status ne 'PASSED' and $status ne 'NOTICE' and $status ne 'RUNNING') {
					$jobdiag_data{$np}{$filedata->{$k}}++;
					$jobpassed = 0;

					if (defined $filestats and defined $diagnose) {
						print BOLD MAGENTA "**FILESTAT**";
						print RESET "(";
						print GREEN, "$fileid";
						print RESET ")";
						$stamp = ctime($fstats->mtime);
						print BOLD MAGENTA " last modified: ";
						print BOLD GREEN "$stamp";
						print RESET "\n";
					}

					if (defined $report) {
						if (! exists $reportdata{testsets}{$testident}{$currtestset}{$bench})  {
							$reportdata{testsets}{$testident}{$currtestset}{$bench}{passed} = 0;
							$reportdata{testsets}{$testident}{$currtestset}{$bench}{failed} = 0;
							$reportdata{testsets}{$testident}{$currtestset}{$bench}{notice} = 0;
						}
						$reportdata{testsets}{$testident}{$currtestset}{$bench}{failed}++;
					}
				}
				# on job success update data
				elsif ($status eq 'PASSED') {
					$success_data{$np}{'PASSED'}++;

					if (defined $showpassed) {
						print BOLD GREEN "**PASSED**";
						print RESET "(";
						print GREEN, "$fileid";
						print RESET ")";
						print RESET "\n";
						if (defined $filestats) {
							print BOLD MAGENTA "**FILESTAT**";
							print RESET "(";
							print GREEN, "$fileid";
							print RESET ")";
							(defined $fstats) and $stamp = ctime($fstats->mtime);
							print BOLD MAGENTA " last modified: ";
							print BOLD GREEN "$stamp";
							print RESET "\n";
						}
						print "-------------------------------------------------------------\n";
					}

					if (defined $report) {
						if (! exists $reportdata{testsets}{$testident}{$currtestset}{$bench})  {
							$reportdata{testsets}{$testident}{$currtestset}{$bench}{passed} = 0;
							$reportdata{testsets}{$testident}{$currtestset}{$bench}{failed} = 0;
							$reportdata{testsets}{$testident}{$currtestset}{$bench}{notice} = 0;
						}
						$reportdata{testsets}{$testident}{$currtestset}{$bench}{passed}++;
					}
				}
				elsif ($status eq 'NOTICE' and defined $report) {
					if (! exists $reportdata{testsets}{$testident}{$currtestset}{$bench})  {
						$reportdata{testsets}{$testident}{$currtestset}{$bench}{passed} = 0;
						$reportdata{testsets}{$testident}{$currtestset}{$bench}{failed} = 0;
						$reportdata{testsets}{$testident}{$currtestset}{$bench}{notice} = 0;
					}
					$reportdata{testsets}{$testident}{$currtestset}{$bench}{notice}++;
				}
				elsif ($status eq 'NOTICE' and $SHOWNOTICES ) {
					$jobpassed = 1;
					print "-------------------------------------------------------------\n";
				}
				elsif ($status eq 'RUNNING') {
					$jobpassed = 1;
					(defined $diagnose) and print "-------------------------------------------------------------\n";
				}

				$success_data{$np}{'TOTAL'}++;
				
				next;
			}
			elsif ($k =~ /MULTIDATA/) {
				# do nothing yet.....
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

		# if we are grokking walltime data capture in the output file that
		# was generated by the Cbench scripts, then grab it and tuck it away
		# in the data hash
		if (defined $walldata) {
			# grab it from the embedded Cbench info we already have
			if ($embedded_info_buf =~ /\nCbench\s+elapsed\s+seconds:\s+(\d+)\n/) {
				# insert into our data hash
				my $key = "DATA_walltime";
				push @{$data{$testident}{$ppnstr}{$bench}{$np}{$key}}, ($1/60.0);

				# poke some data into the report data structure
				if (defined $report) {
					$reportdata{accum_wallclock_minutes} +=  $1;
					$reportdata{accum_nodehour_minutes} +=  $1 * calc_num_nodes($np,$ppn);

					$reportdata{testsets}{$testident}{$currtestset}{$bench}{runtime} += ($1/60.0);

			}
		}
	}

	# if we are in the --report modes, we have more work to do
	if (defined $report) {
		# we want the start and end timestamps of the job
		my ($startraw, $endraw, $start, $end);
		if ($embedded_info_buf =~ /\nCbench\s+start\s+timestamp:\s+(\S+)\n/) {
			$startraw = $1;
			my $tmp = ParseDate($startraw);
			$start = UnixDate($tmp,"%s");
		}
		if ($embedded_info_buf =~ /\nCbench\s+end\s+timestamp:\s+(\S+)\n/) {
			$endraw = $1;
			my $tmp = ParseDate($endraw);
			$end = UnixDate($tmp,"%s");
		}

		# update the report data structure
		($start < $reportdata{firstjob_stamp}) and $reportdata{firstjob_stamp} = $start;
		($end > $reportdata{lastjob_stamp}) and $reportdata{lastjob_stamp} = $end;

		debug_print(3,"DEBUG:parse_output_file() timestamps: $startraw, $endraw, $start, $end, $reportdata{firstjob_stamp}, $reportdata{lastjob_stamp}");

	}

	(defined $DEBUG and $DEBUG > 2) and print
		"DEBUG:parse_output_file() Finished core buffer parsing...\n";

		# if the custom parse filters are enabled, then we need to look at both
		# the STDOUT, and STDERR files for matches to the custom parse filters
		if (defined $customparse and !$jobpassed) {
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
                        # FIXME: this probably should be printed for STDOUT files
						debug_print(1,"parse_output_file() Could not open $file for read ($!)\n");
						next;
					};

					# save references to this buffer
					push @files_to_grok_bufrefs, \@txtbuf;
					$files_sucked_in{$f} = \@txtbuf;
					$bufref_to_files{\@txtbuf} = $file;

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
				(defined $meta) and $fileid = "$metaset\/";
				(!defined $meta) and $fileid = "";
				$fileid .= "$fileid_path/$bufref_to_files{$bufref}";
				foreach my $filter (keys %parse_filters) {
					foreach my $l (@{$bufref}) {
						# skip the "whitespace" output generated by the 
						# 'stress' benchmark since it can generate a TON of
						# useless output
						($l =~ /\.\.\.\.\.\.\.\.\+$/) and next;
						($l =~ /\+\+\+\+\+.*\+\+\+\+$/) and next;

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
							
							print BOLD YELLOW "**PARSEMATCH**";
							print RESET "(";
							print GREEN, "$fileid";
							print RESET ")";
							print BOLD WHITE, "=> ";
                            print BOLD CYAN, "$temp";
							print RESET "\n";
							$filterhits{$filter}++;

							# add to aggregated custom parse hit data
							$customparse_hits{"$temp"}++;
						}
					}
				}
			}			

			# try to help with memory reclaimation
			@files_to_grok_bufrefs = undef;
		}
		
		# --diag and --customparse helpful output separating
		(!$jobpassed and ($diagnose or $customparse)) and print "-------------------------------------------------------------\n";

		# if job failure node diagnosis is enabled, we need to do more work
		if (defined $nodediag and 
			($filedata->{'STATUS'} ne 'PASSED' and 
			 $filedata->{'STATUS'} ne 'NOTICE' and 
			 $filedata->{'STATUS'} ne 'RUNNING')) {

        	debug_print(2,"DEBUG:parse_output_file() Starting nodediag work...(status=$filedata->{'STATUS'})\n");

			my $nodelistdata;

			# extract nodelist if it is there
			my $embedded_nodelist_raw;
			($embedded_nodelist_raw) = $embedded_info_buf =~ /\nCbench\s+\S*\s*nodelist:\s+(\S.*)\n/;
			debug_print(3,"DEBUG: embedded_nodelist_raw: $embedded_nodelist_raw\n");

			# if we found the embedded nodelist, phew, just sanity check it
			# and record the data
			if (length $embedded_nodelist_raw > 2) {
				debug_print(2,"DEBUG: found embedded nodelist for nodediag\n");

				my %nodelisthash;

				# so far we know about two styles of node lists, Torque/pbs and
				# slurm/pdsh
				if ($embedded_nodelist_raw =~ /\[.*\]/) {
					# slurm style
					my %tmphash;
					pdshlist_to_hash($embedded_nodelist_raw,\%tmphash);

					# so %tmphash isn't quite in the right structure so we need to
					# convert it
					my $cnt = 0;
					foreach my $k (keys %tmphash) {
							$nodelisthash{$cnt} = $k;
							$cnt++;
					}
				}
				else {
					# torque style
					my $cnt = 0;
					foreach my $k (split(/ /,$embedded_nodelist_raw)) {
						if ($k =~ /\S+/) {
							$nodelisthash{$cnt} = $k;
							$cnt++;
						}
					}
				}

				$nodelistdata = \%nodelisthash;	
			}
			else {
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
				$nodelistdata = ranktonode_parse_func(@files_to_grok_bufrefs);
			}
			
			foreach $k (keys %{$nodelistdata}) {
				if ($k eq 'NUMPROCS') {
					($nodelistdata->{$k} != $np) and debug_print(1,"WARNING:nodediagnose: ".
						"parsed rank-to-node map for only $nodelistdata->{$k} out of ".
						"$np processes\n");
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
	for $job (sort {$outhash{'0'}{$a} cmp $outhash{'0'}{$b} } (keys %{$outhash{'0'}}) ) {
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
			$output[$firstrow] .= sprintf("%4s ",$xaxis_ppn ? 'PPN' : 'NP');
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

sub results_to_stdout_grephappy {
	my $outhash = shift;
	
	# Now we can run through the 2D hash and generate the output to stdout
	my $firstrow = 0;
	my $lastrow = 0;
	my $column = 0;
	my $row = 1;
	my @output = ();

	# print header line
	push @output, "SERIES, NUMPROCS, MEAN, MAX, MIN, STDDEVIATION, SAMPLECOUNT, UNITS\n";

	for $job (sort {$outhash{'0'}{$a} cmp $outhash{'0'}{$b} } (keys %{$outhash{'0'}}) ) {
    	($job == 0) and next;

		for $np (sort {$a <=> $b} (keys %{$outhash}) ) {
    		($np == 0) and next;
			my $line = $outhash->{'0'}{$job} . ", $np, ";

			if (defined $outhash->{$np}{$job}) {
				$line .= sprintf("%25s ",$outhash->{$np}{$job});
			}
			#else {
				#$line .= sprintf("%25s ",'NODATA');
			#}
			push @output, "$line\n" unless (!defined $outhash->{$np}{$job});
    	}
	}
	print @output;
}

sub results_to_csv {
    my $outhash = shift;

    my $firstrow = 0;
    my $lastrow = 0;
    my $column = 0;
    my $row = 1;
    my %units = ();

    # find the possbile UNITS for these tests
    for my $thisjob (keys %{$outhash->{UNITS}}) {
        my $thisunit = $outhash->{UNITS}{$thisjob};
        ($thisunit ne "UNITS") and $units{$thisunit} = 1;
    }

    # create a separate CSV for all data with a certain unit type
    for my $unitval (keys %units) {

        my $unitstr = $unitval;
        $unitstr =~ s/\//_/g;   #remove '/' from the units so we can use it as a filename

        # construct a descriptive filename
        my $filename = "";
        $filename .= (defined $ident) ? "$ident-" : "test-";
        $filename .= (defined $match) ? "$match-" : "all-";
        $filename .= "$unitstr.csv";

        # create a separate CSV for each unit type
        open (CSV, ">$filename") or die "Could not open $filename for CSV: $!\n";

        # print header line
        print CSV "\"TEST\",\"NUMPROCS\",\"PPN\",\"$unitval\"\n";

        for $job (sort {$outhash{'0'}{$a} cmp $outhash{'0'}{$b} } (keys %{$outhash{'0'}}) ) {
            ($job == 0) and next;

            for $np (sort {$a <=> $b} (keys %{$outhash}) ) {
                ($np == 0) and next;

                # only results with the current unitval are allowed
                ($outhash->{UNITS}{$job} ne $unitval) and next;

                my $seriesval = $outhash->{'0'}{$job};
                # gather ppn and ident from series name
                $seriesval =~ /.*-(\d+)ppn-.*/ and my $ppnval = $1;
                $seriesval =~ /^(\w+)-.*/ and my $identval = $1;

                # strip out ident and ppn from series name
                $seriesval =~ s/^\w+-(.*)/$1/g;
                $seriesval =~ s/^(\w+-)\d+ppn-(.*)/$1$2/g;

                # start constructing the output line
                my $line = "\"$seriesval\",$np,$ppnval,";

                if (defined $outhash->{$np}{$job}) {
                    my $outval = $outhash->{$np}{$job};
                    $outval =~ s/\s+//g;
                    $outval =~ s/NODATA/NA/g; # R prefers "NA" to "NODATA" for non-values
                    $line .= $outval;
                    print CSV "$line\n";
                }
            }
        }
        close (CSV);
        print "CSV file $filename successfully created.\n";
    }
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
	my $units;
	my $units_tmp = '';
	foreach my $u (keys %{$outhash->{'UNITS'}}) {
		if (defined $outhash->{'UNITS'}{$u} and $outhash->{'UNITS'}{$u} !~ /UNITS/){
			$units_tmp = $outhash->{'UNITS'}{$u};
			last if ! defined $y2units;
			# favor units that aren't the user-specified y2-axis units
			if ($units_tmp ne $y2units) {
				$units = $units_tmp;
				last;
			}
		}
	}
	$units = $units_tmp if ! defined $units;

	if (defined $y2units) {
		if ($units eq $y2units) {
			print STDERR "\nWarning: y2units are the same as the default units.  Ignoring --y2units option...\n\n";
			$y2units = undef;
		} else {
			print CMD "set y2label \"$y2units\"\n";
			print CMD "set y2tics\n";
		}
	}

	if (defined $normalize) {
		($normalize =~ /numprocs/) and $units .= " / Num Processors";
		($normalize =~ /const/) and $units .= " / $normalize_const";
		($normalize =~ /minprocdata/) and $units = "Speedup";
		($paralleleff) and $units = "Parallel Efficiency";
		($scaledpeff) and $units = "Scaled Parallel Efficiency";
	}

	my $xstring = $xaxis_ppn ? "PPN" : "Number of Processors";
	(defined $xlabel) and $xstring = $xlabel;

	# continue building the gnuplot cmd file
	print CMD
		"set ylabel \"$units\"\n" .
		"set xlabel \"$xstring\"\n" .
		"set grid\n" .
		"set title \"Cbench $testset Test Set Output Summary\"\n";

	if (defined $keyinside) {
		print CMD "set key top left\n";
	}
	else {
		print CMD "set key outside below right\n";
	}

	if (defined $yrange) {
		my @tmp = split(',',$yrange);
		(defined $DEBUG) and print "DEBUG:results_to_gnuplot() yrange = @tmp\n";
		print CMD "set yrange \[$tmp[0]\:$tmp[1]\]\n";
	}

	if (defined $xrange) {
		my @tmp = split(',',$xrange);
		(defined $DEBUG) and print "DEBUG:results_to_gnuplot() xrange = @tmp\n";
		print CMD "set xrange \[$tmp[0]\:$tmp[1]\]\n";
	}

	print CMD "plot ";

	my %job_to_column = ();
	my $col = 0;
	for $job (sort {$a <=> $b} (keys %{$outhash->{'0'}}) ) {
    	print PLOT "$outhash->{'0'}{$job} ";
		# store column info so we can arbitrarily arrange our gnuplot key entries later
		$job_to_column{$job} = ++$col;
	}

	$numkeys = keys %{$outhash->{'0'}};
	my $keyindex = 1;
	for $job (sort {$outhash{'0'}{$a} cmp $outhash{'0'}{$b} or $a <=> $b} (keys %{$outhash{'0'}}) ) {
    	($job == 0) and next;
    	$keyindex++;

		$column = $job_to_column{$job};
    	my $my_units = defined $outhash->{UNITS}{$job} ? $outhash->{UNITS}{$job} : 'NA';
    	print CMD "\"$testset.dat\" using 1:$column title \"$outhash->{'0'}{$job} ($my_units)\" with lp";
		(defined $linewidth) and print CMD " lw $linewidth";
    	(defined $y2units and $y2units eq $my_units) and print CMD " axes x1y2";
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

	if (defined @addplot) {
		my $fidx = 1;
		foreach (@addplot) {
			my @tmp = split(',',$_);
			my @tmp2 = split('=',$tmp[1]);
			my $title = $tmp2[1];
			print CMD "f$fidx(x) = $tmp[0] \n";
			print CMD "replot f$fidx(x) title \"$title\"\n";
			$fidx++;
		}
	}

	print CMD
		"set term postscript color\n" .
		"set output \"$testset.ps\"\n" .
		"replot\n" .
		"set term png\n" .
		"set output \"$testset.png\"\n" .
		"replot\n" ;
	
	# record our nice invocation data stuff
	print PLOT @invocation_data;
	close(PLOT);

	my $xrm = 
		"-xrm \'gnuplot*line1Color: red\' ".
		"-xrm \'gnuplot*line2Color: green\' ".
		"-xrm \'gnuplot*line3Color: DarkSlateGrey\' ".
		"-xrm \'gnuplot*line4Color: magenta\' ".
		"-xrm \'gnuplot*line5Color: cyan\' ".
		"-xrm \'gnuplot*line6Color: blue\' ".
		"-xrm \'gnuplot*line7Color: orange\' ".
		"-xrm \'gnuplot*line8Color: coral\'";

	my $cmd = "gnuplot -persist -raise $xrm $testset.cmd";

	# record the command we executed in the gnuplot command file for posterity
	print CMD "\n\# gnuplot command line\n\# $cmd\n";
	print CMD @invocation_data;
	close(CMD);

	(defined $DEBUG) and print "DEBUG:results_to_gnuplot(): $cmd\n";

	exec "$cmd";

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
				die "Do we need this block anymore?";
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
		elsif ($outhash->{'0'}{$job} =~ /NP|PPN/) {
			next;
		}
		elsif (defined $metricstr and ($outhash->{'0'}{$job} !~ /$matchstr/)) {
			die "Do we need this block anymore?";
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

		my $xstring = $xaxis_ppn ? "PPN" : "Number of Processors";

		print CMD
			"set ylabel \"%\"\n" .
			"set yrange [0:100]\n" .
			#"set y2label \"Number of Jobs\"\n" .
			#"set y2tics\n" .
			"set sample 10000\n" .
			"set ytics nomirror\n" .
			"set xlabel \"$xstring\"\n" .
			"set key top right\n".
			"set title \"Cbench $testset Test Set Job Success Summary\"\n".
			"plot ";

	}
	
	print color('bold yellow');
	printf "%4s ",$xaxis_ppn ? 'PPN' : 'NP';
	print color('bold magenta');
	printf "%15s","Job Success %";
	print RESET "\n";
	(defined $gnuplot) and printf PLOT "%s %s %s %s\n",$xaxis_ppn ? 'PPN' : 'NP',"Job_Success_%","Successful_Job_Count",
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
	printf "%4s  %s\n",$xaxis_ppn ? 'PPN' : 'NP',"Failure Diagnoses";
	for $np (sort {$a <=> $b} (keys %{$hash}) ) {
		printf "%4d   ",$np;
		foreach $k (sort {$a <=> $b} (keys %{$hash->{$np}}) ) {
			printf "%s=>%d, ",$k,$hash->{$np}{$k};
		}
		print "\n";
	}
}


sub dump_customparse_hits {
	my $hash = shift;

	print GREEN "\nCustomparse Matches Summary:\n----------------------------\n";
	for my $hit (sort {$a <=> $b} (keys %{$hash}) ) {
		print "\'$hit\' => $hash->{$hit} matches\n"; 
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

	my $numbins = 10;
	print "\nFailure count frequency distribution ($numbins bins):\n";
	my %f = $statvar->frequency_distribution($numbins);
	for (sort {$b <=> $a} keys %f) {
	  printf "  %0.2f failures: count = %0.1f\n",$_,$f{$_};
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

    $fstats = stat($file);

	if (defined $fstats and $fstats->size > 1024*1024*1024) {
		# Do we really want to open gigabyte sized output files?
		# I ran across an error case where jobs created 20-300 GB sized
		# files and we really don't want to mess with those.
		my $gb = int $fstats->size / (1024*1024);
		warning_print("$file is too big to sanely parse at $gb MB\n");
		$$txtbuf[0] = "CBENCH PARSE ERROR: FILE TOO BIG TO PARSE: $gb MB\n";
		return 0;
	}
	elsif (defined $fstats and $fstats->size > 1024*1024*50) {
		# If the file is "big enough", this can cause Perl + Glibc memory mgmt
		# issues (some Glibc versions seem to hang in malloc...). So we'll apply
		# some heuristics to trim file sizes down in memory based on known output
		# file bloat.
		(defined $DEBUG and $DEBUG > 1) and print
			"DEBUG:open_and_slurp() BIG FILE of ".$fstats->size." bytes\n";
		open(FILE, "$file") or return 0;
		my $i = 0;
		while (<FILE>) {
			# skip the "whitespace" output generated by the 
			# 'stress' benchmark since it can generate a TON of
			# useless output
			($_ =~ /\.\.\.\.\.\.\.\.\+$/) and next;
			($_ =~ /\+\+\+\+\+.*\+\+\+\+$/) and next;
			$$txtbuf[$i++] = $_;
		};
		close(FILE);
	}
	else {
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


sub results_to_dplot {
	open (PLOT, ">dplot-in.dat");
	foreach my $idx (sort {$a <=> $b} keys(%dplotdata)) {
		my $line = $dplotdata{$idx}{'dat'} . "\t" . $dplotdata{$idx}{'tag'};
		print PLOT "$line\n";
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
};

sub normalize_value {
	my $val = shift;
	my $np = shift;  # optional value

	if ($normalize =~ /const/) {
		return ($val / $normalize_const);
	}
	elsif (defined $scaledpeff and $normalize =~ /minprocdata/) {
		return ($val / ($np*$normalize_dyn));
	}
	elsif ($normalize =~ /minprocdata/) {
		return ($val / $normalize_dyn);
	}
	elsif ($normalize =~ /numprocs/) {
		return ($val / $np);
	}
}


sub report_to_stdout {
	
	print GREEN "\nDetailed Workload Report:\n----------------------------------\n";

	# job workload summary
	foreach my $ident (sort keys %{$reportdata{testsets}}) {
		print "\n";
		print BOLD CYAN "Job Summary for Test Identifier \'$ident\'\n";
		foreach my $tset (sort keys %{$reportdata{testsets}{$ident}}) {
			print BOLD YELLOW uc($tset)." testset\n";
			printf "  %20s %6s %6s %6s %15s\n",'Test   ','Passed','Failed','Notice','Runtime(minutes)';
			printf "  %20s %6s %6s %6s %15s\n",'====================','======',
				'======','======','===============',;
			foreach my $bench (sort keys %{$reportdata{testsets}{$ident}{$tset}}) {
				printf "  ".color('bold white')."%20s ".color('bold green')."%6s ".color('bold red')."%6s ".color('bold magenta')."%6s ".color('reset')."%13.2f\n",$bench,
					$reportdata{testsets}{$ident}{$tset}{$bench}{passed},
					$reportdata{testsets}{$ident}{$tset}{$bench}{failed},
					$reportdata{testsets}{$ident}{$tset}{$bench}{notice},
					$reportdata{testsets}{$ident}{$tset}{$bench}{runtime};
			}
		}
	}

	print "\n\n";
	# print out time info for for all the runs we found
	my $tmp = UnixDate("epoch $reportdata{firstjob_stamp}","%Y-%m-%d %H:%M");
	printf color('bold white')."First Job Started:".color('reset')." %s\n",$tmp;
	my $tmp = UnixDate("epoch $reportdata{lastjob_stamp}","%Y-%m-%d %H:%M");
	printf color('bold white')."Last Job Finished:".color('reset')." %s\n",$tmp;
	my $elapsed_secs = $reportdata{lastjob_stamp} - $reportdata{firstjob_stamp};
	printf color('bold white')."Total Elapsed Time:".color('reset')." %.2f hours (%.2f minutes or %0.2f days)\n",
		$elapsed_secs/(60*60),$elapsed_secs/60,$elapsed_secs/(60*60*24);
	
	printf color('bold white')."Accumulated Wallclock Time:".color('reset')." %.2f hours (%.2f minutes or %0.2f days)\n",
		$reportdata{accum_wallclock_minutes}/(60*60),$reportdata{accum_wallclock_minutes}/60,
		$reportdata{accum_wallclock_minutes}/(60*60*24);

	printf color('bold white')."Accumulated Node-hour Time:".color('reset')." %.2f node-hours\n",
		$reportdata{accum_nodehour_minutes}/(60*60);


}



sub usage {
    print   "USAGE: $0 \n";
    print   "Cbench script to analyze job output in the $testset test set\n".
            "   --testset <name> Override the name of the testset (optional).\n".
            "   --ident <name>   Test identifier to analyze (optional).\n".
			"                    Can also have the form of a list:\n".
			"                      --ident test1,test2,test3\n".
			"   --collapse <name> Collapse data from multiple test identifiers\n".
			"                     into a single set of data with the specified\n".
			"                     name\n".
			"   --meandata       For any given data point with multiple data values, i.e.\n".
			"                    there were multiple runs that generated that data point,\n".
			"                    calculate the MEAN (arithmetic average) of the data points.\n".
			"                    NOTE: this is the default behavior of the output parser\n".
			"                    and/or statistics\n".
			"   --maxdata        For any given data point with multiple data values, i.e.\n".
			"                    there were multiple runs that generated that data point,\n".
			"                    calculate the MAXimum of the data points.\n".
			"   --mindata        For any given data point with multiple data values, i.e.\n".
			"                    there were multiple runs that generated that data point,\n".
			"                    calculate the MINimum of the data points.\n".
            "   --match          This limits the processing of job outputs to\n" .
            "                    jobs with a jobname that matches the specified\n" .
            "                    regex string. For example,\n" .
            "                      --match 2ppn\n" .
            "                    would only process 2 ppn tests\n" .
            "   --exclude        This is just like the --match parameter except\n" .
            "                    that jobs matching are NOT processed\n" .
			"   --metric         A regex to include only certain metrics\n".
            "   --gnuplot        Generate a Gnuplot and display it\n".
			"   --logy           Use a logarithmic y axis\n".
			"   --logx           Use a logarithmic x axis\n".
			"   --linewidth <num> Tell Gnuplot to use the specified linewidth\n".
			"   --yrange n1,n2   Tell gnuplot to use the range [n1:n2] for the y-axis\n".
			"   --xrange n1,n2   Tell gnuplot to use the range [n1:n2] for the x-axis\n".
			"   --addplot function,title=<string>  Add a plot line or lines to the gnuplot\n".
			"                                      graph that is generated by the --gnuplot\n".
			"                                      option.  For example:\n".
			"                        --addplot \'0.80,title=80% mark\'\n".
			"                        --addplot \'3.6*4*0.8*x,title=80% efficiency\'\n".
			"                                      There can be multiple --addplot options\n".
			"                                      used on the command line\n".
			"   --xlabel <string> Tell gnuplot to use the specified string as the x-axis\n".
			"                     label\n".
			"   --keyinside       Tell gnuplot to put the legend or key inside the plot\n".
			"   --dplot <num>,dplotarams  Use the STAB dplot utility to plot the\n".
			"                    the statistical distribution of data for <num> \n".
			"                    processors. Dplotting can only be used for a single\n".
			"                    processor count and a single metric.  This usually\n".
			"                    means that you will need to use the --metric parameter\n".
			"                    to include just the data you want to look at. For example:\n".
			"                        --dplot 32 --metric gflops\n".
			"                    would request a dplot for data from 32 processors and\n".
			"                    the gflops metric. You can optionally pass arguments to\n".
			"                    dplot as well. For example:\n".
			"                        --dplot 32,-bi,-std\n".
			"                    would pass the -bi and -std command line parameters to\n".
			"                    dplot\n".
			"   --normalize <option>   Normalize data in various ways:\n".
			"               numprocs     normalize by the number of processors\n". 
			"               const=NUM    normalize by the constant value NUM\n".
			"               minprocdata  normalize each data series by the data found\n".
			"                            by the parser at the smallest process count for\n".
			"                            that data series. For example, if there is a \n".
			"                            data point at 1 process for a data series, that\n".
			"                            data point is used to normalize all the data\n".
			"                            parsed for the series.\n".
			"   --speedup        Normalize the data to generate speedup information for\n".
			"                    each data series.  This is equivalent to the --normalize\n".
			"                    \'minprocdata\' option\n".
			"   --paralleleff    Normalize the data to show parallel efficiency. This is\n".
			"                    equivalent to the --normalize \'numprocs\' option\n".
			"   --scaledparalleleff  Massage the data to show scaled parallel effiency\n".
			"   --nodata         Don't print out the data tables, just errors\n".
			"   --filestats      Print out output file info from stat()\n".
            "   --diagnose       Include more data concerning errors and\n".
            "                    failures in jobs\n".
			"   --customparse    Run the raw output files through the Cbench custom parse\n".
			"                    filters which enables more in depth error diagnoses\n".
			"   --statsmode      Output the tabular parsed data in a more statistically\n".
			"                    informative mode\n".
			"   --successstats   Generate an analysis of the percentage of jobs\n".
			"                    at each job size (i.e. processor count) that succeed\n".
			"   --nodediagnose   Analyze failed jobs and generate a list of nodes\n".
			"                    and the number of job failurs on each node.\n".
			"                    NOTE: this requires that rank-to-node information, i.e.\n".
			"                          MPI rank-to-node mapping information, is present\n".
			"                          in the job launch output.\n".
			"   --errorsonly     Only printout the error information\n".
			"                    e.g. --custom --diagnose --nodata\n" .
			"   --minprocs <num> Only parse jobs who's number of processors is\n" .
			"                    greater than or equal to this parameter\n".
			"   --maxprocs <num> Only parse jobs who's number of processors is\n" .
			"                    less than or equal to this parameter\n".
			"   --procs <num>    Only parse jobs who's number of processors is\n".
			"                    equal to the specified parameter\n".
			"   --minnodes <num>\n".
			"   --maxnodes <num>\n".
			"   --nodes <num>    Same as --maxprocs, --minprocs, --procs but with number\n".
			"                    of nodes\n".
			"   --listfound      Print out a list of the key stuff that the output parse\n".
			"                    work found like test identifiers, data metrics, etc.\n".
			"   --grepable       Output gathered test data in a grep friendly format\n".
			"   --meta           Tell output parse to work in meta testset mode where\n".
			"                    all testsets are parsed at once\n".
			"   --y2units <string>  Set the right-hand y-axis units, and make any\n".
			"                       metrics with these units plot against it instead\n".
			"                       of the default left-hand y-axis.\n".
			"   --usecwd          Override the path to the nodehwtest that is determined\n".
			"                     and use the current working directory\n".
			"   --numcolumns <num>  Number of columns used for text output of parsed data.\n".
			"                       The default is 2.\n".
			"   --xaxis_ppn          Put PPN on the x-axis and organize the data series\n".
			"                        with a number of process centric view\n".
			"   --xaxis_ppn_nodeview Put PPN on the x-axis but organize the data series\n".
			"                        with a node centric view as opposed to a number of \n".
			"                        processes centric view\n".
			"   --follow_symlinks  Tell output parser to follow directories that are\n".
			"                      symbolic links\n".
			"   --walltimedata     Look for elapsed walltime data in the stdout stream\n".
			"                      from jobs (that is generated by the Cbench scripts), and\n".
			"                      if found, add walltime as a datapoint for each job\n".
			"   --showpassed       In a similar fashion to the --diagnose output, show jobs\n".
			"                      that passed explicitly\n".
			"   --shownotices      When the --diagnose flag is used, also print out info\n".
			"                      about jobs that returned a Cbench NOTICE status. The NOTICE status\n".
			"                      means the job neither passed nor failed but encountered a known\n".
			"                      condition that it did not like.  An example of this is an Mpi\n".
			"                      test that will not run on one process\n".
			"   --jobid <num>      Tells the output parser to only look for output from the\n".
			"                      specific job identified by the specified number\n".
			"   --gazebo           Outputs results of the parse in a format that is friendly\n".
			"                      to being run under the Gazebo testing system\n".
			"   --report           Generate a detailed workload report for all parsed jobs\n".
                        "   --csv              Create a CSV file for each type of unit found in the output\n".
            "   --debug <level>  turn on debugging at the specified level\n";
}
