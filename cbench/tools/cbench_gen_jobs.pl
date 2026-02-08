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

# Generic Cbench *_gen_jobs.pl utility template script

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

detect_color_support();

use Getopt::Long;
use Data::Dumper;
use Term::ANSIColor qw(:constants color colored);

# pre init some vars before command line parsing
my $xhplbin = 'xhpl';
my $hpccbin = 'hpcc';
my $testset;
our $use_single_template_for_testset = 0;

GetOptions(
	'ident=s' => \$ident,
	'binident=s' => \$BINIDENT,
	'binname=s' => \$binname,
	'xhplbin=s' => \$xhplbin,
	'hpccbin=s' => \$hpccbin,
        'maxprocs=i' => \$maxprocs_cmdline,
        'minprocs=i' => \$minprocs_cmdline,
        'procs=i' => \$procs_cmdline,
	'minnodes=i' => \$minnodes,
	'maxnodes=i' => \$maxnodes,
	'nodes=i' => \$nodes,
        'runsizes=s' => \$runsizes,
	'testdir|scratchdir=s' => \$testdir,
	'jobcbenchtest=s' => \$JOBCBENCHTEST,
	'testset=s' => \$testset,
	'preamble=s' => \$preamble,
	'match=s' => \$match,
	'exclude=s' => \$exclude,
	'debug:i' => \$DEBUG,
	'help' => \$help,
	'redundant' => \$redundant,
	'unevenspan' => \$unevenspan,
	'joblaunch_extraargs=s' => \$joblaunchargs,
	'memory_util_factors|mem_factors=s' => \$new_memory_util_factors,
	'threads|ompthreads|ompnumthreads=i' => \$OMPNUMTHREADS,
        'scaled_only' => \$scaled_only,
        'scalefactor=i' => \$scale_factor,
	'gazebo' => \$gazebo,
	'gazebohome|gzhome|gazhome=s' => \$gazebo_home,
	'gazeboconfig|gzhome|gazconfig=s' => \$gazebo_config, 
	'gazebodebug|gzdebug|gazdebug' => \$gazebo_debug, 
	'walltimemethod|walltime_method=i' => \$walltime_method,
	'defaultwalltime|defwalltime=s' => \$default_walltime,
        'edgefactor=i' => \$edge_factor,
);

if (defined $help) {
	usage();
	exit;
}

if (!defined $testset) {
	$testset = find_testset_identity($0);
}

if (defined $new_memory_util_factors) {
	@memory_util_factors = split(',',$new_memory_util_factors);
	debug_print(1,"DEBUG: overriding memory_util_factors array from command line ".
		"with @memory_util_factors");
}

if (defined $joblaunchargs) {
	# override the cluster.def setting
	debug_print(3,
		"Old joblaunch_extraargs = \"$joblaunch_extraargs\", New joblaunch_extraargs = \"$joblaunchargs\"");
	$joblaunch_extraargs = $joblaunchargs;
}


# Gazebo mode stuff
(defined $gazebo and (!defined $gazebo_home or !defined $gazebo_config)) and
		die "--gazebo requires --gazebohome and --gazeboconfig parameters";
# Gazebo submit config file we'll append to
my $submitconfig_file = "$gazebo_home/submit_configs/$gazebo_config";
# this variable is where we'll incrementally build the Gazebo submit config file
my $submitconfig = "";

# locate the cbench testing tree we'll use
$cbenchtest = $bench_test = get_bench_test();
$testset_path = "$bench_test/$testset";
$DEBUG and print "DEBUG: $bench_test $testset_path\n";

(!defined $ident) and $ident = $cluster_name . "1";
if (!defined $testdir) {
	$testdir = "$testset_path/$ident/SCRATCH";
	#info_print("$0: --testdir not specified, defaulting to $testdir\n");
	mkdir "$testdir",0750;
}


# custom generate processing control hash
%custom_gen_hash = (
	'benchmark' => {
		'npb' => {
			'init' => 'npb_gen_init',
		},
		'xhpl' => {
			'init' => 'xhpl_gen_init',
			'innerloop' => 'xhpl_gen_innerloop',
		},
        'xhpl2' => {
            'init' => 'xhpl_gen_init',      # uses same custom functions as xhpl
            'innerloop' => 'xhpl_gen_innerloop', 
        },
        'xhplintel' => {
            'init' => 'xhpl_gen_init',      # uses same custom functions as xhpl
            'innerloop' => 'xhpl_gen_innerloop', 
        },
		'hpcc' => {
			'init' => 'hpcc_gen_init',
			'innerloop' => 'hpcc_gen_innerloop',
		},
		'epetratest' => {
			'innerloop' => 'trilinos_epetratest_gen_innerloop',
		},
	},
	'testset' => {
		'npb' => {
			'joblist' => 'npb_gen_joblist',
			'innerloop' => 'npb_gen_innerloop',
		},
        'lammps' => {
            'innerloop' => 'lammps_gen_innerloop',
            'joblist' => 'lammps_gen_joblist',
        },
        'amg' => {
            'innerloop' => 'amg_gen_innerloop',
            'joblist' => 'amg_gen_joblist',
        },
        'irs' => {
            'runsizes' => 'irs_gen_runsizes',
        },
        'sweep3d' => {
            'init' => 'sweep3d_gen_init',
            'joblist' => 'sweep3d_gen_joblist',
            'innerloop' => 'sweep3d_gen_innerloop',
        },
        'phdmesh' => {
            'runsizes' => 'phdmesh_gen_runsizes',
            'innerloop' => 'phdmesh_gen_innerloop',
        },
        'sppm' => {
            'init' => 'sppm_gen_init',
            'innerloop' => 'sppm_gen_innerloop',
        },
        'graph500' => {
            'innerloop' => 'graph500_gen_innerloop',
        },
	},
);

# load any gen_jobs modules
my %genjobs_modules;
load_genjobs_modules(\%genjobs_modules);

# now we need to add hook the gen_jobs modules into the %custom_gen_hash
# structure
foreach my $mod (keys %genjobs_modules) {
	# first query what we might need to put into the testset specific overload
	my %tmp = $genjobs_modules{$mod}->testset_hash();
	my $keys = keys %tmp;
	#print Dumper (%tmp);
	if ($keys > 0) {
		%{$custom_gen_hash{testset}{$mod}} = %tmp;
	}

	# second query what we might need to put into the benchmark specific overload
	my %tmp = $genjobs_modules{$mod}->benchmark_hash();
	my $keys = keys %tmp;
	#print Dumper (%tmp);
	if ($keys > 0) {
		%{$custom_gen_hash{benchmark}{$mod}} = %tmp;
	}
}
(defined $DEBUG and ($DEBUG > 3)) and print Dumper (%custom_gen_hash);

# find and read in the job templates for the testset
my %templates = ();
build_job_templates($testset,\%templates);
# delete the Cbench internal combobatch "job" since we won't use
# it in this context
delete $templates{combobatch};

# this hash will hold any job template specific walltime requirements
our %specialwalltimes = ();

# process any Cbench directives inside the job templates
foreach my $k (keys %templates) {
	# job templates that have special walltime requirements
	if ($templates{$k}{batch} =~ /#\s+Cbench_walltime:\s+(\S+)/) {
		debug_print(2,"DEBUG: job template $k requires walltime $1");
		$specialwalltimes{$k} = $1;
	}

	# job templates that require a certain gen_jobs module 
	if ($templates{$k}{batch} =~ /#\s+Cbench_require: (\S+)::(\S+)/) {
		debug_print(2,"DEBUG: job template $k requires $1::$2");
		if (! exists $genjobs_modules{$2}) {
			warning_print("Will not generate for job template \'$k\': required module $1::$2 not found\n");
			delete $templates{$k};
		}
	}
}
#print Dumper (%templates);
#print Dumper (%specialwalltimes);

# by default the list of jobs is the list of templates found
our @job_list = keys %templates;
debug_print(2,"DEBUG: default job_list= @job_list");
# if we have no jobs to generate, say so and exit
if (scalar keys %templates <= 0) {
	warning_print("No jobs to generate...exiting");
	exit 1;
}

# run initialization subroutines for an custom generation code
custom_gen_init($testset);

# This is the core of the set of loops that generate all the
# job files (batch and interactive) for all the permutations of
# number of processors, ppn, and specific test.
#
# The method cbench uses is to build a template for all the tests
# and then do keyword replacment in the template to generate the
# actual job files.

# make sure the directory is there with the proper test identification
(! -d "$testset_path\/$ident") and mkdir "$testset_path\/$ident",0750;

# if the user passed in a set of runsizes on the command line, convert
# to an array and replace the default @run_sizes array from cbench.pl
(defined $runsizes) and use_custom_runsizes($runsizes);

# at this point we have the array of runsizes, i.e. mpi process counts,
# that the user wants to generate for. some tests/benchmarks only support
# specific numbers of mpi processes (e.g. only powers of two).
# we'll give any benchmark/testset the chance to filter the list of
# runsizes here
@run_sizes = custom_gen_runsizes(\@run_sizes);

# for every mpi process count, runsize, we want to determine the walltime
# that will be associated with that job. the simple way to do this is
# to assign every job the same $default_walltime from cluster.def. A
# downside of this approach is that schedulers have a harder time making
# scheduling decisions when there is no walltime delta between a bunch
# of jobs.
my %walltimes = ();
(!defined $walltime_method) and $walltime_method = 0;
my $temptime = walltime_to_seconds("$default_walltime");
foreach $numprocs (sort {$a <=> $b} @run_sizes) {
	if ($walltime_method == 0) {
		$walltimes{$numprocs} = $default_walltime;
	}
	elsif ($walltime_method == 1) {
		$walltimes{$numprocs} = seconds_to_walltime($temptime);
		$temptime += $walltime_steptime * 60;
	}
	#print "np $numprocs  $temptime  $walltimes{$numprocs}\n";
}

#
# HERE BEGINS the main job generation loop
#
my $job_count = 0;

# outer loop iterates over the various ppn cases as defined in
# the max_ppn_procs hash in cluster.def
foreach $ppn (sort {$a <=> $b} keys %max_ppn_procs) {
	# prevent oversubscription of processes to processors
	($ppn > $procs_per_node) and next;


	# inner loop iterates of the various run sizes (i.e. number of
	# processors in a parallel job) in the @run_sizes array as
	# defined in cbench.pl
	foreach $numprocs (sort {$a <=> $b} @run_sizes) {

		# Gazebo mode special cases
		# for jobs > 1 node in size, we only want to generate jobs for the 
		# $procs_per_node ppn case.
		# for jobs == 1 node in size, generate jobs for all the ppn cases
		if (defined $gazebo) {
			($ppn != $procs_per_node) and next;
			$redundant = 1;
		}

		# check and make sure we don't generate jobs over the max
		# number of procs for the cluster or for the current
		# ppn (as specified in cluster.def)
		if ($numprocs > $max_ppn_procs{$ppn}) {
			debug_print(3,"DEBUG: $numprocs procs exceeds max_ppn_procs at $ppn\ppn in cluster.def");
			next;
		}
		if ($numprocs > $max_procs) {
			debug_print(3,"DEBUG: $numprocs procs exceeds max_procs in cluster.def");
			next;
		}

		# honor any max/min processor count arguments from the command line
		if ((defined $maxprocs_cmdline) and ($numprocs > $maxprocs_cmdline)) {
			debug_print(3,"DEBUG: $numprocs procs exceeds --maxprocs $maxprocs_cmdline");
			next;
		}
		if ((defined $minprocs_cmdline) and ($numprocs < $minprocs_cmdline)) {
			debug_print(3,"DEBUG: $numprocs procs below --minprocs $minprocs_cmdline");
			next;
		}
		if ((defined $procs_cmdline) and ($numprocs != $procs_cmdline)) {
			debug_print(3,"DEBUG: $numprocs procs != --procs $procs_cmdline");
			next;
		}

		my $numnodes = calc_num_nodes($numprocs,$ppn);
		# honor any max/min node count arguments from the command line
		if ((defined $maxnodes) and ($numnodes > $maxnodes)) {
			debug_print(3,"DEBUG: $numnodes nodes exceeds --maxnodes $maxnodes");
			next;
		}
		if ((defined $minnodes) and ($numnodes < $minnodes)) {
			debug_print(3,"DEBUG: $numnodes nodes below --minnodes $minnodes");
			next;
		}
		if ((defined $nodes) and ($numnodes != $nodes)) {
			debug_print(3,"DEBUG: $numnodes nodes != --nodes $nodes");
			next;
		}

		# iterate over the job templates we need to process
		foreach $job (custom_gen_joblist($ppn,$numprocs)) {
			# most job templates correspond directly with the name of the job
			my $job_template = $job;
			# NPB is slightly different
			if ($use_single_template_for_testset) {
				$job_template = $testset;
			}

			# figure out how many nodes we need based on the number of
			# procs and ppn
			$numnodes = calc_num_nodes($numprocs,$ppn);

			# determine the walltime to be used for this specific job
			my $thiswalltime = $walltimes{$numprocs};
			if (exists $specialwalltimes{$job}) {
				$thiswalltime = $specialwalltimes{$job};
				debug_print(3,"DEBUG: Found job specific walltime $specialwalltimes{$job} for $job");
			}

			# this check should be superflous but do it anyway
			($numnodes > $max_nodes) and next;

			if (!$redundant) {
				# don't generate jobs for redundant 1-node cases, like the following:
				# mpiexec -npernode 8 -np 2 ...
				# mpiexec -npernode 4 -np 2 ...
				($ppn > $numprocs) and next;
			}
			if ($numprocs % $ppn and !$unevenspan) {
				debug_print(2,"DEBUG: Found $numprocs not really modulo by $ppn for $job");
				next;
			}

			# build the full job name
			$jobname = "$job-".$ppn."ppn-$numprocs";

			# if --match param was used, only process jobs matching the regex
			if (defined $match) {
				my $matchstr = "$match";
				next unless ($jobname =~ /$matchstr/);
			}
			# if --exclude param was used, only process files NOT matching
			if (defined $exclude) {
				$matchstr = "$exclude";
				next unless ($jobname !~ /$matchstr/);
			}

			debug_print(1,"DEBUG: Generating for $jobname\n");

			# Check for Gazebo mode which takes advantage of the gen_jobs smarts
			# but does things completely differently
			if (defined $gazebo) {
				# gazebo doesn't deal with odd process counts so far
				next unless power_of_two($numprocs);

				# gazebo name for the cbench job
				my $gazname =  uc($testset)."-$job";
				# add a line to the Gazebo submit config file
				$submitconfig .= "$gazname $numprocs 50 - $thiswalltime *\n";

				# build up the test_exec directory for the job
				(! -d "$gazebo_home\/test_exec\/$gazname") and mkdir "$gazebo_home\/test_exec\/$gazname",0750;
				# symlink the cbench gazebo wrapper
				(! -l "$gazebo_home\/test_exec\/$gazname/run") and 
					system("/bin/ln -s $bench_test/tools/cbench_gazebo_runjob.sh $gazebo_home\/test_exec\/$gazname/run");

				# build the test_exec/$gazname/config file contents
				my $testconfig = "
\$test_config{'AUTHOR'} = \"Cbench\";
\$test_config{'VERSION'} = \"$cbench_version\";
\$test_config{'COMPILER'} = \"\";
\$test_config{'MPILIB'} = \"\";
\$test_config{'JOBSIZE'} = \"\";
\$test_config{'NPES'} = \"2\";
\$test_config{'TIMELIMIT'} = \"$thiswalltime\";
\$test_config{'TARGET_WD'} = \"\";
\$test_config{'TEST_PARAMS'} = \"\";
\$test_config{'CMD'} = \"run\";
\@legend = ( );
# The following are non-standard vars that the cbench wrapper uses to figure
# out what to do. We rely on the property of Gazebo that these vars will end
# up in the environment of the running job, and thus we can see them.
\$test_config{'CBENCHTEST'} = \"$bench_test\";
\$test_config{'CBENCH_JOB'} = \"$job\";
\$test_config{'CBENCH_TESTSET'} = \"$testset\";
\$test_config{'CBENCH_TESTIDENT'} = \"$ident\";
";

				# possibly enable Gazebo debug mode
				(defined $gazebo_debug) and $testconfig .= "\$test_config{'CBENCH_DEBUG'} = \"2\"";

				# write out the config file
				open (EXECCONFIG,">$gazebo_home\/test_exec\/$gazname/config") or die
					"Could not write $gazebo_home\/test_exec\/$gazname/config ($!)";
				print EXECCONFIG $testconfig;
				close(EXECCONFIG);

			}

			# All Cbench jobs are isolated within their own named directory.
			# These dirs are withing the test ident directory and are
			# named for the jobname. This just helps keep job stuff orderly
			# and an added benefit is being able to tuck away extra files as
			# we see fit in the job directories.
			(! -d "$testset_path\/$ident\/$jobname") and mkdir "$testset_path\/$ident\/$jobname",0750;

			# iterate over batch and interactive job generation
			foreach $runtype (('batch','interactive')) {
				my $captype = uc $runtype;

				# prime the output buffers with the appopriate template
				$outbuf = $templates{$job_template}{$runtype};

				# here we do all the standard substitutions
				$outbuf = std_substitute($outbuf,$numprocs,$ppn,$numnodes,
							$runtype,$thiswalltime,$testset,$jobname,$ident,$job);

				# other substitutions
				$outbuf =~ s/TESTDIR_HERE/$testdir/gs;
				$outbuf =~ s/SCRATCHDIR_HERE/$testdir/gs;
				$outbuf =~ s/XHPL_BIN_HERE/$xhplbin/gs;
				$outbuf =~ s/XHPL2_BIN_HERE/xhpl2/gs;
				$outbuf =~ s/XHPLINTEL_BIN_HERE/xhplintel/gs;
				$outbuf =~ s/HPCC_BIN_HERE/$hpccbin/gs;

				# preamble 
				if (defined $preamble) {
					$outbuf =~ s/#PREAMBLE_HERE/$preamble/gs;
					debug_print(9,"DEBUG: Writing $preamble for $jobname\n");
				}

				# run any custom generation inner loop work, passing a reference to $outbuf so custom
				# innerloops can modify it
				my $ret = custom_gen_innerloop(\$outbuf,$numprocs,$ppn,$numnodes,
							$runtype,$thiswalltime,$testset,$jobname,$ident,$job);
				if ($ret) {
					# custom_gen_innerloop returned some sort of error
					# skip the remainder of this loop
					next;
				}

				# build the filename
				($runtype eq 'batch') and $outfile = "$jobname\.$batch_extension";
				($runtype eq 'interactive') and $outfile = "$jobname\.sh";

				debug_print(2,"DEBUG: Writing $captype script for $jobname\n");

				# write out the generated job file
				open (OUT,">$testset_path\/$ident\/$jobname\/$outfile") or die
					"Could not write $testset_path\/$ident\/$jobname\/$outfile ($!)";
				print OUT $outbuf;
				close(OUT);

				($runtype eq 'interactive') and
					`/bin/chmod gu+x $testset_path\/$ident\/$jobname\/$outfile`;

			}
			
			# update stat
			$job_count++;
		}
	}
}

# Gazebo mode stuff
if (defined $gazebo) {
	open (SUBMITCONFIG,">>$submitconfig_file") or die
		"Could not write $submitconfig_file ($!)";
	print SUBMITCONFIG $submitconfig;
	#print $submitconfig;
	close(SUBMITCONFIG);
}

print "Generated $job_count jobs in the ".uc($testset)." testset (--ident \'$ident\').\n";

######################################################################
######################################################################
# The following subroutines implement the "dynamic" subroutine call,
# structure that is loosely termed "custom gen" or custom generation.
# The dynamic calls allow for testsets and/or specific benchmarks to
# customize the job generation process, directed by the %custom_gen_hash
# data structure, by calling their own custom subroutines at certain
# defined points in the generation process.  Currently there are 
# four defined points of customization:
#   * building the array of runsizes (i.e. list of number of mpi
#     processes to build jobs for, e.g. 2,4,16...)
#   * building the array of "jobs" to generate job files for where
#     a job is the unique combination of a testname-ppncountstring-numberofprocs
#   * initialization outside of the actual job file generation loop
#   * inside the innermost loop of job generation
#

sub custom_gen_runsizes {
	my $sizes = shift;

	debug_print(3,"DEBUG: entering custom_gen_runsizes($sizes)\n");

	# run any specific custom runsizes list subroutine
	if (exists $custom_gen_hash{testset}{$testset}{runsizes}) {
		debug_print(2,"DEBUG:custom_gen_runsizes() calling $custom_gen_hash{testset}{$testset}{runsizes}\n");
		my $funcname = "$custom_gen_hash{testset}{$testset}{runsizes}";
		*func = \&$funcname;
		return func($sizes);
	}
	else {
		return @$sizes;
	}
}

sub custom_gen_joblist {
	my $ppn = shift;
	my $numprocs = shift;

	# run any specific custom job list subroutine
	if (exists $custom_gen_hash{testset}{$testset}{joblist}) {
		debug_print(2,"DEBUG:custom_gen_joblist() calling $custom_gen_hash{testset}{$testset}{joblist}\n");
		my $funcname = "$custom_gen_hash{testset}{$testset}{joblist}";
		*func = \&$funcname;
		return func($ppn,$numprocs);
	}
	else {
		return @job_list;
	}
}


sub custom_gen_init {
	my $testset = shift;

	debug_print(3,"DEBUG: entering custom_gen_init()\n");

	#  do any testset specific gen_init called for
	if (exists $custom_gen_hash{testset}{$testset}{init}) {
		debug_print(2,"DEBUG:custom_gen_init() calling $custom_gen_hash{testset}{$testset}{init} \n");
		my $funcname = "$custom_gen_hash{testset}{$testset}{init}";
		*func = \&$funcname;
		func($testset);	
	}

	# loop through the benchmarks/tests/apps found to find any benchmark
	# specific generate stuff to init
	foreach $job (keys %templates) {
		debug_print(3,"DEBUG:custom_gen_init() looking for benchmark \'$job\' customizations\n");
		if (exists $custom_gen_hash{benchmark}{$job}{init}) {
			debug_print(2,"DEBUG:custom_gen_init() calling $custom_gen_hash{benchmark}{$job}{init} \n");
			my $funcname = "$custom_gen_hash{benchmark}{$job}{init}";
			*func = \&$funcname;
			func($testset);	
		}
	}
}


sub custom_gen_innerloop {
	my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $job = shift;

	debug_print(3,"DEBUG: entering custom_gen_innerloop()\n");

	# specific generate stuff to run in the inner most generate loop
	if (exists $custom_gen_hash{benchmark}{$job}{innerloop}) {
		debug_print(2,"DEBUG:custom_gen_innerloop() calling $custom_gen_hash{benchmark}{$job}{innerloop} \n");
		my $funcname = "$custom_gen_hash{benchmark}{$job}{innerloop}";
		*func = \&$funcname;
		return func($outbuf,$numprocs,$ppn,$numnodes,
			$runtype,$walltime,$testset,$jobname,$ident,$job);
	}

	# specific generate stuff to run in the inner most generate loop based on testset
	if (exists $custom_gen_hash{testset}{$testset}{innerloop}) {
		debug_print(2,"DEBUG:custom_gen_innerloop() calling $custom_gen_hash{testset}{$testset}{innerloop} \n");
		my $funcname = "$custom_gen_hash{testset}{$testset}{innerloop}";
		*func = \&$funcname;
		return func($outbuf,$numprocs,$ppn,$numnodes,
			$runtype,$walltime,$testset,$jobname,$ident,$job);
	}
}


######################################################################
######################################################################
# The following subroutines implement the actualy testset and benchmark
# specific customizations as directed by the %custom_gen_hash
#

sub npb_gen_init {
	my $testset = shift;

	debug_print(3,"DEBUG: entering npb_gen_init()\n");

    # tell cbench_gen_jobs to use the 'npb' job template for
	# all jobs
	$use_single_template_for_testset = 1;

	# The list of NAS codes to build.
	my @codes = ('cg','ft','sp','bt','mg','lu','ep','is');

	# The list of NAS code classes (which correspond to how much memory
	# a NAS code uses and how much work is done) to generate.
	# class A and W are too small for us to really care about
	my @classes = ('B', 'C', 'D');

	@npb_job_list = ();

	foreach my $c (@codes) {
		foreach my $m (@classes) {
			push @npb_job_list, "$c$m";	
		}
	}
	debug_print(3,"DEBUG:npb_gen_init() joblist=".join(',',@npb_job_list));
}

sub npb_gen_joblist {
	my $ppn = shift;
	my $numprocs = shift;

	debug_print(3,"DEBUG: entering npb_gen_joblist($ppn,$numprocs)\n");

	# npb job list will be different depending on the number of processors
	# we are generating for... so we have to cull the list each time
	my @tmplist = ();
	foreach my $job (@npb_job_list) {
		my ($code) = $job =~ /^(\S+)[ABCD]$/;

		# NAS benchmarks only run on a perfect square number of
		# processors or a power of two number of procs (depending
		# on the benchmark).  Filter out all other run sizes.
		if ($code =~ /sp|bt/) {
			# perfect square codes
			next unless perfect_square($numprocs);
		}
		else {
			# power of two codes
			next unless power_of_two($numprocs);
		}
		push @tmplist, $job;
	}

	debug_print(3,"DEBUG:npb_gen_joblist() joblist=".join(',',@tmplist));
	return @tmplist;
}

sub npb_gen_innerloop {
	my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $job = shift;

	debug_print(3,"DEBUG: entering npb_gen_innerloop($job)\n");

	my ($code,$class) = $job =~ /^(\S+)([ABCD])$/;
	my $npbname = "$code\.$class\.$numprocs";
	debug_print(3,"DEBUG:npb_gen_innerloop() $npbname\n");
	$$outbuf =~ s/NPB_HERE/$npbname/gs;

	return 0;
}

sub hpcc_gen_init {
	my $testset = shift;

	debug_print(3,"DEBUG: entering hpcc_gen_init()\n");

	# if we are generating for the shakedown testset, we use low
	# memory utilization setup for Linpack to speed the testing up
	if ($testset eq "shakedown") {
		@memory_util_factors = (0.45);
	}

	# read in the hpcc hpccinf.txt config file generation template
	$file = "$bench_test\/$testset\/hpccinf_txt.in";
	open (INFILE,"<$file") or die
		"ERROR:hpcc_gen_init() Could not open $file ($!)";
	undef $/;
	$hpccinf_txt = <INFILE>;
	close(INFILE);
	$/ = "\n";
}

sub hpcc_gen_innerloop {
	my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $job = shift;

	debug_print(3,"DEBUG: entering hpcc_gen_innerloop()\n");

	# We try generating the hpccinf.txt file first so that we can
	# abort properly if compute_PQ() fails w/o writing any
	# files.
	#
	# now we need to generate the hpccinf.txt file for this job. First,
	# we need to figure out the N, P, and Q parameters for this
	# particular job. N is computed based on the total memory available
	# per processor and a memory utlization factor (or array of factors
	# which will generate multiple N values for HPL.dat). P and Q are
	# computed based on the heuristic that HPL "likes" a P:Q ratio
	# of 1:k with k in [1..3].
	my ($P, $Q) = compute_PQ($numprocs);
	if ($P == 0 or $Q == 0) {
		warning_print("No files generated for hpcc $jobname\n");
		rmdir "$testset_path\/$ident\/$jobname";
		return 1;
	}
	my @Nvals = compute_N($numprocs,$ppn);
	my $num_Nvals = @Nvals;
	$datbuf = $hpccinf_txt;
	$datbuf =~ s/HPCC_NUM_N_HERE/$num_Nvals/gs;
	$datbuf =~ s/HPCC_N_HERE/@Nvals/gs;
	$datbuf =~ s/HPCC_P_HERE/$P/gs;
	$datbuf =~ s/HPCC_Q_HERE/$Q/gs;

	# write out the generated hpccinf.txt file
	my $full_test_path = "$testset_path\/$ident\/$jobname\/hpccinf.txt";
	open (OUTFILE,">$full_test_path") or die
		"Could not write $full_test_path ($!)";
	print OUTFILE $datbuf;
	close(OUTFILE);

	return 0;
}

sub xhpl_gen_init {
	my $testset = shift;

	debug_print(3,"DEBUG: entering xhpl_gen_init()\n");

	# if we are generating for the shakedown testset, we use low
	# memory utilization setup for Linpack to speed the testing up
	if ($testset eq "shakedown") {
		@memory_util_factors = (0.45);
	}

	# read in the xhpl HPL.dat config file generation template
	$file = "$bench_test\/$testset\/xhpl_dat.in";
	open (INFILE,"<$file") or die
		"ERROR:xhpl_gen_init() Could not open $file ($!)";
	undef $/;
	$xhpl_dat = <INFILE>;
	close(INFILE);
	$/ = "\n";
}


sub xhpl_gen_innerloop {
	my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $job = shift;

	debug_print(3,"DEBUG: entering xhpl_gen_innerloop()\n");

	# We try generating the HPL.dat file first so that we can
	# abort properly if compute_PQ() fails w/o writing any
	# files.
	#
	# now we need to generate the HPL.dat file for this job. First,
	# we need to figure out the N, P, and Q parameters for this
	# particular job. N is computed based on the total memory available
	# per processor and a memory utlization factor (or array of factors
	# which will generate multiple N values for HPL.dat). P and Q are
	# computed based on the heuristic that HPL "likes" a P:Q ratio
	# of 1:k with k in [1..3].
	my ($P, $Q) = compute_PQ($numprocs);
	if ($P == 0 or $Q == 0) {
		warning_print("No files generated for linpack $jobname\n");
		rmdir "$testset_path\/$ident\/$jobname";
		return 1;
	}
	my @Nvals = compute_N($numprocs,$ppn);
	my $num_Nvals = @Nvals;
	$datbuf = $xhpl_dat;
	$datbuf =~ s/XHPL_NUM_N_HERE/$num_Nvals/gs;
	$datbuf =~ s/XHPL_N_HERE/@Nvals/gs;
	$datbuf =~ s/XHPL_P_HERE/$P/gs;
	$datbuf =~ s/XHPL_Q_HERE/$Q/gs;

	# write out the generated HPL.dat file
	my $full_test_path = "$testset_path\/$ident\/$jobname\/HPL.dat";
	open (OUTFILE,">$full_test_path") or die
		"Could not write $full_test_path ($!)";
	print OUTFILE $datbuf;
	close(OUTFILE);

	return 0;
}


sub trilinos_epetratest_gen_innerloop {
	my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $job = shift;

	debug_print(3,"DEBUG: entering trilinos_epetratest_gen_innerloop()\n");

	# The epetra test program wants NumProcX and NumProcY parameters on the command line,
	# with NumProcX * NumProcY == NP.  The examples on http://www.sandia.gov/benchmarks show
	# that the factors should look like what HPL and HPCC use for P and Q values, so the
	# compute_PQ() function can be used.
	my ($X, $Y) = compute_PQ($numprocs);
	if ($X == 0 or $Y == 0) {
		print "Couldn't determine NumProcX and NumProcY for NP=$numprocs.  Skipping $jobname...\n";
		rmdir "$testset_path\/$ident\/$jobname";
		return 1;
	}

	# Epetra prefers X >= Y though
	my $NUMPROCS_X = max($X,$Y);
	my $NUMPROCS_Y = min($X,$Y);
	$$outbuf =~ s/NUMPROCS_X_HERE/$NUMPROCS_X/gs;
	$$outbuf =~ s/NUMPROCS_Y_HERE/$NUMPROCS_Y/gs;

	return 0;
}

sub lammps_gen_joblist {
    my $ppn = shift;
    my $numprocs = shift;

	# scaled in the lammps testset means weakly scaled, otherwise jobs are
	# strongly scaled
    my @scaled_joblist = qw(rhodo.scaled chain.scaled lj.scaled eam.scaled chute.scaled);
    my @normal_joblist = qw(rhodo chain lj eam chute rhodo.scaled rhodolong.scaled chain.scaled lj.scaled eam.scaled chute.scaled); #this is only a temporary list; LAMMPS has many more codes to use 
    debug_print(3, "DEBUG: entering lammps_gen_joblist($ppn,$numprocs)\n");

    my @tmplist =();

    # generate normal jobs
    if (not defined $scaled_only) {
        debug_print(3, "DEBUG: generating lammps normal jobs (strongly scaled)");
        push(@tmplist, @normal_joblist);
    }

    # create only scaled jobs when --scaled_only parameter is set
    else {
        debug_print(3, "DEBUG: generating lammps scaled jobs (weakly scaled)");
        push(@tmplist, @scaled_joblist);
    }

    debug_print(3, "DEBUG: lammps_gen_joblist() joblist=".join(',',@tmplist));
    return @tmplist; 
}   

sub lammps_gen_innerloop {
    my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
    my $ppn = shift;
    my $numnodes = shift;
    my $runtype = shift;
    my $walltime = shift;
    my $testset = shift;
    my $jobname = shift;
    my $ident = shift;
    my $job = shift;

    debug_print(3,"DEBUG: entering custom_lammps_innerloop()\n");

    debug_print(2,"DEBUG:lammps_gen_innerloop() populating files in: $testset_path\/$ident\/$jobname\n");

	# symlink any data files into the jobs directory from the directory holding all the input
	# decks and data files that only need to be read
	#
	# this way we don't have to muck with the input decks path to the data files, they just
	# look in the CWD
	my $jobbase = $job;
	$jobbase =~ s/\.scaled//;
	if (-f "$testset_path\/bench\/data.$jobbase") { 
		debug_print(2,"DEBUG:lammps_gen_innerloop() symlinking $testset_path\/bench\/data.$jobbase\n");
		system("/bin/ln -sf $testset_path/bench/data.$jobbase $testset_path\/$ident\/$jobname\/data.$jobbase");
	}
	if ($jobname =~ /eam/ ) {
		debug_print(2,"DEBUG:lammps_gen_innerloop() symlinking $testset_path\/bench\/Cu_u3.eam\n");
		system("/bin/ln -sf $testset_path/bench/Cu_u3.eam $testset_path\/$ident\/$jobname\/Cu_u3.eam");
	}

	#set up the scaling parameters based on this jobsize
    if ( $jobname =~ /scaled/ ) {
		my $scale = 1;
		(defined $scale_factor) and $scale = $scale_factor;

		# according to LAMMPS readme file, LJ and EAM decks need to have Px,Py,Pz a factor
		# of 20 greater than other decks
		#
		# UPDATE (03-24-09): It looks like the in.lj and in.eam input decks already 
		# 	account for the scale factor of 20. In some testing, it seems like a
		#   additional scale factor of 2-3 results in an about 200MB/process footprint.
		($job =~ /lj\.scaled|eam\.scaled/) and $scale = 3;

		my $factors = "$scale $scale $scale";
        my $scaling_params = lammps_get_scaling_params($numprocs, $factors);
		debug_print(2,"DEBUG:lammps_gen_innerloop($job) scaling_params=$scaling_params");
        $$outbuf =~ s/SCALING_PARAMS_HERE/$scaling_params/gs;
    }
	else {
        $$outbuf =~ s/SCALING_PARAMS_HERE//gs;
	}


    return 0;
}

sub amg_gen_joblist {
	my $ppn = shift;
	my $numprocs = shift;
	
	my @list = ();

	main::debug_print(3,"DEBUG: entering amg_gen_joblist($ppn,$numprocs)\n");

	foreach my $j (@main::job_list) {
		(main::three_int_factors($numprocs) ne '') and push @list, $j;
	}

	return @list;
}


sub amg_gen_innerloop {
	my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = uc shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $job = shift;

	main::debug_print(3,"DEBUG: entering amg_gen_innerloop()\n");

	my ($px,$py,$pz) = split(',',main::three_int_factors($numprocs));
	main::debug_print(3,"DEBUG:amg_gen_innerloop() px=$px py=$py pz=$pz\n");

	$$outbuf =~ s/PX_HERE/$px/gs;
	$$outbuf =~ s/PY_HERE/$py/gs;
	$$outbuf =~ s/PZ_HERE/$pz/gs;

	# symlink the input deck
	system("/bin/ln -sf $testset_path/sstruct.in.AMG.FD $testset_path\/$ident\/$jobname\/.");

	return 0;
}

sub irs_gen_runsizes {
	my $sizes = shift;

	#my @newsizes = ();
	my @newsizes = (8,27,64,125,216,343,512,729,1000,1331,1728,2197,2744,3375,4096);

	main::debug_print(3,"DEBUG: entering irs_gen_runsizes(@$sizes)\n");

	#foreach my $n (@{$sizes}) {
		# if the number is a cube root, we can use it
	#	if (main::int_cube_root($n) != 0) {
	#		push @newsizes, $n;
	#	}
	#}

	main::debug_print(3,"DEBUG:irs_gen_runsizes() runsizes=".join(',',@newsizes));
	return @newsizes;
}

sub sweep3d_gen_init {
    my $testset = shift;
    %sweep3d_files = ();

    my $file;
    main::debug_print(3,"DEBUG: entering sweep3d_gen_init()\n");

    # cache the input file generation templates
    @sweep3d_templates = qw(150std long);
    for my $template (@sweep3d_templates) {
        main::debug_print(3, "DEBUG: reading in $template input file template\n");

        open (INFILE,"<$bench_test\/$testset\/input_files\/sweep3d_$template") or die
            "ERROR:sweep3d_gen_init() Could not open $bench_test\/$testset\/input_files\/sweep3d_$template ($!)";
        undef $/;

        $sweep3d_files{$template} = <INFILE>;

        close(INFILE);
        $file = "";
    }
    $/ = "\n";
}

sub sweep3d_gen_joblist {

    main::debug_print(3, "DEBUG: entering sweep3d_gen_joblist\n");

    my @joblist = qw(150std long);

    main::debug_print(3, "DEBUG: sweep3d_gen_joblist=".join(',',@joblist));

    return @joblist;
}

sub sweep3d_gen_innerloop {
    my $outbuf = shift;      # a *reference* to the actual $outbuf
    my $numprocs = shift;
    my $ppn = shift;
    my $numnodes = shift;
    my $runtype = shift;
    my $walltime = shift;
    my $testset = shift;
    my $jobname = shift;
    my $ident = shift;
    my $job = shift;

    main::debug_print(3,"DEBUG: entering custom_sweep3d_innerloop()\n");
    main::debug_print(2,"DEBUG: sweep3d_gen_innerloop() populating files in: $testset_path\/$ident\/$jobname\n");
    main::debug_print(3,"DEBUG: writing input file for $job with NP=$numprocs and PPN=$ppn\n");

    # substitute in required input deck information for this job size
    $databuf = $sweep3d_files{$job};
    $databuf =~ s/NP_HERE/$numprocs/gs;
    $databuf =~ s/PPN_HERE/$ppn/gs;

    # write out the generated input file
    my $full_test_path = "$testset_path\/$ident\/$jobname\/input";
    open (OUTFILE,">$full_test_path") or die
        "Could not write $full_test_path ($!)";
    print OUTFILE $databuf;
    close(OUTFILE);

    return 0;
}

sub phdmesh_gen_runsizes {
	my $sizes = shift;

	main::debug_print(3,"DEBUG: entering phdmesh_gen_runsizes(@$sizes)\n");

	# powers of two only
	my @newsizes = (1,2,4,8,16,32,64,128,256,512,1024,2048,4096,8192);

	main::debug_print(3,"DEBUG:phdmesh_gen_runsizes() runsizes=".join(',',@newsizes));
	return @newsizes;
}

sub phdmesh_gen_innerloop {
	my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = uc shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $job = shift;

	main::debug_print(3,"DEBUG: entering phdmesh_gen_innerloop()\n");

	my %fact = (
		1 => '2,1,1',
		2 => '2,1,2',
		4 => '4,1,2',
		8 => '4,1,4',
		16 => '4,2,4',
		32 => '8,2,4',
		64 => '8,2,8',
		128 => '8,4,8',
		256 => '16,4,8',
		512 => '16,4,16',
		1024 => '16,8,16',
		2048 => '32,8,16',
		4096 => '32,8,32',
		8192 => '32,16,32',
	);

	# get the base factors 
	my ($px,$py,$pz) = split(',',$fact{$numprocs});

	# for the standard gears job that phdmesh has as an example, i.e. the scaling.i
	# file, we just need to multiply the py base factor by 3.
	($job eq 'gearsstd') and $py = $py * 3;

	# for the gearsbig job, we just want to scale things some. the amount is based
	# on some sample runs, but is subject to change as needed.
	if ($job eq 'gearsbig') {
		$px = $px * 2;
		$py = $py * 6;
		$pz = $pz * 2;
	}

	my $numgears_per_proc = ($px * $py * $pz) / $numprocs;

	main::debug_print(3,"DEBUG:phdmesh_gen_innerloop() px=$px py=$py pz=$pz\n");

	# build the input file contents
	my $datbuf = "threadpool 1
#
# Weak scaling test with $numgears_per_proc gears per processor,
# such that the gear-grid dimensions grow roughly
# uniformly in each spatial dimension.
#
# $numprocs Processes:
gears $px $py $pz
";

	# write out the generated phdmesh input file
	my $full_test_path = "$testset_path\/$ident\/$jobname\/input.i";
	open (PHDFILE,">$full_test_path") or die
		"Could not write $full_test_path ($!)";
	print PHDFILE $datbuf;
	close(PHDFILE);

	return 0;
}

sub sppm_gen_init {
    my $testset = shift;

    main::debug_print(3,"DEBUG: entering sppm_gen_init()\n");

    open (INFILE,"<$bench_test\/$testset\/inputdeck.cbench") or die
        "ERROR:sweep3d_gen_init() Could not open $bench_test\/$testset\/inputdeck.cbench ($!)";
    undef $/;

    # save input file for later use
    $input_file = <INFILE>;

    close(INFILE);

    return 0;
}

sub sppm_gen_innerloop {
	my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = uc shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $job = shift;

	main::debug_print(3,"DEBUG: entering sppm_gen_innerloop()\n");

    # substitute in required input deck information for this job size
    my $databuf = $input_file;
    $databuf =~ s/NP_HERE/$numprocs/gs;
    my $temp = calc_num_threads($numprocs, $ppn);
    $databuf =~ s/NUM_THREADS_HERE/$temp/gs;

    main::debug_print(3,"DEBUG: writing input file for $job with NP=$numprocs and PPN=$ppn\n");

    # write out the generated input file
    my $full_test_path = "$testset_path\/$ident\/$jobname\/inputdeck";
    open (OUTFILE,">$full_test_path") or die
        "Could not write $full_test_path ($!)";
    print OUTFILE $databuf;
    close(OUTFILE);

    return 0;
}

sub graph500_gen_innerloop {
	my $outbuf = shift;      # a *reference* to the actual $outbuf
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = uc shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $job = shift;

    main::debug_print(3,"DEBUG: entering graph500_gen_innerloop()\n");

    # give factors some default values if undefined
    $scale_factor = 8 unless (defined $scale_factor);
    $edge_factor = 16 unless (defined $edge_factor);


    # substitute in the factor values
    $$outbuf =~ s/SCALE_HERE/$scale_factor/gs;
    $$outbuf =~ s/EDGE_FACTOR_HERE/$edge_factor/gs;

    return 0;
}

######################################################################
######################################################################
# The following are utility subroutines for cbench_gen_jobs

sub seconds_to_walltime {
	my $secs = shift;

	my $hour = int ($secs / 3600);
	$secs -= $hour * 3600;
	my $min = int ($secs / 60);
	$secs -= $min * 60;

	return sprintf("%02d:%02d:%02d",$hour,$min,$sec);
}

sub walltime_to_seconds {
	my $str = shift;
	if ($str =~ /(\d+):(\d+):(\d+)/ ) {
		my ($hour, $min, $sec) = ($1,$2,$3);
		$sec += $min * 60;
		$sec += $hour * 3600;

		return $sec;
	}
	elsif ($str =~ /(\d+):(\d+)/ ) {
		my ($hour, $min, $sec) = ($1,$2,0);
		$sec += $min * 60;
		$sec += $hour * 3600;

		return $sec;
	}
	else {
		warning_print("default_walltime is in an unknown format, using 24:00:00");
		return (3600 * 24);
	}
}

sub usage {
    print "USAGE: $0 \n";
    print "Cbench script to generate jobs in the $testset test set\n".
          "   --testset <name> Override the name of the testset (optional).\n".
          "   --ident          Identifying string for the test\n".
		  "   --binident       Binary tree identifier\n".
		  "   --preamble           Command string to execute before running the\n".
		  "                        actual hardware tests on each node. For example\n".
		  "                        to pickup the right environment:\n".
		  "                            --preamble '. /etc/profile'\n".
	#	  "   --binname        Use a non-default binary name\n".
	#	  "                      e.g. --binname xhpl.superoptimized\n".
		  "   --xhplbin        Use a non-default Linpack binary name\n".
		  "                      e.g. --binname xhpl.superoptimized\n".
		  "   --hpccbin        Use a non-default HPCC binary name\n".
          "   --maxprocs       The maximum number of processors to generate\n".
          "                    jobs for\n".
          "   --minprocs       The minimum number of processors to generate\n".
          "                    jobs for\n".
          "   --procs          Only generate jobs for a single processor count\n".
		  "   --nodes <num>    Same as --maxprocs, --minprocs, --procs but with number\n".
		  "                    of nodes\n".
		  "   --minnodes <num>\n".
		  "   --maxnodes <num>\n".
          "   --runsizes       Comma separated list of run sizes, i.e. processor\n".
          "                    counts, to generate jobs for.  This overrides\n".
          "                    the default array of run sizes declared in cbench.pl\n".
          "   --match          This limits the generation of jobs to\n" .
          "                    jobs with a jobname that matches the specified\n" .
          "                    regex string. For example,\n" .
          "                      --match 2ppn\n" .
          "                    would only generate 2 ppn tests\n" .
          "   --exclude        This is just like the --match parameter except\n" .
          "                    that jobs matching are NOT processed\n" .
          "   --scratchdir <path>\n".
          "   --testdir <path> Path to use as a \"scratch\" or parallel filesystem\n".
		  "                    for benchmarks/apps testing which require the use of \n".
		  "                    a larger scale or higher performance filesystem. The\n".
		  "                    path determines the filesystem to use implicitly\n".
		  "   --jobcbenchtest <path>  Specify an alternate CBENCHTEST path used when\n".
		  "                           generating job scripts. This is useful for\n".
		  "                           generating jobs in one place and being able to use\n".
		  "                           a different path where the jobs are run, like a \n".
		  "                           lightweight initramfs Linux node for instance\n".
		  "   --redundant      Generate redundant ppn/np combinations (not on by default)\n".
		  "   --unevenspan      Generate uneven ppn/np span combinations (not on by default)\n".
		  "   --joblaunch_extraargs <args>  Override the joblaunch_extraargs setting in cluster.def\n".
		  "   --memory_util_factors  Override the cluster.def \@memory_util_factors array.\n".
		  "                          For example:\n".
		  "                            --memory_util_factors 0.10,0.77,0.85\n".  
		  "   --ompthreads <num> \n".
		  "   --ompnumthreads <num> \n".
		  "   --threads <num>  Tell Cbench to use the specified number of threads per\n".
		  "                    process where applicable. This is usually equivalent to\n".
		  "                    setting OMP_NUM_THREADS environment variable\n".
		  "   --defaultwalltime <time> String of the form HH:MM:SS specificying the default\n".
		  "                            walltime used for generating jobs. This overrides\n".
		  "                            the cluster.def \$default_walltime option.\n".
		  "   --walltimemethod <0|1>   Choose the algorithm used to generate walltimes for jobs.\n".
		  "                            This overrides the cluster.def \$walltime_method option.\n".
          "                            Method 0 is simply a constant value equal to \n".
		  "                            \$default_walltime.\n".
          "                            Method 1 is an algorithm that discretely steps up the\n".
		  "                            walltime for each job of increasing runsize by the constant\n".
          "                            time in minutes controlled by the \$walltime_steptime \n".
		  "                            cluster.def option. In this method, the \$default_walltime\n".
		  "                            option is used as the minimum starting walltime from which\n".
		  "                            all others are increased.  The stepped walltimes help \n".
		  "                            schedulers backfill better in general.\n".
		  "   --gazebo               Gazebo mode of operation\n".
		  "   --gazebohome <path>    Where the Gazebo tree is located\n".
		  "   --gazeboconfig <name>  Name of the Gazebo submit_config that will be APPENDED to\n".
          "   --debug <level>  Turn on debugging at the specified level\n";
    # only print the LAMMPS options when it is a lammps testset
	($0 =~ /lammps/) and print "   \nLAMMPS scaling options:\n".
          "   --scaled_only             Generate scaled jobs only (weakly scaled that is)\n".
          "   --scalefactor <factor>   The additional factor by which you would like to \n".
          "                             scale the x,y,z values in the scaling benchmarks\n".
		  "                             For example:\n".
		  "                               --scale_factor 20\n\n";

        ($0 =~ /graph500/) and print "\nGraph500 Scaling Options:\n".
          "   --scalefactor <factor>  Scale factor for Graph500 graph (Default: 8)\n".
          "   --edgefactor  <factor>  Edge factor for Graph500 graph (Default: 16)\n\n";
}
