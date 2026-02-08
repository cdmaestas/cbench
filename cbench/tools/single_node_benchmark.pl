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

# First pass at a script purposed to deal with running a standard repeatable
# single node benchmarking suite, captializing on other Cbench capabilities
# and building a report about it.
#
# This first pass won't address, in the interest of time and needing to see
# how things develop, Marcus's monte carlo multi-node data gathering scenario...

#use warnings;

# need to know where everything cbench lives!
BEGIN {
	die "Please define CBENCHOME!\n" if !defined($ENV{CBENCHOME});
}
use lib $ENV{CBENCHOME};
use lib "/home/rkbrait/perl5/lib64/perl5";
require "cbench.pl";
$CBENCHOME = $BENCH_HOME = $ENV{CBENCHOME};

# add Cbench perl library to the Perl search path
use lib "$ENV{CBENCHOME}\/perllib";

# enable/disable color support appropriately
detect_color_support();

use Getopt::Long;
use Data::Dumper;
use File::stat;
use Term::ANSIColor qw(:constants color);
use Statistics::Descriptive;
$Term::ANSIColor::AUTORESET = 1;

GetOptions(
	'numcore|numcpu=i' => \$NUMCPUS,
	'ident=s' => \$ident,
	'binident=s' => \$binident,
	'destdir=s' => \$destdir,
	'run' => \$run,
	'report' => \$report,
	'savepdfsrc' => \$savepdfsrc,
	'pdftag=s' => \$pdftag,
	'node=s' => \$node,
	'tests=s' => \$tests,
	'dryrun|dry-run' => \$dryrun,
	'debug=i' => \$DEBUG,
    'help' => \$help,
    'nodetonode' => \$nodetonode,
    'coretonode' => \$coretonode,
);

(defined $help) and usage() and exit;

(!defined $tests) and $tests = 'stream|cachebench|dgemm|mpistreams|linpack|npb';

(!defined $run and !defined $report) and $run = 1 and $report = 0;

(!defined $ident) and $ident = $cluster_name . "1";
(!defined $destdir) and $destdir = ".";
# make sure the test ident directory is there with the proper test identification
(! -d "$destdir\/$ident") and mkdir "$destdir\/$ident",0750;

# find the Cbench testing tree
my $bench_test = get_bench_test();
my $bindir = 'bin';
my $binidentopt = '';
(defined $binident) and $bindir = "bin.$binident";
(defined $binident) and $binidentopt = "--binident $binident";
my $binpath = "$bench_test/$bindir";
(defined $DEBUG) and print "DEBUG: test tree path = $bench_test\n";

my $hn = `/bin/hostname`;
chomp $hn;
if (defined $report and defined $node) {
    $hn = $node;
}


# When we use other Cbench testsets we will create unique test identifiers
# in each testset for whatever we are doing. This is the basename for those
# test identifiers.
my $identbase = "snb_$ident";

# When we are generating a report we'll build sections in the Latex doc
# as we go along. This buffer captures all that will be added in the core
# of the doc
my @report_core_buf= ();

# log file for the run
my $logfile = "$destdir/snb.$hn.$ident.log";
open (LOG,">>$logfile") or die
	"Could not open $logfile ($!)";

# probe the number of cpu cores
my $numcores = linux_num_cpus();
# the number of cores read in from cpuinfo files generated during a run
my $num_cores_counted = 0;

# become the leader of a new process group so that all the child test
# processes will see our signals
setpgrp(0,0);
$SIG{CHLD} = \&REAPER;
$SIG{INT} = \&CATCH;
$SIG{TERM} = \&CATCH;
$SIG{KILL} = \&CATCH;
$SIG{USR1} = \&CATCH;
$SIG{USR2} = \&CATCH;


(defined $run) and
	logmsg("INITIATING Single Node Benchmarking RUN on node $hn, test identifier is $ident, test regex: $tests");
(defined $report and !defined $run) and
	logmsg("INITIATING Single Node Benchmarking REPORT for node $hn, test identifier is $ident");

# grab some info on the node
if (defined $run) {
	runcmd("/bin/uname -s -r -m -p -i -o","uname","overwrite");
	runcmd("cat /proc/cpuinfo","cpuinfo","overwrite");
	runcmd("cat /proc/meminfo","meminfo","overwrite");

        # hwloc info
        runcmd("$binpath/lstopo","hwloc","file");
}
if ($report) {
	add_section("Basic Node Description");

	my $text = "";
	my $num_physical_cpus = 0;
	my $num_logical_cpus = 0;

	# uname info
	my $uname = `cat $destdir/$ident/$hn.snb.uname.out`;
	$text .= "$uname";

	# cpu/core info
	my @cpudata = `cat $destdir/$ident/$hn.snb.cpuinfo.out`;
        my %cpumap = linux_parse_cpuinfo(\@cpudata);
	(defined $DEBUG) and print Dumper(%cpumap);
        # decode what the cpumap hash tells us
        foreach (keys %cpumap) {
                    (/model/) and next;
                    $num_physical_cpus++;
            $num_cores_counted += $cpumap{$_}{'cores'};
            $num_logical_cpus += scalar @{$cpumap{$_}{'logical'}};
        }
	# if no detailed core/socket info was found, fall back to just
	# simple logical cpu count 
	if (exists $cpumap{'COUNT'}) {
		$num_physical_cpus = $num_cores_counted = $cpumap{'COUNT'};
	}


	$text .= "Number of Physical Processors: $num_physical_cpus\n".
			"Number of Processing Cores: $num_cores_counted\n";

	# memory info
	my @meminfo = `cat $destdir/$ident/$hn.snb.meminfo.out`;
	foreach (@meminfo) {
		if (/MemTotal:\s+(\d+)\s+kB/) {
			my $mb = int ($1 / 1024);
			$text .= "Total Memory: $mb MB\n";
		}
	}

	add_text_raw($text);
	# more processor info
	add_list("Processor Models:",\@{$cpumap{'model'}});

}

#
# streams, via node_hw_test
if ($tests =~ /stream/ and $run) {
	logmsg("Starting STREAMS testing");
	runcmd("$bench_test/nodehwtest/node_hw_test --ident $identbase $binidentopt --match streams --debug 1","streams","overwrite");
}
# parse and report on streams
if ($report) {
	runcmd("$bench_test/nodehwtest/nodehwtest_output_parse.pl --ident $identbase --noerrors | /bin/grep streams","streams_data","overwrite");

	my $out = "$destdir/$ident/$hn.snb.streams_data.out";
	open (IN,"<$out") or do {
		print "WARNING: Could not open $out ($!)\n";
	};
	my @rawdata = <IN>;
	close(IN);

	# digest the raw data
	my %data = ();
	my $text = "";
	foreach my $l (@rawdata) {
		chomp $l;
		# streams_add: mean=3888.0000 max=3888.0000 min=3888.0000 stddev=0.0000  (sample count=1)
		if ($l =~ /streams\_(\w+)\:\s+mean=(\d+\.\d+)\s+max=(\d+\.\d+)\s+min=(\d+\.\d+)\s+stddev=(\d+\.\d+)\s+/)
		{
			$data{$1}{'mean'} = $2;
			$data{$1}{'max'} = $3;
			$data{$1}{'min'} = $4;
			$text .= "streams $1: $3 MB/s\n" unless ($1 =~ /failed/);
		}
	}
	#print Dumper (%data);

	add_section("STREAM Results");
	add_text_raw($text);
	add_text("\\clearpage\n");
}

#
# stream2
if ($tests =~ /streams/ and $run) {
	logmsg("Starting STREAM2 testing");
	# run any stream2 binary
	my @binlist = `cd $binpath/hwtests;ls -1 stream2-* 2>/dev/null`;
	foreach my $bin (@binlist) {
		chomp $bin;
		runcmd("$binpath/hwtests/$bin",$bin,"overwrite");
	}
}
# parse and report on stream2
if ($report) {
	# could be multiple stream2 binaries run...
	my %data = ();
	foreach my $out (`cd $destdir/$ident;ls -1 $hn.snb.stream2*.out`) {
		chomp $out;
		my $file = "$destdir/$ident/$out";
		open (IN,"<$file") or do {
			print "WARNING: Could not open $file ($!)\n";
		};
		my @rawdata = <IN>;
		close(IN);

		# find the stream2 binary name
		(my $bin) = $out =~ /$hn\.snb\.(\S+)\.out/;

		# grab the raw stream2 results
		for my $l (@rawdata) {
			if ($l =~ /\s+(\d+)\s+\d+\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+/)
			{
				$data{$1}{"$bin-fill"} = $2;
				$data{$1}{"$bin-copy"} = $3;
				$data{$1}{"$bin-daxpy"} = $4;
				$data{$1}{"$bin-sum"} = $5;
			}
		}
	}
	#print Dumper (%data);

	build_gnuplot_graph("stream2","STREAM2 Results","Bytes","MB/s",\%data,["set log x"]);
	add_section("STREAM2 Results");
	add_figure("stream2.pdf","STREAM2 Data","stream2");
}

#
# cachebench, via node_hw_test
if ($tests =~ /cachebench/ and $run) {
	logmsg("Starting CACHEBENCH testing");
	runcmd("$bench_test/nodehwtest/node_hw_test --ident $identbase $binidentopt --match cachebench --debug 1 --dump","cachebench","overwrite");
}
# parse and report on cachebench
if ($report) {
	my $out = "$destdir/$ident/$hn.snb.cachebench.out";
	open (IN,"<$out") or do {
		print "WARNING: Could not open $out ($!)\n";
	};
	my @rawdata = <IN>;
	close(IN);

	# digest the raw data
	my %data = ();
	my $test_context = "NONE";
	foreach my $l (@rawdata) {
		if ($l =~ /====> (\S+)/) {
			$test_context = $1;
		}
		elsif ($l =~ /^(\d+)\s+(\d+\.\d+)/) {
			push @{$data{$1}{$test_context}}, $2;
		}
	}
	#print Dumper (%data);

	# average the results at each vector length and put into a hash data
	# structure suitable for passing to the gnuplot generate
	my %plotdata = ();
	foreach my $len (sort {$a <=> $b} keys(%data)) {
		foreach my $tst (sort {$a cmp $b} keys(%{$data{$len}})) {
			my $statvar = Statistics::Descriptive::Full->new();
			$statvar->add_data(@{$data{$len}{$tst}});
			$plotdata{$len}{$tst} = $statvar->mean();
		}
	}
	#print Dumper (%plotdata);

	build_gnuplot_graph("cachebench","Cachebench Results","Bytes","MB/s",\%plotdata,["set log x"]);
	add_section("Cachebench Results");
	add_figure("cachebench.pdf","Cachebench Data","cachebench");
}

#
# dgemm memsize vs gflops, nodeperf2
if ($tests =~ /dgemm/ and $run) {
    
	logmsg("Starting DGEMM (nodeperf2) testing");

	# reset the output file
	runcmd("/bin/true","nodeperf2","overwrite");
	# loop through dgemm matrix sizes
	my $x = 20000;
	for (my $n = 2; $n <= 2048; )  {
		# figure out the number of iterations we want to do, rule of thumb
		my $i = int ($x / $n);
		(($i % 2) == 1) and $i++;
		# run the dgemm test multiple times so we can average
		for my $j (1..3) {
                        $ENV{OMP_NUM_THREADS}=$numcores; # the exec("exec $cmd") command doesn't like 'export', so
                                                         # set the environment variable here and hope it gets
                                                         # inherited by the nodeperf2 process - RKB
			runcmd("$binpath/nodeperf2-nompi -i $i -s $n","nodeperf2");
                        #runcmd("export OMP_NUM_THREADS=$numcores; $binpath/nodeperf2-nompi -i $i -s $n","nodeperf2");
		}
		$n = int ($n * 1.5);
	}
}
# parse and report on dgemm
if ($report) {
	my $out = "$destdir/$ident/$hn.snb.nodeperf2.out";
	open (IN,"<$out") or do {
		print "WARNING: Could not open $out ($!)\n";
	};
	my @rawdata = <IN>;
	close(IN);

	# grab the raw dgemm results
	my %data = ();
	for my $l (@rawdata) {
		if ($l =~ /\s+\S+: NN lda=\d+ ldb=\s*\d+ ldc=\d+ \d+ \d+ \d+ (\d+\.\d+) mem=(\d+) MB\s+/) {
			push @{$data{$2}}, $1;
		}
	}

	# average the dgemm results and put into a hash data structure suitable for
	# passing to the gnuplot generate
	my %plotdata = ();
	foreach my $mem (sort {$a <=> $b} keys(%data)) {
		my $statvar = Statistics::Descriptive::Full->new();
		$statvar->add_data(@{$data{$mem}});
		$plotdata{$mem}{'dgemm'} = $statvar->mean();
	}
	#print Dumper (%plotdata);

	build_gnuplot_graph("nodeperf2","DGEMM Results","Megabytes","Megaflops",\%plotdata);
	add_section("DGEMM Results");
	add_text("All DGEMM tests a run using a single process with OMP number of threads set".
		" to the maximum number of computing cores on the node\n");
	add_figure("nodeperf2.pdf","DGEMM Data","nodeperf2");
}

#
# mpi streams
if ($tests =~ /mpistreams/ and $run) {
	logmsg("Starting Multiprocess STREAMS (mpi streams) testing");
	# reset the output file
	runcmd("/bin/true","mpistreams","overwrite");
	
	# need this for building mpi job launches
	my $funcname = "$joblaunch_method\_joblaunch_cmdbuild";
	*func = \&$funcname;

	for my $np (1..$numcores) {
		system("echo '====> $np processes' >> $destdir/$ident/$hn.snb.mpistreams.out");
		my $jobcmd = func($np,$procs_per_node,1);
		$jobcmd .= "$binpath/hwtests/stream-mpi";
		runcmd("$jobcmd","mpistreams");
	}

}
# parse and report on mpi streams
if ($report) {
	my $out = "$destdir/$ident/$hn.snb.mpistreams.out";
	open (IN,"<$out") or do {
		print "WARNING: Could not open $out ($!)\n";
	};
	my @rawdata = <IN>;
	close(IN);

	# digest the raw data
	my %data = ();
	my $np = "NONE";
	foreach my $l (@rawdata) {
		if ($l =~ /====> (\d+) processes/) {
			$np = $1;
		}
		elsif ($l =~ /^(\w+):\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)/) {
			#Copy:       6049.9450      0.1059      0.1058      0.1061
			#Scale:      5980.1428      0.1072      0.1070      0.1073
			#Add:        6998.5623      0.1373      0.1372      0.1376
			#Triad:      5903.7286      0.1628      0.1626      0.1630
			$data{$np}{$1} = $2;
		}
	}  
	#print Dumper (%data);

	build_gnuplot_graph("mpistreams","Multiple Process STREAMS Results (MPI Streams)",
		"Number of Processes","MB/s",\%data);
	add_section("Multiple Process STREAMS Results (MPI Streams)");
	add_figure("mpistreams.pdf","MPISTREAMS Data","mpistreams");
}


# xhpl, use testset
if ($tests =~ /linpack/ and $run) {
	logmsg("Starting Linpack testing");

	# record the memory utilization factors from cluster.def for the run
	my $tmptxt = "MEM_UTIL_FACTORS: ". join(',',@memory_util_factors);
	system("echo '$tmptxt' > $destdir/$ident/$hn.snb.linpack.out");
	
	#
	# first we need to generate all the linpack jobs scripts
	logmsg("Generating Linpack testing scripts");

	# do the actual job script generation
	for my $threads (1..$numcores) {
		my $count = $numcores / $threads;
		for my $processes (1..$count) {
			#(($processes * $threads) > $numcores) and next;
			(!power_of_two($processes) and ($processes > 1)) and next;
			(!power_of_two($threads) and ($threads > 1)) and next;

			my $pq = $threads * $processes;
			my $cmd = "$bench_test/linpack/linpack_gen_jobs.pl --ident ".$identbase."_".
				$threads."threads --runsizes $processes $binidentopt --threads $threads";
			print "$cmd\n";
			runcmd("$cmd",'linpack');
		}
	}

	#
	# next we need to run all the linpack jobs scripts that make sense
	logmsg("Running Linpack testing scripts");
	for my $threads (1..$numcores) {
		my $count = $numcores / $threads;
		for my $processes (1..$count) {
			#(($processes * $threads) > $numcores) and next;
			(!power_of_two($processes) and ($processes > 1)) and next;
			(!power_of_two($threads) and ($threads > 1)) and next;

			my $cmd = "$bench_test/linpack/linpack_start_jobs.pl --ident ".$identbase."_".
				$threads."threads --procs $processes --interactive --match ${processes}ppn";
			#print "$cmd\n";
			runcmd("$cmd",'linpack');
		}
	}
	
}
# parse and report on linpack
if ($report) {
	runcmd("$bench_test/linpack/linpack_output_parse.pl --match \'$identbase\' --metric gflops --grep",
		"linpack_data","overwrite");

	my $out = "$destdir/$ident/$hn.snb.linpack_data.out";
	open (IN,"<$out") or do {
		print "WARNING: Could not open $out ($!)\n";
	};
	my @rawdata = <IN>;
	close(IN);

	# grok the grepable data spit out by the linpack output parser and categorize
	# it by number of procs and number of threads
	my %data = ();
	foreach (@rawdata) {
		# SERIES, NUMPROCS, MEAN, MAX, MIN, STDDEVIATION, SAMPLECOUNT, UNITS
		# snb_bl460c-quad-04_4threads-xhpl-2ppn-gflops, 2, 18.1125, 20.1500, 15.1000, 2.2187, 4, GigaFlops
		if (/(\S+)\_(\d+)threads\-(\S+)\-(\d+)ppn\-(\S+),\s+(\d+),\s+(\d+\.\d+),\s+(\d+\.\d+),\s+(\d+\.\d+),\s+(\d+\.\d+),\s+(\d+),\s+(\S+)/) {
			#print "$1 $2 $3 $4 $5 $6 $7 $8 $9 $10 $11 $12\n";
			my $ident = $1;
			my $nthreads = $2;
			my $bench= $3;
			my $nppn = $4;
			my $metric = $5;
			my $nproc = $6;
			my $mean = $7;
			my $max =  $8;
			my $min = $9;
			my $stddev = $10;
			my $count = $11;
			my $units = $12;

			$data{$nproc}{$nthreads} = $8;
		}

	}
	(defined $DEBUG) and print Dumper (%data);

	my $outl = "$destdir/$ident/$hn.snb.linpack.out";
	@rawdata = `cat $outl`;
	my $memfactors = 'unknown';
	foreach (@rawdata) {
		if (/MEM_UTIL_FACTORS:\s+(\S+)/) {
			$memfactors = $1;
		}
	}

	build_gnuplot_histogram("linpack","Single Node Linpack Results",
		"Number of MPI Processes","GigaFlops",\%data);
	add_section("Single Node Linpack Results");
	add_text("Memory Utilization Factors Used: $memfactors\n\n");
	add_figure("linpack.pdf","Linpack Data","linpack");

	# now, normalize the data by number of computing threads and build another
	# graph (easier to see scaling efficiency)
	for my $np (keys %data) {
		for my $nt (keys %{$data{$np}}) {
			my $tmp = $data{$np}{$nt};
			$data{$np}{$nt} = $tmp / ($np * $nt);
		}
	}
	build_gnuplot_histogram("linpack-normalized","Normalized Single Node Linpack Results",
		"Number of MPI Processes","GigaFlops / Total Number of Computing Threads",\%data);
	add_text("This graph normalizes the Single Node Linpack data by the total number of ".
		" computing threads so that scaling efficiency can more easily be seen.  The".
		" total number of".
		" computing threads is product of the number of MPI processes".
		" and the number of BLAS threads.\n");
	add_figure("linpack-normalized.pdf","Normalized Linpack Data","linpack-normalized");
}


# NPB, use testset
if ($tests =~ /npb/ and $run) {
	logmsg("Starting NAS Parallel Benchmark testing");
	# reset the output file

	runcmd("/bin/true","npb","overwrite");

	# generate the test identifier for our npb testing runs
	my $cmd = "$bench_test/npb/npb_gen_jobs.pl --ident ".$identbase.
		" --maxprocs $numcores $binidentopt --redundant";
	runcmd("$cmd",'npb');

	# do our npb testing runs starting with the biggest memory runs first,
	# i.e. the C class binaries
	$cmd = "$bench_test/npb/npb_start_jobs.pl --ident $identbase --minprocs 1".
		" --maxprocs $numcores --match \'C-".$numcores."ppn\' --interactive";
	runcmd("$cmd",'npb');
}
# parse and report on NPB
if ($report) {
	add_section("Single Node NAS Parallel Benchmark Results");

	#--xrange 0,4 --norm numprocs --match 'snb_bl465c-dual-05' --collapse 'snb'

	# build the first NPB plot
	runcmd("/bin/rm -f $bench_test/npb/npb.ps","npb");
	runcmd("$bench_test/npb/npb_output_parse.pl --match \'$identbase\' ".
		"--collapse \'snb\' --xrange 1,$num_cores_counted --yrange 0,\* --gnuplot ".
		"--linewidth 4 </dev/null","npb");
	runcmd("/bin/cp -f $bench_test/npb/npb.ps $destdir/.","npb");
	ps2pdf("$destdir/npb.ps");
	add_figure("npb.pdf","NAS Parallel Benchmark Data","npb");

	# build the second NPB plot which is normalized to show scaling efficiency
	runcmd("/bin/rm -f $bench_test/npb/npb.ps","npb");
	runcmd("$bench_test/npb/npb_output_parse.pl --match \'$identbase\' --scaledparalleleff ".
		"--collapse \'snb\' --xrange 1,$num_cores_counted --gnuplot --yrange 0,\* ".
		"--linewidth 4 </dev/null","npb");
	runcmd("/bin/cp -f $bench_test/npb/npb.ps $destdir/npb-normalized.ps","npb");
	ps2pdf("$destdir/npb-normalized.ps");
	add_text("This graph normalizes the NAS Parallel Benchmark data so that scaled parallel".
		"efficiency can be seen. A flat line at a Y value of 1 would be 100% efficiency.\n");
	add_figure("npb-normalized.pdf","Normalized NAS Parallel Benchmark Data","npb-normalized");
}


# hpcc, use testset, need cbench tweaked version with cmdline options

#
# test out how locking down threads to various core combinations
# affects performance. this kind of tests linux scheduler prowess
# as well as other core locality things. the data is quite open for
# interpretation...


# NUMA Memory-Access Tests
if ($tests =~ /numa-mem/ and $run) {
    my $logstr = "Starting NUMA Memory-Access ";
    my $mode = "unknown";
    $logstr .= $mode = ($coretonode) ? "core_to_node" : "node_to_node";
    $logstr .= " Testing";
    logmsg($logstr);


    if ($tests !~ /numa-mem-mpi/) {
        # to test memory-access characteristics, we look at memory read latency and memory bandwidth
        for my $metric ("latency", "bandwidth") {
            logmsg("Running NUMA $metric tests");

            my $cmdtag = "numa-$metric";
            my $command = "none";
            my @binlist = ();

            # compile an array of binaries for this metric
            if ($metric eq "latency") {
                $command = "$binpath/hwtests/lat_mem_rd";
                @binlist = "lat_mem_rd";
            }
            elsif ($metric eq "bandwidth") {
                # run any stream binary
                @binlist = `cd $binpath/hwtests;ls -1 stream*-* 2>/dev/null`;
            }
            else {
                print STDERR "numa-mem metric $metric is invalid\n";
                next;
            }

            # run the numa tests for each binary in the list
            for my $bin (@binlist) {
                ($main::INTsignalled) and exit;
                ($bin =~ /mpi/) and next; # we'll deal with mpi multi-threaded tests later
                chomp $bin;
                ($bin =~ /~/) and next; # don't run backup versions of an executable
                $command = "$binpath/hwtests/$bin";

                # verify that the requested executable exists
                $ret = `which $command`;
                if ($ret =~ /^which: no/ or $ret =~ /^$/) {
                    print STDERR "run_numa_tests(): can't find $command\n";
                }
                # found the executable - let's run the tests!
                else {

                    # need to set up the tests so that they save their output appropriately
                    #$command .= " >> $destdir/$ident/$hn.snb.$cmdtag.$date.out 2>&1";
                    my $filename = "$destdir/$ident/$hn.snb.$cmdtag.out";

                    # default to node-to-node mode
                    my $mode = ($coretonode) ? "core-to-node" : "node-to-node";

                    # lat_mem_rd needs some additional parameters
                    # the stride parameter here probably isn't ideal - perhaps do a sort of stride test on new machines?
                    ($command =~ /lat_mem_rd/) and $command .= " -P 1 -S 1000 131072";

                    # some Cbench-built STREAM tests can use a lot of memory - do a quick check 
                    # before trying to run one of the '10G' or 'big' STREAM tests
                    my $free = `free | grep Mem | awk \'{print \$2}\' 2>&1`;
                    chomp($free);
                    if (($bin =~ /big/ and $free < (2**20)/1024)){
                        logmsg("  NOT Starting $command: Only " . sprintf("%.2f", $free/(2**20)) . " GiB of memory in the system");
                        next;
                    }
                    if ($bin =~ /10G/ and $free < (10* 2**30)/1024) {
                        print "free is $free, " . ((10*2**30)/1024) . "\n";
                        logmsg("  NOT Starting $command: Only " . sprintf("%.2f", $free/(2**20)) . " GiB of memory in the system");
                        next;
                    }

                    # run the command now
                    logmsg("  Starting $command >> $filename");
                    run_numa_tests("", $command, $mode, $filename);
                }
            }

        }
    }
    if ($tests !~ /numa-mem-serial/) {

        # Run the Multi-Threaded STREAM binaries
        my $filename = "$destdir/$ident/$hn.snb.numa-mem_multithreaded.out";
        @binlist = `cd $binpath/hwtests;ls -1 stream*mpi* 2>/dev/null`;

        logmsg("Running Multi-Threaded NUMA Memory Bandwidth Tests");

        for my $mpitest (@binlist) {
            chomp($mpitest);
            $mpitest = "$binpath/hwtests/$mpitest";
            logmsg("  Starting $mpitest >> $filename");
            run_multithreaded_numa_tests($mpitest, $filename);
        }
    }
}

# NUMA GPU-Access Tests
if ($tests =~ /numa-gpu/ and $run) {
    my $logstr = "Starting NUMA GPU-Access ";
    my $mode = "unknown";
    $logstr .= $mode = ($coretonode) ? "core_to_node" : "node_to_node";
    $logstr .= " Testing";
    logmsg($logstr);

    # to test GPU-access characteristics, we use both the CUDA and OpenCL SHOC benchmarks
    for my $framework ("CUDA", "OpenCL") {
        logmsg("Running NUMA $framework tests");

        my $cmdtag = "numa-SHOC_$framework";
        my $command = "none";
        my $shoc_src = "$binpath/shoc/shoc-1.1.1";
        my @command_list = ("$shoc_src/tools/driver.pl");

        # run the numa tests for each binary in the list
        for my $command (@command_list) {
            ($main::INTsignalled) and last;

            # verify that the requested executable exists
            if (!(-e "$command")) {
                print STDERR "run_numa_tests(): can't find $command\n";
            }
            # found the executable - let's run the tests!
            else {

                # so prepend perl and some libraries
                my $LD_LIB_addition = "$ENV{OPENCLLIB}:$ENV{CUDALIB}:$ENV{MPIHOME}/lib64:$ENV{MPIHOME}/lib:$ENV{LD_LIBRARY_PATH}";
                $ENV{LD_LIBRARY_PATH} = $LD_LIB_addition; 

                # need to get the number of GPU devices in the system
                #  to do this we utilize the method used in driver.pl's printDevInfo() subroutine
                my $numdev = 0;
                my @retval = ();
                if (-e "$shoc_src/bin/Serial/OpenCL/BusSpeedDownload" ) {
                    @retval = `$shoc_src/bin/Serial/OpenCL/BusSpeedDownload -i 2>&1`;
                    #@retval = `LD_LIBRARY_PATH=$LD_LIB_addition $shoc_src/bin/Serial/OpenCL/BusSpeedDownload -i 2>&1`;
                }
                else {
                    @retval = `$shoc_src/bin/Serial/CUDA/BusSpeedDownload -i 2>&1`;
                    #@retval = `LD_LIBRARY_PATH=$LD_LIB_addition $shoc_src/bin/Serial/CUDA/BusSpeedDownload -i 2>&1`;
                }
                for (@retval) {
                    (/DeviceName/) and $numdev++;
                }
                logmsg("  Found $numdev GPU devices");

                my @d_list = ();
                for (0..($numdev-1)) {
                    push @d_list,$_;
                }

                # the driver.pl script isn't executable by default, so invoke perl explicitly
                ($command =~ /driver\.pl/) and $command = "perl $command -s 4 -bin-dir $shoc_src/bin -" . lc($framework);

                # run the NUMA tests on each device
                for my $device (@d_list) {

                    # only run on each memory node with memory local to that node
                    my $runmode = "only-mem-nodes";

                    # need to set up the tests so that they save their output appropriately
                    my $filename = "$destdir/$ident/$hn.snb.numa-gpu.out";

                    # run the command now
                    logmsg("  Starting $command -d $device >> $filename");
                    run_numa_tests("", "$command -d $device", $runmode, $filename);
                }
            }
        }

    }
}

# Parse and report on the NUMA-mem tests
if ($report) {

    # Try to 'require' the numa_mem.pm module and see if
    # we can use it properly.
    my $modname = "hw_test::numa_mem";
    eval "require($modname)";
    require Algorithm::KMeans;
    if ($@ =~ /Can't locate hw_test/) {
        print "numa_mem test module not supported.  ($modname not found)\n";
    } elsif ($@) {
        print "Error loading '$modname'.\n\n$@\n";
    }
    else {
        my $tobj = "$modname"->new($ofh);
        if ($tobj) {
            # success! save the module name and object ref
            $$href{$modname} = $tobj;
            defined $DEBUG and print
            "DEBUG: loaded $modname module, test_class=" .
            $tobj->test_class . "\n";
        }
        else {
            print "Error initializing $modname object!\n";
        }

        # Define the Gamma parameter for memory benchmark result normalization
        my $Gamma = 17066;  #MB/s, DDR3-2133 SPEC

        my $infile = "$destdir/$ident/$hn.snb.numa-bandwidth.out";
        my $havefile = 1;
        open (IN,"<$infile") or do {
            print "WARNING: Could not open $infile ($!)\n";
            $havefile = 0;
        };
        # Algorithm::KMeans will terminate the script if it can't parse the data, so
        # we only try to parse the data if there was a data file
        if ($havefile) {

            my @buffer = <IN>;
            close(IN);
            # use the numa_mem.pm-parse() to create a hash full of our data
            my $data = $tobj->parse(\@buffer);


            # digest the raw data
            # the data hash built in numa_mem.pm looks like this:
            # $data{$testname}{$cpu_location}{$mem_location}{$bin_name}->(Statistics::Descriptive object)
            #
            # let's do two things. First, create a row in the full-results table. Second, see if this result qualifies
            # as the best we've seen so we can plot it later
            my $text = "";
            my %best_results = ();
            my %full_results = (); # results for every test and every cpu/memory location
            my $num_cpu_locs = 0;
            my $num_mem_locs = 0;
            my $column_headers = "";
            my @all_data = ();
            for my $testname (keys %{$data}) {
                ($testname !~ /triad/) and next; # for now we only care about Triad

                $num_cpu_locs = keys(%{$data->{$testname}});

                for my $cpu_loc (sort {$a cmp $b} keys %{$data->{$testname}}) {

                    $num_mem_locs = keys(%{$data->{$testname}{$cpu_loc}});

                    for my $mem_loc (sort {$a cmp $b} keys %{$data->{$testname}{$cpu_loc}}) {

                        $num_cols++;
                        
                        $column_headers .= " , $cpu_loc $mem_loc";

                        for my $bin_name (sort {$a cmp $b} keys %{$data->{$testname}{$cpu_loc}{$mem_loc}}) {

                            my $statref = $data->{$testname}{$cpu_loc}{$mem_loc}{$bin_name};

                            #print "Test Name: $testname, CPU_Loc: $cpu_loc, MEM_Loc: $mem_loc, BIN_Name: $bin_name, mean value: " . $statref->mean() . "\n";
                            ($cpu_loc =~ /\w+=(\d+)/) and my $cpu_num = $1;
                            ($mem_loc =~ /\w+=(\d+)/) and my $mem_num = $1;

                            # save the result as part of the appropriate row
                            $full_results{$testname}{$bin_name} .= "," . $statref->max();

                            push (@all_data, ($statref->get_data()));

                            # save this result if it's the best we've seen so far
                            if ((!defined $best_results{$cpu_loc}{$mem_loc}) or ($best_results{$cpu_loc}{$mem_loc}{value} < $statref->max())) {
                                $best_results{$cpu_loc}{$mem_loc}{value} = $statref->max();
                                $best_results{$cpu_loc}{$mem_loc}{range} = $statref->sample_range();
                                $best_results{$cpu_loc}{$mem_loc}{binary} = $bin_name;
                            }
                                
                        }
                    }
                }
            }
            #my $num_cols = $num_cpu_locs*$num_mem_locs;

            ### use k-means to find our equivalence classes
            # the Algorithm::KMeans module wants a file containing the datapoints, so let's create a temporary file
            my $pwd = `pwd`;
            chomp($pwd);
            my $tmp_filename =  "$pwd/snb_temp.txt";
            open(KFILE, ">$tmp_filename");

            # prune out values from poor-performing executables so k-means can do a better job
            my @good_values = ();
            for my $testname (keys %{$data}) {
                ($testname !~ /triad/) and next; # for now we only care about Triad
                for my $cpu_loc (sort {$a cmp $b} keys %{$data->{$testname}}) {
                    for my $mem_loc (sort {$a cmp $b} keys %{$data->{$testname}{$cpu_loc}}) {
                        for my $bin_name (sort {$a cmp $b} keys %{$data->{$testname}{$cpu_loc}{$mem_loc}}) {

                            my $statref = $data->{$testname}{$cpu_loc}{$mem_loc}{$bin_name};
                            my @testvals = $statref->get_data();

                            for (@testvals) {
                                # only save results that are within 10% of the best value for this class of data-access
                                ($_ > (0.9*$best_results{$cpu_loc}{$mem_loc}{value})) and push @good_values, $_;
                            }
                        }
                    }
                }
            }

            # create a data file for Algorithm::KMeans to use
            #  - use dummy symbolic names because the KMeans module doesn't like duplicate names, and
            #    we use the same binary name for several results

            # as a trick for using kmeans() on datasets less of fewer than 16 samples, just create multiple
            # data points for each sample in the file (probably not the most official way of doing
            # things, but at least kmeans() doesn't break
            my $repeat = 0;
            my $counter = 0;
            if ( (@good_values) <= 1) {
                $repeat = 17;
            }
            elsif ( (@good_values) <= 4) {
                $repeat = 5;
            }
            elsif ( (@good_values) <= 8) {
                $repeat = 3;
            }
            elsif ( (@good_values) <= 16) {
                $repeat = 2;
            }

            for my $value (@good_values) {
                for (0..$repeat) {
                    print KFILE "result-$counter-$value $value\n";
                    $counter++;
                }
            }
            close(KFILE);

            
            # create the KMeans object; see http://search.cpan.org/~avikak/Algorithm-KMeans/lib/Algorithm/KMeans.pm
            my $clusterer = Algorithm::KMeans->new( 
                datafile => "$tmp_filename",
                mask     => "N1",    
                K        => 0,
    #            Kmin     => 2,
    #            Kmax     => $num_mem_locs,
    #            terminal_output => 1,
            );

            # read in the data from the temporary file we created
            $clusterer->read_data_from_file();

            # analyze the data using Algorithm::KMeans
            my ($clusters, $cluster_centers) = $clusterer->kmeans();

            # find the maximum value for each cluster found by k-means
            my @cluster_max_vals = ();
            for my $found_clusters (@$clusters) {
                my @this_cluster = ();
                for my $cluster_val (@$found_clusters) {
                    $cluster_val =~ s/result-\d+-//g;
                    push @this_cluster, $cluster_val;
                }
                my @tmp_array = sort {$b <=> $a} @this_cluster;
                push @cluster_max_vals, $tmp_array[0];
            }

            # some of the clusters that are found are really the same bandwidth class
            # take any cluster centers that are within 10% of each other and combine them
            my @our_cluster_max_vals = ();
            my $prev = 100000000;
            for (sort {$b <=> $a} @cluster_max_vals) {
                ($_ < (0.9*$prev)) and push @our_cluster_max_vals, $_;
                $prev = $_;
            }

            add_text("\\newpage\n");
            add_section("NUMA Data-Access Memory Bandwidth Characterization Results");

            add_table_init("\\textbf{Memory Data-Access Bandwidth Classes}", 2);
            add_table_row("\$\\Gamma=17066\ MB/s\$ , \\cellcolor[gray]{0.8}\\texttt{STREAM Triad}");
            my $class_num = 0;
            for my $class (sort {$b <=> $a} @our_cluster_max_vals) {
                my $classtext = "";
                if ($class_num == 0) {
                    $classtext = "\\cellcolor{snbgreen}\\textbf{Class $class_num}\\hspace{0.5em} (\$\\alpha_{m_{$class_num}}\$)";
                }
                elsif ($class_num == 1) {
                    $classtext = "\\cellcolor{snbyellow}\\textbf{Class $class_num}\\hspace{0.5em} (\$\\alpha_{m_{$class_num}}\$)";
                }
                else {
                    $classtext = "\\cellcolor{snbred}\\textbf{Class $class_num}\\hspace{0.5em} (\$\\alpha_{m_{$class_num}}\$)";
                }
                my $alpha_val = $class/$Gamma;
                add_table_row("$classtext , " . sprintf("\$\\leq\%d\$", $class) . "\\hspace{.1em} MB/s" .
                                         "\\hspace{0.5em} (" . sprintf("%.4f",$alpha_val) . ")");
                $class_num++;
            }
            #add_table_space_between_rows();
            add_table_conclusion();

            # build the full results table
            add_table_init("\\textbf{NUMA \\texttt{STREAM}\\hspace{.1em} Bandwidth Test Results} --- the best value in each column is highlighted", $num_cols+1, "3em");

            my @col_header_array = split ',',$column_headers;

            $column_headers =~ s/physcpubind=/Core~/g;
            $column_headers =~ s/cpunodebind=/Node~/g;
            $column_headers =~ s/membind=/to Node~/g;

            for my $testname (sort {$a cmp $b} keys %full_results) {

                ($testname =~ /triad/i) and add_table_spanning_row("\\cellcolor[gray]{0.8}\\textbf{STREAM Triad (MB/s)}");
                add_table_row($column_headers);

                # all of the nonsense in this loop is so that we can color the best-in-column cells
                for my $binname (sort {$a cmp $b} keys %{$full_results{$testname}}) {

                    my @row_values = split ',',$full_results{$testname}{$binname};
                    my @print_values = ();
                    my $col_num = 1;

                    for my $cell_value (@row_values) {
                        ($cell_value eq "") and next;
                        my $cpu_loc = -1;
                        my $mem_loc = -1;

                        if ($col_header_array[$col_num] =~ /\s+(.*bind=\d+)\s+(membind=\d+)/) {
                            $cpu_loc = $1;
                            $mem_loc = $2;
                        }

                        if ( ($binname eq $best_results{$cpu_loc}{$mem_loc}{binary}) and ($cell_value == $best_results{$cpu_loc}{$mem_loc}{value})) {
                            #print "found best-in-column for $binname $cpu_loc-$mem_loc: $cell_value\n";
                            my $num_classes = @our_cluster_max_vals;
                            if ($num_classes == 1) {
                                $cell_value = "\\cellcolor{snbgreen} $cell_value";
                            }
                            elsif ($num_classes == 2) {
                                if ($cell_value <= $our_cluster_max_vals[1]) {
                                    $cell_value = "\\cellcolor{snbyellow} $cell_value";
                                }
                                else {
                                    $cell_value = "\\cellcolor{snbgreen} $cell_value";
                                }
                            }
                            else {
                                if ($cell_value <= $our_cluster_max_vals[2]) {
                                    $cell_value = "\\cellcolor{snbred} $cell_value";
                                }
                                elsif ($cell_value <= $our_cluster_max_vals[1]) {
                                    $cell_value = "\\cellcolor{snbyellow} $cell_value";
                                }
                                else {
                                    $cell_value = "\\cellcolor{snbgreen} $cell_value";
                                }
                            }
                        }

                        push @print_values, " , $cell_value";
                        $col_num++;
                        ($col_num > ($num_cols+1)) and $col_num = 1;
                    }
                    add_table_row("$binname@print_values");
                }
            }
            add_table_conclusion();
            add_text("\\clearpage\n");
        }
    }
}

# Parse and report on the NUMA-gpu tests
if ($report) {

    # Try to 'require' the numa_gpu.pm module and see if
    # we can use it properly.
    my $modname = "hw_test::numa_gpu";
    eval "require($modname)";
    if ($@ =~ /Can't locate hw_test/) {
        print "numa_gpu test module not supported.  ($modname not found)\n";
    } elsif ($@) {
        print "Error loading '$modname'.\n\n$@\n";
    }
    else {
        my $tobj = "$modname"->new($ofh);
        if ($tobj) {
            # success! save the module name and object ref
            $$href{$modname} = $tobj;
            defined $DEBUG and print
            "DEBUG: loaded $modname module, test_class=" .
            $tobj->test_class . "\n";
        }
        else {
            print "Error initializing $modname object!\n";
        }

        # the Phi value for the PCIe test result normalization
        my $Phi = 12.8;  #GB/s, PCIe 2.0 SPEC (8/10 encoding of 16 GB/s)

        # the SHOC tests generate one file for each mode/device combination
        my @buffer = ();

        #@filelist = `cd $destdir/$ident;ls -1 *snb.numa-SHOC* 2>/dev/null`;
        my $infile = "$destdir/$ident/$hn.snb.numa-gpu.out";

        #$infile = "$destdir/$ident/$infile";

        my $havefile = 1;
        open (IN,"<$infile") or do {
            print "WARNING: Could not open $infile ($!)\n";
            $havefile = 0;
        };

        # Algorithm::KMeans will terminate the script if it can't parse the data, so
        # we only try to parse the data if there was a data file
        if ($havefile) {
            my @tmpbuffer = <IN>;
            push @buffer, @tmpbuffer;
            close(IN);
            # Use the numa_mem.pm-parse() to create a hash full of our data
            #
            # Note that this parse() routine expects a reference to our data hash
            # so that it can update the hash with the new data
            my $data = $tobj->parse(\@buffer);

            #print "Dump of %data" . Dumper($data) . "\n";

            # digest the raw data
            # the data hash built in numa_gpu.pm looks like this:
            # $data{$testname}{BusSpeedDownload}{$mode}{"Device $device"}{$cpu_location}{$mem_location}->(Statistics::Descriptive object)
            #
            # let's do two things. First, create a row in the full-results table. Second, see if this result qualifies
            # as the best we've seen so we can plot it later
            my $text = "";
            my %best_results = ();
            my %full_results = (); # results for every test and every cpu/memory location
            my $num_cpu_locs = 0;
            my $num_mem_locs = 0;
            my $column_headers = "";
            my @all_data = ();
            my $num_rows = 0;
            for my $testname (keys %{$data}) {

                for my $benchmark (sort {$a cmp $b} keys %{$data->{$testname}}) {

                    for my $mode (sort {$a cmp $b} keys %{$data->{$testname}{$benchmark}}) {

                        for my $device (sort {$a cmp $b} keys %{$data->{$testname}{$benchmark}{$mode}}) {

                            $num_cpu_locs = keys(%{$data->{$testname}{$benchmark}{$mode}{$device}});

                            for my $cpu_loc (sort {$a cmp $b} keys %{$data->{$testname}{$benchmark}{$mode}{$device}}) {

                                $num_mem_locs = keys(%{$data->{$testname}{$benchmark}{$mode}{$device}{$cpu_loc}});

                                for my $mem_loc (sort {$a cmp $b} keys %{$data->{$testname}{$benchmark}{$mode}{$device}{$cpu_loc}}) {

                                    my $statref = $data->{$testname}{$benchmark}{$mode}{$device}{$cpu_loc}{$mem_loc};
                        
                                    my $header_val = "$cpu_loc $mem_loc";
                                    ($column_headers !~ /$header_val/) and $column_headers .= " , $header_val";

                                    #print "Test Name: $testname, CPU_Loc: $cpu_loc, MEM_Loc: $mem_loc, BIN_Name: $bin_name, mean value: " . $statref->mean() . "\n";
                                    ($cpu_loc =~ /\w+=(\d+)/) and my $cpu_num = $1;
                                    ($mem_loc =~ /\w+=(\d+)/) and my $mem_num = $1;

                                    # save the result as part of the appropriate row
                                    $full_results{$benchmark}{$mode}{$device} .= "," . $statref->max();

                                    push (@all_data, ($statref->get_data()));

                                    # save this result if it's the best we've seen so far
                                    if ((!defined $best_results{$benchmark}{$mode}{$cpu_loc}{$mem_loc}) or ($best_results{$benchmark}{$mode}{$cpu_loc}{$mem_loc}{value} < $statref->max())) {
                                        $best_results{$benchmark}{$mode}{$cpu_loc}{$mem_loc}{value} = $statref->max();
                                        $best_results{$benchmark}{$mode}{$cpu_loc}{$mem_loc}{range} = $statref->sample_range();
                                        $best_results{$benchmark}{$mode}{$cpu_loc}{$mem_loc}{device} = $device;
                                    }
                                }
                            }
                            $num_rows++;
                        }
                    }
                }
            }
            my $num_cols = $num_cpu_locs*$num_mem_locs;

            #print "Dump of %full_results:\n" . Dumper(\%full_results) . "\n";
            #print "Dump of %best_results:\n" . Dumper(\%best_results) . "\n";

            ### use k-means to find our equivalence classes
            #
            # prune out values from poor-performing executables so k-means can do a better job
            my %good_values = ();
            for my $testname (keys %{$data}) {
                for my $benchmark (sort {$a cmp $b} keys %{$data->{$testname}}) {
                    for my $mode (sort {$a cmp $b} keys %{$data->{$testname}{$benchmark}}) {
                        for my $device (sort {$a cmp $b} keys %{$data->{$testname}{$benchmark}{$mode}}) {
                            for my $cpu_loc (sort {$a cmp $b} keys %{$data->{$testname}{$benchmark}{$mode}{$device}}) {
                                for my $mem_loc (sort {$a cmp $b} keys %{$data->{$testname}{$benchmark}{$mode}{$device}{$cpu_loc}}) {

                                    my $statref = $data->{$testname}{$benchmark}{$mode}{$device}{$cpu_loc}{$mem_loc};
                                    my @testvals = $statref->get_data();

                                    for (@testvals) {
                                        # only save results that are within 10% of the best value for this class of data-access
                                        my @new_array;
                                        $good_values{$benchmark} = \@new_array unless (exists $good_values{$benchmark});
                                        ($_ > (0.9*$best_results{$benchmark}{$mode}{$cpu_loc}{$mem_loc}{value})) and push @{$good_values{$benchmark}}, $_;
                                    }
                                }
                            }
                        }
                    }
                }
            }
            #print "Dump of %good_values:\n" . Dumper(\%good_values) . "\n";

            my %our_cluster_max_vals = ();
            my $kmeans = 0; # keep track of whether we actually complete the k-means analysis or not

            for my $benchmark (sort {$a cmp $b} keys %good_values) {

                    # create a data file for Algorithm::KMeans to use
                    #  - use dummy symbolic names because the KMeans module doesn't like duplicate names, and
                    #    we use the same binary name for several results
                    my $counter = 0;

                    # the Algorithm::KMeans module wants a file containing the datapoints, so let's create a temporary file
                    my $tmp_filename =  "snb_temp.txt";
                    open(KFILE, ">$tmp_filename");

                    # as a trick for using kmeans() on datasets less of fewer than 16 samples, just create multiple
                    # data points for each sample in the file (probably not the most official way of doing
                    # things, but at least kmeans() doesn't break
                    my $repeat = 0;
                    if ( (@{$good_values{$benchmark}}) <= 1) {
                        $repeat = 17;
                    }
                    elsif ( (@{$good_values{$benchmark}}) <= 4) {
                        $repeat = 5;
                    }
                    elsif ( (@{$good_values{$benchmark}}) <= 8) {
                        $repeat = 3;
                    }
                    elsif ( (@{$good_values{$benchmark}}) <= 16) {
                        $repeat = 2;
                    }

                    for my $value (@{$good_values{$benchmark}}) {
                        for (0..$repeat) {
                            print KFILE "result-$counter-$value $value\n";
                            $counter++;
                        }
                    }
                    close(KFILE);

                    
                    # create the KMeans object; see http://search.cpan.org/~avikak/Algorithm-KMeans/lib/Algorithm/KMeans.pm
                    my $clusterer = Algorithm::KMeans->new( 
                        datafile => "$tmp_filename",
                        mask     => "N1",    
                        #            K        => 0,
                        #Kmin     => 2,
                        #Kmax     => 3,
                        Kmax     => $num_cpu_locs,
            #            terminal_output => 1,
                    );

                    # read in the data from the temporary file we created
                    $clusterer->read_data_from_file();

                    # analyze the data using Algorithm::KMeans
                    my ($clusters, $cluster_centers) = $clusterer->kmeans();

                    # find the maximum value for each cluster found by k-means
                    my @cluster_max_vals = ();
                    for my $found_clusters (@$clusters) {
                        my @this_cluster = ();
                        for my $cluster_val (@$found_clusters) {
                            $cluster_val =~ s/result-\d+-//g;
                            push @this_cluster, $cluster_val;
                        }
                        my @tmp_array = sort {$b <=> $a} @this_cluster;
                        push @cluster_max_vals, $tmp_array[0];
                    }


                    # some of the clusters that are found are really the same bandwidth class
                    # take any cluster centers that are within 10% of each other and combine them
                    my $prev = 100000000;
                    for (sort {$b <=> $a} @cluster_max_vals) {
                        my @new_array;
                        $our_cluster_max_vals{$benchmark} = \@new_array unless (exists $our_cluster_max_vals{$benchmark});
                        ($_ < (0.95*$prev)) and push @{$our_cluster_max_vals{$benchmark}}, $_;
                        $prev = $_;
                    }
                    $kmeans = 1;
                    #print "Dump of %our_cluster_max_vals:\n" . Dumper(\%our_cluster_max_vals) . "\n";
                    system("rm $tmp_filename");
            }

            add_text("\\newpage\n");
            add_section("NUMA Data-Access GPU Bandwidth Characterization Results");
            if ($kmeans) {
                my $class_num = 0;
                my @bwclass_rows = ();
                my $header_row = "\$\\Phi=12.8\ GB/s\$";

                #add_table_spanning_row("\\cellcolor[gray]{0.7}\\texttt{$benchmark}\\hspace{.1em} Benchmark");
                for my $benchmark (sort keys %our_cluster_max_vals) {
                    $header_row .= " , \\cellcolor[gray]{0.8}\\texttt{$benchmark}";


                    for my $class (sort {$b <=> $a} @{$our_cluster_max_vals{$benchmark}}) {
                        $classtext = "";
                        if ($class_num == 0) {
                            $classtext = "\\cellcolor{snbgreen}\\textbf{Class $class_num}\\hspace{0.5em} (\$\\alpha_{p_{$class_num}}\$)";
                        }
                        elsif ($class_num == 1) {
                            $classtext = "\\cellcolor{snbyellow}\\textbf{Class $class_num}\\hspace{0.5em} (\$\\alpha_{p_{$class_num}}\$)";
                        }
                        else {
                            $classtext = "\\cellcolor{snbred}\\textbf{Class $class_num}\\hspace{0.5em} (\$\\alpha_{p_{$class_num}}\$)";
                        }

                        # calculate the alpha value for this class
                        my $alpha_val = $class/$Phi;
                        $bwclass_rows[$class_num] = "\\multicolumn{1}{|c}{$classtext}" unless (exists $bwclass_rows[$class_num]);
                        $bwclass_rows[$class_num] .= " , " . sprintf("\$\\leq\%.2f\$", $class) . "\\hspace{.1em} GB/s" . 
                                                     "\\hspace{0.5em} (" . sprintf("%.4f",$alpha_val) . ")";
                        #add_text("\\qquad $classtext: " . sprintf("\$\\leq\%.2f\$", $class) . " MB/s}\n\n");
                        $class_num++;
                    }
                    $class_num = 0;
                }
                my $num_benchmarks = keys %our_cluster_max_vals;
                add_table_init("\\textbf{GPU Data-Access Bandwidth Classes}", $num_benchmarks + 1);
                add_table_row($header_row);
                for (@bwclass_rows) {
                    add_table_row($_);
                }
                #add_table_space_between_rows();
                add_table_conclusion();
            }


            # build the full results table
            add_table_init("\\textbf{NUMA \\texttt{SHOC}\\hspace{.1em} GPU Data-Access Bandwidth Test Results} --- the best value in each column is highlighted", $num_cols+1, "3em");

            my @col_header_array = split ',',$column_headers;

            $column_headers =~ s/physcpubind=/Core~/g;
            $column_headers =~ s/cpunodebind=/Node~/g;
            $column_headers =~ s/membind=/to Node~/g;

            for my $benchmark (sort {$a cmp $b} keys %full_results) {

                add_table_spanning_row("\\cellcolor[gray]{0.7}\\textbf{\\texttt{$benchmark (GB/s)}}");

                # all of the nonsense in this loop is so that we can color the best-in-column cells
                for my $mode (sort {$a cmp $b} keys %{$full_results{$benchmark}}) {
                    add_table_spanning_row("\\cellcolor[gray]{0.9}\\textbf{" . uc($mode) . "}");
                    add_table_row($column_headers);

                    for my $device (sort {$a cmp $b} keys %{$full_results{$benchmark}{$mode}}) {

                        my @row_values = split ',',$full_results{$benchmark}{$mode}{$device};
                        my @print_values = ();
                        my $col_num = 1;

                        for my $cell_value (@row_values) {
                            ($cell_value eq "") and next;
                            my $cpu_loc = -1;
                            my $mem_loc = -1;

                            if ($col_header_array[$col_num] =~ /\s+(.*bind=\d+)\s+(membind=\d+)/) {
                                $cpu_loc = $1;
                                $mem_loc = $2;
                            }

                            if ($cell_value == $best_results{$benchmark}{$mode}{$cpu_loc}{$mem_loc}{value}) {
                                #print "found best-in-column for $binname $cpu_loc-$mem_loc: $cell_value\n";
                                if ($kmeans) {
                                    my $num_classes = @{$our_cluster_max_vals{$benchmark}};
                                    if ($num_classes == 1) {
                                        $cell_value = "\\cellcolor{snbgreen} $cell_value";
                                    }
                                    elsif ($num_classes == 2) {
                                        if ($cell_value <= $our_cluster_max_vals{$benchmark}[1]) {
                                            $cell_value = "\\cellcolor{snbyellow} $cell_value";
                                        }
                                        else {
                                            $cell_value = "\\cellcolor{snbgreen} $cell_value";
                                        }
                                    }
                                    else {
                                        if ($cell_value <= $our_cluster_max_vals{$benchmark}[2]) {
                                            $cell_value = "\\cellcolor{snbred} $cell_value";
                                        }
                                        elsif ($cell_value <= $our_cluster_max_vals{$benchmark}[1]) {
                                            $cell_value = "\\cellcolor{snbyellow} $cell_value";
                                        }
                                        else {
                                            $cell_value = "\\cellcolor{snbgreen} $cell_value";
                                        }
                                    }
                                }
                                else {
                                    $cell_value = "\\cellcolor{snbgreen} $cell_value";
                                }
                            }

                            push @print_values, " , $cell_value";
                            $col_num++;
                            ($col_num > ($num_cols+1)) and $col_num = 1;
                        }
                        add_table_row("$device@print_values");
                    }
                    #add_table_space_between_rows();
                }
                add_tabular_midstream();
            }
            add_table_conclusion();
            add_text("\\clearpage\n");
        }
    }
}
#
# do the final report generation and such
if ($report) {
	add_section("Cbench Single Node Benchmark Run Details");
	add_text_raw("Hostname of Benchmarked Node: $hn\n".
		"Cbench Test Identifier for Benchmark Run: $ident\n");

	my $tex = "$bench_test/tools/snb_report.tex.in";
	open (IN,"<$tex") or die
		"Could not open $tex ($!)";
	# set slurp mode
	undef $/;
	my $template = <IN>;
	# unset slurp
	$/ = "\n";
	close(IN);

	# title the doc
	my $tmp = "\\title{Cbench Single Node Benchmark Report for Hostname \\texttt{$hn}}";
	$template =~ s/TITLE_HERE/$tmp/gs;

	# write out the core body of the doc
	$tmp = "";
	foreach (@report_core_buf) {
		$tmp .= $_;
	}
	$tmp .= "\n";
	$template =~ s/CORE_BODY_HERE/$tmp/gs;

	# write out the LaTeX source file
	system("/bin/rm -f $destdir/snb_report_$hn.{tex,pdf,log,aux}");
	my $basename = "snb_report_$hn";
	(defined $pdftag) and $basename = "snb_report_$hn\_$pdftag";

	$tex = "$destdir/$basename.tex";
	open (OUT,">$tex") or die
		"Could not open $tex ($!)";
	print OUT $template;
	close(OUT);

	# try to generate a pdf from the latex input
	my $cmd_output = `pdflatex -interaction=nonstopmode $destdir/$basename.tex 2>&1`;
	if ($cmd_output =~ /Output written on (.*)\.pdf/) {
            print "\nCreated $1.pdf successfully.\n".
            "Check $1.log for details from pdflatex.\n\n";
        }
        elsif ($cmd_output =~ /LaTeX Error/) {
            print "$cmd_output\n";
        }
	
	# if specified save the raw pieces used to generate the pdf
	if (defined $savepdfsrc) {
		# make a temp directory to hold everything
		my $tmpdir = "/tmp\/$ident";
		mkdir "$tmpdir";
		my @list = (
			"\*.ps",
			"\*.dat",
			"\*.cmd",
			"$basename.tex",
			"snb.$hn.$ident.log",
			"$ident\/$hn\.snb\.\*\.out",
		);
		foreach $f (@list) {
			#print("rsync $f $tmpdir/.\n");
			system("rsync $f $tmpdir/.");
		}
		system("cd /tmp;tar cfz $basename.tgz $ident;/bin/mv -f $basename.tgz $destdir/$basename.tgz");
		system("/bin/rm -rf $tmpdir");
		print "Saved pdf source files in $destdir/$basename.tgz .\n";
	}
}
else {
	logmsg("Finished running the Single Node Benchmarks");
	my $msg = "To generate a report: ".
		"$ENV{'CBENCHOME'}/tools/single_node_benchmark.pl --report ".
		"--node $hn --ident $ident --destdir $destdir\n";
	logmsg($msg);
}
close(LOG);


################################################################
################################################################
########## subroutines

sub addchange_envvar {
	my $buf = shift;
	my $varbase = shift;
	my $value = shift;

	#print ("$$buf\n");
	if ($$buf =~ /[\n]*$varbase\=/) {
		#print "DEBUG:addchange_envvar() varbase found...editing\n";
		$$buf =~ s/([\n]*)$varbase\=.*\n/$1$varbase\=$value\n/g;
	}
	else {
		#rint "DEBUG:addchange_envvar() varbase not found...adding\n";
		$$buf .= "$varbase"."=$value\n";
	}
	#print ("$$buf\n");
}


sub add_list {
	my $name = shift;
	my $list = shift;

	my $text = "$name\n\\begin{itemize}\n";
	foreach (@$list) {
		$text .= "  \\item $_\n";
	}
	$text .= "\\end{itemize}\n";
	push @report_core_buf, $text;
}

sub add_section {
	my $sect = shift;

	push @report_core_buf, "\\section{$sect}\n";
}

sub add_subsection {
	my $subsect = shift;

	push @report_core_buf, "\\subsection{$subsect}\n";
}

sub add_text {
	my $text = shift;

	push @report_core_buf, "$text";
}

sub add_text_raw {
	my $text = shift;

	push @report_core_buf, "\\begin{verbatim}\n$text\\end{verbatim}\n";
}

sub add_figure {
	my $file = shift;
	my $name = shift;
	my $label = shift;

	my ($base,$suf) = $file =~ /(\S+)\.(\S+)$/;
	if (! -f "$destdir/$base.pdf") {
		print "WARNING:add_figure() $base.pdf doesn't exist...not adding figure\n";
		push @report_core_buf, "\nFigure \'$name\' not available.\n\n";
		return;
	}

	my $text = "\n".
"\\begin{figure}[h]\n".
"  \\begin{center}\n".
"  \\includegraphics[scale=0.6]{$file}\n".
"  \\caption{$name}\n".
"  \\label{fig:$label}\n".
"  \\end{center}\n".
"\\end{figure}\n".
"\\clearpage\n";

	push @report_core_buf, "$text";
}

sub add_table_init {

    my $caption = shift;
    $table_num_columns = shift; # declare as global so that other table subroutines can use it
    my $col_width = shift; # optional, if used the data cells will be set to use this width
    my $init_text = "";

    # RKB: The narrow environment allows us to shift a figure into the left margin.
    # However, it is only available in newer distributions of TeXLive and therefore
    # isn't included until I decide whether it's worth creating the dependency.
#    if ($table_num_columns > 16) {
#        $init_text .= "\\begin{narrow}{-.5cm}{0cm}\n";
#        $narrow_env = 1;
#    }

    $init_text .= "\\begin{flushleft}\n";
    $init_text .= "\\begin{table}[hptb!]\n";
    $init_text .= "\\captionsetup{singlelinecheck=off}\n"; # to allow the table caption to be left-justified
    $init_text .= "\\caption{$caption}\n";
    $init_text .= "\\begin{tabular}{";

    $tabular_args = "|r|";
    for my $col (1..($table_num_columns-1)) {
        if (defined $col_width) {
            $tabular_args .= ">{\\centering}m{$col_width}|";
        }
        else {
            $tabular_args .= "c|";
        }
    }
    $init_text .= "$tabular_args}\n";
    $init_text .= "\\hline\n";

    #print "init_text: $init_text\n";
    push @report_core_buf, $init_text;
}

sub add_table_row {
    # expects a CSV *with spaces before and after each comma* for a row
    my $row = shift;
    $row =~ s/ , / \& /g;

    push @report_core_buf, "$row\\tabularnewline \\hline\n";
}

sub add_table_spanning_row {
    my $cell_text = shift;

    my $spanning_text .= "\\cline{1-$table_num_columns}\n";
    $spanning_text .= "\\cline{1-$table_num_columns}\n";
    $spanning_text .= "\\multicolumn{$table_num_columns}{|l|}{$cell_text}\\\\ \\hline\n";
    #$spanning_text .= "\\multicolumn{" . ($table_num_columns) . "}{|l|}{$cell_text}\\\\ \\hline \\hline\n";

    push @report_core_buf, $spanning_text;
}

sub add_table_conclusion {
    my $concl_text .= "\\end{tabular}\n";
    $concl_text .= "\\end{table}\n";
    $concl_text .= "\\end{flushleft}\n";

    # RKB: see comment in add_table_init()
#    if ($narrow_env) {
#        $concl_text .= "\\end{narrow}\n";
#    }

    push @report_core_buf, $concl_text;
}

sub add_table_space_between_rows {
    # create an empty spanning row with its newline spacing adjusted to make the row thin
    my $space_between_rows = "\\multicolumn{$table_num_columns}{c}{}\\\\[-0.5em]\\hline\n";
    push @report_core_buf, "$space_between_rows";
}

sub add_tabular_midstream {
    my $newtab = "\\end{tabular}\n" .
                 "\\qquad\n" .
                 "\\begin{tabular}{$tabular_args}\n";

    push @report_core_buf, "$newtab";
}

sub build_gnuplot_graph {
	my $fileid = shift;
	my $title = shift;
	my $xlabel = shift;
	my $ylabel = shift;
	my $href = shift;
	my $options = shift;

	# remove old plot files
	system("/bin/rm -f $fileid.{ps,jpg,pdf}");

	open (PLOT, ">$fileid.dat");
	open (CMD, ">$fileid.cmd");

	# build the gnuplot command file we'll run
	print CMD
		"set ylabel \"$ylabel\"\n" .
		"set xlabel \"$xlabel\"\n" .
		"set grid\n" .
		"set title \"$title\"\n" .
		"set term postscript color\n" .
		"set output \"$fileid.ps\"\n";
	
	if (defined $options) {
		foreach (@$options) {
			print CMD "$_\n";
		}
	}

	print CMD "plot ";
	for my $x (sort {$a <=> $b} (keys %$href) ) {
		print PLOT "$xlabel ";
		$keyindex = 2;
		my $numseries = scalar keys(%{$href->{$x}});
		for my $series (sort {$a cmp $b} (keys %{$href->{$x}}) ) {
			print CMD "\"$fileid.dat\" using 1:$keyindex title \"$series\" with lp";
			print PLOT "$series ";
			print CMD ", " unless ($keyindex-1 == $numseries);
			$keyindex++;
		}
		last;
	}
	print CMD "\n";
	print PLOT "\n";

	print CMD
		"set term png\n" .
		"set output \"$fileid.png\"\n" .
		"replot\n" ;

	my $xrm = 
		"-xrm \'gnuplot*line1Color: red\' ".
		"-xrm \'gnuplot*line2Color: green\' ".
		"-xrm \'gnuplot*line3Color: DarkSlateGrey\' ".
		"-xrm \'gnuplot*line4Color: magenta\' ".
		"-xrm \'gnuplot*line5Color: cyan\' ".
		"-xrm \'gnuplot*line6Color: blue\' ".
		"-xrm \'gnuplot*line7Color: orange\' ".
		"-xrm \'gnuplot*line8Color: coral\'";

	my $cmd = "gnuplot $xrm $fileid.cmd";

	# record the command we executed in the gnuplot command file for posterity
	print CMD "\n\# gnuplot command line\n\# $cmd\n";

	# we are done building the command file
	close(CMD);

	# build the data file
	for my $x (sort {$a <=> $b} (keys %$href) ) {
		print PLOT "$x ";
		for my $series (sort {$a cmp $b} (keys %{$href->{$x}}) ) {
			print PLOT $href->{$x}{$series} . " ";
		}
		print PLOT "\n";
	}
	close(PLOT);

	# now execute gnuplot
	(defined $DEBUG) and print "DEBUG:build_gnuplot_graph(): $cmd\n";
	system "$cmd 1>/dev/null 2>&1";

	# generate a pdf from the ps file (hopefully) built by gnuplot
	my $fstats = stat("$fileid.ps");
	if (defined $fstats and $fstats->size > 50) {
		system("ps2pdf $fileid.ps");
	}
	else {
		print "WARNING:build_gnuplot_graph() The generated $fileid.ps seems to be bogus...\n";
	}
}


sub build_gnuplot_histogram {
	my $fileid = shift;
	my $title = shift;
	my $xlabel = shift;
	my $ylabel = shift;
	my $href = shift;
	my $options = shift;

	# we have to have Gnuplot 4.1 or greater for histograms... check for it
	my $tmpbuf = `gnuplot -V`;
	my ($gnuplot_ver) = $tmpbuf =~ /gnuplot\s+(\S+)\s+/;
	if ($gnuplot_ver < 4.1) {
		print "WARNING:build_gnuplot_histogram() requires Gnuplot version 4.1 or greater!\n";
		return;
	}

	# remove old plot files
	system("/bin/rm -f $fileid.{ps,jpg,pdf}");

	open (PLOT, ">$fileid.dat");
	open (CMD, ">$fileid.cmd");

	# build the gnuplot command file we'll run
	print CMD
		"set ylabel \"$ylabel\"\n" .
		"set xlabel \"$xlabel\"\n" .
		"set grid\n" .
		"set title \"$title\"\n" .
		"set term postscript color\n" .
		"set output \"$fileid.ps\"\n".
		"set key outside below right\n".
		"set yrange [0:*]\n".
	    "# histogram specific stuff\n".
		"set auto x\n".
		"set style histogram clustered gap 1 title  offset character 0, 0, 0\n".
		"set style fill   solid 1.00 border -1\n".
		"set datafile missing \'\-\'\n".
		"set style data histograms\n";
		#"set xtics border in scale 1,0.5 nomirror rotate by 0  offset character 0, 0, 0\n".
		#set boxwidth 0.9 absolute

	if (defined $options) {
		foreach (@$options) {
			print CMD "$_\n";
		}
	}

	print CMD "plot ";
	for my $x (sort {$a <=> $b} (keys %$href) ) {
		print PLOT "\"$xlabel\" ";
		$keyindex = 2;
		my $numseries = scalar keys(%{$href->{$x}});
		#plot 'linpack.dat-custom' using 2:xtic(1) ti col, '' u 3 ti col, '' u 4 ti col
		for my $series (sort {$a <=> $b} (keys %{$href->{$x}}) ) {
			print CMD "\"$fileid.dat\" using $keyindex:xtic(1) ti col";
			print PLOT "\"$series threads\" ";
			print CMD ", " unless ($keyindex-1 == $numseries);
			$keyindex++;
		}
		last;
	}
	print CMD "\n";
	print PLOT "\n";

#	print CMD
#		"set term png\n" .
#		"set output \"$fileid.png\"\n" .
#		"replot\n" ;

	my $xrm = 
		"-xrm \'gnuplot*line1Color: red\' ".
		"-xrm \'gnuplot*line2Color: green\' ".
		"-xrm \'gnuplot*line3Color: DarkSlateGrey\' ".
		"-xrm \'gnuplot*line4Color: magenta\' ".
		"-xrm \'gnuplot*line5Color: cyan\' ".
		"-xrm \'gnuplot*line6Color: blue\' ".
		"-xrm \'gnuplot*line7Color: orange\' ".
		"-xrm \'gnuplot*line8Color: coral\'";

	my $cmd = "gnuplot $xrm $fileid.cmd";

	# record the command we executed in the gnuplot command file for posterity
	print CMD "\n\# gnuplot command line\n\# $cmd\n";

	# we are done building the command file
	close(CMD);

	# build the data file
	for my $x (sort {$a <=> $b} (keys %$href) ) {
		print PLOT "$x ";
		for my $series (sort {$a <=> $b} (keys %{$href->{$x}}) ) {
			print PLOT $href->{$x}{$series} . " ";
		}
		print PLOT "\n";
	}
	close(PLOT);

	# now execute gnuplot
	(defined $DEBUG) and print "DEBUG:build_gnuplot_histogram(): $cmd\n";
	system "$cmd 1>/dev/null 2>&1";

	# generate a pdf from the ps file (hopefully) built by gnuplot
	my $fstats = stat("$fileid.ps");
	if (defined $fstats and $fstats->size > 50) {
		system("ps2pdf $fileid.ps");
	}
	else {
		print "WARNING:build_gnuplot_histogram() The generated $fileid.ps seems to be bogus...\n";
	}
}


sub ps2pdf {
	my $file = shift;

	# generate a pdf from the ps file (hopefully) built by gnuplot
	my $fstats = stat("$file");
	if (defined $fstats and $fstats->size > 50) {
		system("ps2pdf $file");
	}
	else {
		print "WARNING:ps2pdf() The generated $file seems to be bogus...\n";
	}
}


sub runcmd {
	my $cmd = shift;
	my $cmdtag = shift;
	my $options = shift;

	my $echo = 0;
	my $finalcmd = $cmd;
	(defined $DEBUG) and $echo = 1;

        # some commands generate files instead of text output
        if (defined $options and $options =~ /file/) {
            if ($cmd =~ /lstopo/) {
                runhwloc($cmd);
            }
        }
        else {
            # need to save the output intelligently
            if (defined $options and $options =~ /overwrite/) {
                    $finalcmd .= " > $destdir/$ident/$hn.snb.$cmdtag.out 2>&1";
            }
            else {
                    $finalcmd .= " >> $destdir/$ident/$hn.snb.$cmdtag.out 2>&1";
            }

            if (defined $options and $options =~ /nosave/) {
                    logmsg("RUNCMD: $cmd",$echo);
                    #system("$cmd") unless defined $dryrun;
                    snb_fork("$cmd") unless defined $dryrun;
            }
            else {
                    logmsg("RUNCMD: $finalcmd",$echo);
                    #system("$finalcmd") unless defined $dryrun;
                    snb_fork("$finalcmd") unless defined $dryrun;
            }
        }
        ($main::INTsignalled) and exit(1);
}

sub snb_fork {

    my $cmd = shift;

    # use fork so that we can kill the child command if necessary
    my $pid = fork();
    if (not defined $pid) {
        print "resources not avilable.\n";
    } elsif ($pid == 0) {
        exec("exec $cmd"); # the IO redirection in $cmd will cause Perl to create a 
                           # sub-process unless 'exec' is prepended to the command
                           # http://stackoverflow.com/questions/2965067/problem-with-fork-exec-kill-when-redirecting-output-in-perl
        exit(0);
    } else {
        $main::childpids{$pid} = 1;
        waitpid($pid,0);
    }
    delete($main::childpids{$pid}); # don't need to try to kill children that have finished
}

sub logmsg {
	my $msg = shift;
	my $echo = shift;

	my $txt = get_log_timestamp()." $msg\n";
	print LOG $txt;
	print $txt unless (defined $echo and $echo == 0);
}

sub get_file_timestamp {
	my ($sec, $min, $hour, $day, $mon, $year, $wday, $yday, $isdst) = localtime;
    
    $year = $year + 1900;
    $stamp = sprintf "%04d-%02d-%02d_%02d:%02d:%02d",$year,$mon+1,$day,$hour,$min,$sec;
    return $stamp;
}

sub get_log_timestamp {
	my ($sec, $min, $hour, $day, $mon, $year, $wday, $yday, $isdst) = localtime;
    
    $year = $year + 1900;
    $stamp = sprintf "%04d/%02d/%02d %02d:%02d:%02d",$year,$mon+1,$day,$hour,$min,$sec;
    return $stamp;
}

sub runhwloc {
    my $cmd = shift;

    # Generate either a PDF or text file containing the memory hierarchy for a node
    # default to txt
    my $suffix = "txt";

    # the lstopo help file shows avaliable file formats based on how it was configured and built
    my $lstopo_help = `$cmd --help 2>&1`;
    
    # if it says it can make an xml file, do it (that way we can generate other output file types later)
    if ($lstopo_help =~ /Supported output file formats:.*xml/) {
        $suffix = "xml";
    }
    my $finalcmd = "$cmd $destdir/$ident/$hn.snb.lstopo.$suffix";

    logmsg("RUNCMD: $finalcmd",$echo);
    system("$finalcmd") unless defined $dryrun;

    # if it says it can make a pdf, make a pdf
    if ($lstopo_help =~ /Supported output file formats:.*pdf.*/) {
        $suffix = "pdf";
    }

    $finalcmd = "$cmd $destdir/$ident/$hn.snb.lstopo.$suffix";

    logmsg("RUNCMD: $finalcmd",$echo);
    system("$finalcmd") unless defined $dryrun;
}

sub usage {
    print "USAGE: $0 \n" .
    "Cbench utility to benchmark a single node and generate a LaTeX report of the results\n" .
    "\n" .
    " General Cbench Options:\n" .
    "   --tests <regex>     Run only tests whose test name is included in the\n".
    "                       provided regex string. For example:\n".
    "                         --tests 'stream|cachebench|linpack|numa-mem|numa-gpu'\n".
    "   --ident <string>    Identifier for the test group\n" .
    "   --binident <string> Identifier for the set of binaries to use.\n" .
    "                       Maps to $CBENCHTEST/<binident> .\n".
    "   --numcpus <num>     Override the auto-detection of the number of CPU\n".
    "                       cores\n".
    "   --dryrun            Do everything but actually run the tests\n" .
    "   --quiet             Output as little as possible during run\n".
    "   --debug <level>     Turn on debugging at the specified level\n" .
    "\n" .
    " Single Node Benchmark Options:\n" .
    "   --destdir           Specify the desitnation directory for the *.snb*.out files\n" .
    "   --run               Actually run the tests, if defined (default=defined)\n" .
    "   --report            Generate a report, if defined (default=undef)\n" .
    "   --savepdfsrc        Save intermediate files when generating report, if defined (default=undef)\n" .
    "   --pdftag            An arbitrary tag appended to the report pdf filename\n" .
    "   --node              The hostname of a specific node that is to be tested\n" .
    "   --help              Print this help information\n" .
    "   --nodetonode        Run NUMA tests from each memory node to each memory nodes (default)\n" .
    "   --coretonode        Run NUMA tests from each core to each memory node\n" .
    "";

# RKB: I think these would be useful features to have in the SNB script (particularly since
# they're supported by node_hw_test)
#    "   --iterations <num> Number of test iterations\n" .
#    "   --exclude <regex>  Do NOT run hw_test modules that match the\n" .
#    "                      the specified regex string. For example,\n" .
#    "                         --exclude streams\n" .
#    "                      would only run the streams hw_test module\n" .
#    "   --maxmem <num>     Override the auto-detection of free memory to be\n".
#    "                      used in testing. The value is the number of megabytes.\n".
#    "                      For example,\n".
#    "                         --maxmem 1024\n".
#    "                      would only use 1024MB or 1GB of memory for any tests\n".
#    "                      that utilize free memory detection.\n".
#    "   --memory_util_factors  Override the cluster.def \@memory_util_factors array.\n".
#    "                          For example:\n".
#    "                            --memory_util_factors 0.10,0.77,0.85\n".
}

sub run_numa_tests {
    my $prefix = shift;
    my $test = shift;
    my $mode = shift;
    my $filename = shift;
    my $date = `date +%d%b%Y_%H%M`;
    chomp($date);

    debug_print(3,"DEBUG:In run_numa_tests()\n");
    debug_print(3,"DEBUG:  prefix: $prefix\n");
    debug_print(3,"DEBUG:  test: $test\n");
    debug_print(3,"DEBUG:  mode: $mode\n");
    debug_print(3,"DEBUG:  filename: $filename\n");

    # find numactl
    my $numactl = "numactl";

    #   look for numactl in our current path
    my $ret = `which $numactl`;
    if ($ret =~ /^which: no/ or $ret =~ /^$/) {
        # maybe it's in /usr/bin
        if (-e "/usr/bin/numactl") {
            $numactl = "/usr/bin/numactl";
        }
        # can't find it - abort this subroutine
        else {
            print STDERR "run_numa_tests(): can't find $numactl\n";
            return;
        }
    }
    debug_print(3, "DEBUG:  using $numactl\n");

    # check numactl's capabilities
    $ret = `$numactl 2>&1`;
    my $bind_process_to_node = "cpunodebind";
    ($ret =~ /--cpubind=/) and $bind_process_to_node = "cpubind";
    if (($ret !~ /membind/) or ($ret !~ /preferred/) or ($ret !~ /physcpubind=/)) {
        print STDERR "run_numa_tests(): some functionality of $numactl is missing\n";
        return;
    }

    # since we're using numactl, gather the number of nodes and cores that numactl sees
    my $numa_show = `$numactl --show 2>&1`;
    my $numa_hardware = `$numactl --hardware 2>&1`;
    my $numa_max_node = 1;
    my $numa_max_core = 1;
    my @cores = ();
    my @nodes = ();
    ($numa_show =~ /physcpubind: (.*)\n/) and @cores = split(' ',$1);
    ($numa_show =~ /nodebind: (.*)\n/) and @nodes = split(' ',$1);
    $numa_max_node = pop(@nodes);
    $numa_max_core = pop(@cores);
    debug_print(3, "DEBUG:  numa_max_core: $numa_max_core\n");
    debug_print(3, "DEBUG:  numa_max_node: $numa_max_node\n");

    system("echo `date` >> $filename");
    # run the command according to the requested mode
    if ($mode eq "node-to-node") {
        debug_print(3, "DEBUG:  Running node-to-node tests\n");
        # run the test command running on each memory node with its memory on each memory node
        for my $cpu_node (0..$numa_max_node) {
            for my $mem_node (0..$numa_max_node) {
                my $command = "$prefix $numactl --$bind_process_to_node=$cpu_node --membind=$mem_node $test";
                debug_print(3, "DEBUG: run_numa_test() command: $command\n");
                system("echo \"CBENCH RUN_NUMA_TEST COMMAND: $command\" >> $filename");
                snb_fork("$command >> $filename 2>&1") unless defined $dryrun;
            }
        }
    }
    elsif ($mode eq "core-to-node") {
        debug_print(3, "DEBUG:  Running core-to-node tests\n");

        # run the test command running on each core with its memory on each memory node
        for my $core (0..$numa_max_core) {
            for my $mem_node (0..$numa_max_node) {
                my $command = "$prefix $numactl --physcpubind=$core --membind=$mem_node $test";
                debug_print(3, "DEBUG: run_numa_test() command: $command\n");
                system("echo \"CBENCH RUN_NUMA_TEST COMMAND: $command\" >> $filename");
                snb_fork("$command >> $filename 2>&1") unless defined $dryrun;
            }
        }
    }
    elsif ($mode eq "only-mem-nodes") {
        debug_print(3, "DEBUG:  Running only-mem-nodes tests\n");
        # run the test command running on each memory node with its memory on the same memory node
        # (memory is only ever local to the process; this expedites tests such as GPU tests)
        for my $mem_node (0..$numa_max_node) {
            my $command = "$prefix $numactl --$bind_process_to_node=$mem_node --membind=$mem_node $test";
            debug_print(3, "DEBUG: run_numa_test() command: $command\n");
            system("echo \"CBENCH RUN_NUMA_TEST COMMAND: $command\" >> $filename");
            snb_fork("$command >> $filename 2>&1") unless defined $dryrun;
        }
    }
    else {
        print STDERR "run_numa_tests(): Argument 3 must be either 'node-to-node' or 'core-to-node'\n";
        return;
    }

}

sub run_multithreaded_numa_tests {

    my $test = shift;
    my $filename = shift;
    my $date = `date +%d%b%Y_%H%M`;
    chomp($date);
    my $selfname = "run_multithreaded_numa_tests()";

    debug_print(3,"DEBUG:In $selfname\n");
    debug_print(3,"DEBUG:  test: $test\n");
    debug_print(3,"DEBUG:  filename: $filename\n");

    # find numactl
    my $numactl = "numactl";

    #   look for numactl in our current path
    my $ret = `which $numactl`;
    if ($ret =~ /^which: no/ or $ret =~ /^$/) {
        # maybe it's in /usr/bin
        if (-e "/usr/bin/numactl") {
            $numactl = "/usr/bin/numactl";
        }
        # can't find it - abort this subroutine
        else {
            print STDERR "$selfname: can't find $numactl\n";
            return;
        }
    }
    debug_print(3, "DEBUG:  using $numactl\n");

    # check numactl's capabilities
    $ret = `$numactl 2>&1`;
    my $bind_process_to_node = "cpunodebind";
    ($ret =~ /--cpubind=/) and $bind_process_to_node = "cpubind";
    if (($ret !~ /membind/) or ($ret !~ /preferred/) or ($ret !~ /physcpubind=/)) {
        print STDERR "$selfname: some functionality of $numactl is missing\n";
        return;
    }

    # since we're using numactl, gather the number of nodes and cores that numactl sees
    my $numa_show = `$numactl --show 2>&1`;
    my $numa_hardware = `$numactl --hardware 2>&1`;
    my $numa_max_node = 1;
    my $numa_max_core = 1;
    my @cores = ();
    my @nodes = ();
    ($numa_show =~ /physcpubind: (.*)\n/) and @cores = split(' ',$1);
    ($numa_show =~ /nodebind: (.*)\n/) and @nodes = split(' ',$1);
    $numa_max_node = pop(@nodes);
    $numa_max_core = pop(@cores);
    my $cores_per_mem_node = ($numa_max_core + 1) / ($numa_max_node + 1);
    debug_print(3, "DEBUG:  numa_max_core: $numa_max_core\n");
    debug_print(3, "DEBUG:  numa_max_node: $numa_max_node\n");
    debug_print(3, "DEBUG:  cores_per_mem_node: $cores_per_mem_node\n");

    system("echo `date` >> $filename");

    # Run the multi-threaded test between memory nodes
    debug_print(3, "DEBUG:  Running node-to-node tests\n");
    # run the test command running on each memory node with its memory on each memory node
    for my $cpu_node (0..$numa_max_node) {
        for my $mem_node (0..$numa_max_node) {
            my $command = "$ENV{MPIHOME}/bin/mpirun -np 0 $numactl --$bind_process_to_node=$cpu_node " .
                          "--membind=$mem_node $test";
#            my $delta = 1000000;
#            my $prev_result = 0;
#            my $curr_result = 0;
#            my $threshold = 0;      # the idea with the threshold is to allow an arbitrary cutoff for 
#                                    # increasing the number of threads
            #my $np = 1;
            
            #while ($delta > 0.0) and ($delta > $threshold) {

            # run the MPI STREAM binary using increasing thread counts up to 
            # one more than then number of cores on a memory node so that
            # we can see the dropoff occur
            for (my $np = 1; $np <= ($cores_per_mem_node+1); $np++) {
                $command =~ s/-np \d+/-np $np/g;
                debug_print(3, "DEBUG: $selfname command: $command\n");
                system("echo \"CBENCH RUN_NUMA_TEST COMMAND: $command\" >> $filename");
                snb_fork("$command >> $filename 2>&1") unless defined $dryrun;
            }
            #};
        }
    }
    # will need to deal with this stuff to get the multi-threaded stream results
#    # need this for building mpi job launches
#    my $funcname = "$joblaunch_method\_joblaunch_cmdbuild";
#    *func = \&$funcname;
#
#    for my $np (1..$numcores) {
#        system("echo '====> $np processes' >> $destdir/$ident/$hn.snb.mpistreams.out");
#        my $jobcmd = func($np,$procs_per_node,1);
#        $jobcmd .= "$binpath/hwtests/stream-mpi";
#        runcmd("$jobcmd","mpistreams");
#    }

}

