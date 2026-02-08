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

# pass_through lets "non options" stay in ARGV w/o raising an error
Getopt::Long::Configure("pass_through");

GetOptions( 'ident=s' => \$ident,
			'background|bg' => \$background,
            'batch' => \$batch,
            'nodebatch' => \$nodebatch,
			'maxprocs=i' => \$maxprocs,
			'minprocs=i' => \$minprocs,
			'procs=i' => \$procs,
			'minnodes=i' => \$minnodes,
			'maxnodes=i' => \$maxnodes,
			'nodes=i' => \$nodes,
            'remote' => \$remote,
			'batchargs=s' => \$batchargs,
            'nodelist=s' => \$nodelist,
            'nodefile=s' => \$nodefile,
            'offloadmap=s' => \$offloadmap,
            'ignorenodes|x=s' => \$ignorenodes,
            'preamble=s' => \$preamble,
			'jobtemplate=s' => \$jobtemplate,
            'match=s' => \$match,
            'exclude=s' => \$exclude,
            'class=s' => \$class,
            'dryrun|dry-run' => \$DRYRUN,
			'debug:i' => \$DEBUG,
            'help' => \$help,
          );

if (defined $help) {
    usage();
    exit;
}

(!defined $ident) and $ident = $cluster_name . "1";

if (!defined $remote and !defined $batch and !defined $nodebatch) {
    die "ERROR: --batch or --nodebatch or --remote parameter required\n";
}

#
# can uncomment if there is a real reason for this, 
# but this doesn't allow --remote --nodelist MYNODE to run
# -cdm4hp
#
#if ((defined $nodebatch and ! defined $nodelist) or
#	(!defined $nodebatch and defined $nodelist)) { 
#    die "ERROR: --nodebatch and --nodelist must be used together\n";
#}

my $pwd = `pwd`;
chomp $pwd;
my $testset = 'nodehwtest';
my $bench_test = get_bench_test();
my $testset_path = "$bench_test/$testset";
(! -d "$testset_path/$ident") and mkdir "$testset_path/$ident",0750;
chdir "$testset_path/$ident";
my $datenow = `date`;
chomp $datenow;
my $nodecmd = '';

# the master list (not a Perl list though) of nodes to run on, we'll
# be updating this several times potentially
my %nodehash = ();

# read in the test identifier data telling us what nodes to
# run the tests on
# save the node list information into the test ident directory
if (defined $nodelist) {
	pdshlist_to_hash($nodelist,\%nodehash);
}
elsif (defined $nodefile) {
	open (IN,"<$nodefile") or
		die "Could not open $nodefile ($!)";
	while (<IN>) {
		chomp $_;
		$nodehash{$_} = 1;
	}
	close(IN);
}
#elsif (!defined $batch) {
elsif (-f "$testset_path/$ident/nodelist") {
	my $infile = "$testset_path/$ident/nodelist";
	open (IN,"<$infile") or die
		"Could not read $infile ($!)";
	while (<IN>) {
		if (/nodelist=(\S+)$/) {
			$nodelist = $1;
			(defined $DEBUG) and print "DEBUG: ".
				"nodelist = $nodelist\n";
		}
		pdshlist_to_hash($nodelist,\%nodehash);
	}
	close(IN);
} 
else {
	die "Could not initialize a node list to run on!"
}

# if the --ignorenodes (aka -x) parameter is given, we need to exclude the
# nodes specified (as a pdsh style list) from the nodes we will eventually
# start nodehwtest activity on
if (defined $ignorenodes) {
	# convert the ignore list to a hash, then exclude from the master
	# node hash
	my %ignorehash = ();
	pdshlist_to_hash($ignorenodes,\%ignorehash);
	foreach $n (keys %ignorehash) {
		if (exists $nodehash{$n} and $nodehash{$n} == 1) {
			# the node is in the master list, so flag it
			# as excluded
			$nodehash{$n} = 0xdead;
			(defined $DEBUG) and print "DEBUG: ".
				"excluding node = $n\n";
		}
	} 
}

# how many nodes will we be running tests on?
# in --nodebatch mode, this is just the count of the %nodehash.
# in --batch mode, we have to do some figuring.
my $numtestnodes = 0;
#if (!defined $batch) {
	foreach my $node (keys %nodehash) {
		($nodehash{$node} == 1) and $numtestnodes++;
	}
#}
#else {
#	if (defined $procs) {
#		$numtestnodes = int ($procs / $procs_per_node);
#		($numtestnodes == 0) and $numtestnodes = 1;
#	}
#	elsif (defined $maxprocs) {
#		$numtestnodes = int ($maxprocs / $procs_per_node);
#		($numtestnodes == 0) and $numtestnodes = 1;
#	}
#	elsif (defined $nodes) {
#		$numtestnodes = $nodes;
#	}
#	elsif (defined $maxnodes) {
#		$numtestnodes = $maxnodes;
#	}
#	else {
#		$numtestnodes = $max_nodes;
#	}
#
#	# to make the block of code below abled to deal with --nodebatch and
#	# cases, we put some dummy info in the %nodehash array.
#	for (1..$numtestnodes) {
#		$nodehash{"dummy$_"} = "dummy";
#	}
#}
(defined $DEBUG) and print "DEBUG: numtestnodes=$numtestnodes\n";

# If an offload map file was given, life becomes a good deal more difficult.
# We have to carve up the nodelist in the test identifier and then be mindful
# of nodes we are supposed to ignore.
my $num_per_offload = $numtestnodes;
if (defined $offloadmap) {
	$infile = "$pwd/$offloadmap";
	($offloadmap =~ /\//) and $infile = $offloadmap;
	open (IN,"<$infile") or die
		"Could not read $infile ($!)";
	while (<IN>) {
		(/^\#/) and next;
		if (/(\S+)\s+(.*)$/) {
			my $ident = $1;
			my @nodes = split(',',$2);
			(defined $DEBUG and $DEBUG > 1) and print "DEBUG: ".
				"ident=$ident offload list=".join(',',@nodes)."\n";
			@{$offloadnodes{$ident}} = @nodes;
		}
	}
	close(IN);

	# figure out how many nodes that will be running node hw tests belong
	# to each offload node
	(!exists $offloadnodes{$ident}) and
		die "No entry in offloadmap for ident $ident\n";
	$num_per_offload = int ($numtestnodes / scalar(@{$offloadnodes{$ident}}));
	(defined $DEBUG) and print "DEBUG: num offload nodes=".
		scalar(@{$offloadnodes{$ident}}) ."\n";

	# if the number of nodes doesn't divide evenly we have to add extra
	# to make sure we get everything
	if (($numtestnodes % scalar(@{$offloadnodes{$ident}})) != 0) {
		my $delta = $numtestnodes - (scalar(@{$offloadnodes{$ident}}) * $num_per_offload);
		(defined $DEBUG) and print "DEBUG: ".
			"$delta extra nodes from num_per_offload calculation\n";
		$num_per_offload += $delta;
	}

	(defined $DEBUG) and print "DEBUG: ident=$ident offload list=".
		join(',',@{$offloadnodes{$ident}})." num_per_offload=$num_per_offload\n"; 
}
else {
	# build the command we will execute on each node, i.e. to run node_hw_test
	$nodecmd = build_nodehwtest_cmdline(undef,"$bench_test/$testset/node_hw_test");
	#$nodecmd .= "$bench_test/$testset/node_hw_test ";
	#$nodecmd .= "--ident $ident ";
	#$nodecmd .= join(' ',@ARGV);
	#(defined $match) and $nodecmd .= " --match \'$match\' ";
	#(defined $exclude) and $nodecmd .= " --exclude \'$exclude\' ";
	#(defined $class) and $nodecmd .= " --class \'$class\' ";
	defined $DEBUG and print "DEBUG: node command = $nodecmd\n";
}

# We have to do somewhat different work to startup the node level hw tests
# in a batch versus nodebatch mode versus a remote execution mode versus a
# remote execution mode with offload
if (defined $nodebatch or defined $batch) {
	# make sure the directory is there with the proper test identification
	(! -d "$testset_path\/$ident") and mkdir "$testset_path\/$ident",0750;

	# read in the appropriate batch system header template
	my $file = "$bench_test\/templates/$batch_method\_header.in";
    (defined $DEBUG) and print "DEBUG: JOB TEMPLATE => $file\n";

	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	$batch_header = <IN>;
	close(IN);
	$/ = "\n";

	# Here we build the core nodehwtest batch template we will use to do
	# all our substitutions below.
	%templates = ();
	$job = 'nodetest';
	$templates{$job}{'batch'} = $batch_header;

	# read in the job template so we can add it
	$file = "$testset_path\/nodehwtest\_$job.in";
	(defined $jobtemplate) and $file = $jobtemplate;
	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	$job_template = <IN>;
	close(IN);
	$/ = "\n";

	# continue building the job template
	$templates{$job}{'batch'} .= $job_template;
	
	if ($DEBUG and $DEBUG < 2) {
		print "DEBUG: found and processed job template nodehwtest\_$job.in\n";
	}

	# prime the output buffer with the appopriate template
	$outbuf_clean = $templates{$job}{'batch'};

	# loop through all the nodes we'll be running node-level tests on through
	# the batch system, generate a script specifically targeted for each
	# node (i.e. a batch script per node which only works on batch schedulers
	# that support this), and then submit each script 

	print "Starting jobs for test identifier \'$ident\':\n";

	# need to prime some vars
	$numsubmitted = 0;
	$ppn = $numnodes = $numprocs = 1; 
	$runtype = 'batch';
	foreach my $node (sort sort_by_nodename keys(%nodehash)) {
		# make sure the node wasn't excluded
		($nodehash{$node} == 0xdead) and next;

		$jobname = "nodehwtest-$node";
		# get clean batch job template
		$outbuf = $outbuf_clean;

#		if (defined $nodebatch) {
			# build the string that we will put into the batch template
			# that will target the batch script for a specific node
			@nodearray = ("$node");
			$nodespec = batch_nodespec_build(\@nodearray); 
			# update the batch job file with the nodespec
			$outbuf =~ s/TORQUE_NODESPEC_HERE/$nodespec/gs;
			$outbuf =~ s/SLURM_NODESPEC_HERE/-w $nodespec/gs;
			$outbuf =~ s/BSUB_NODESPEC_HERE/$nodespec -R span[ptile=$procs_per_node]/gs;
#		}
#		else {
#			# update the batch job file with a generic nodecount
#			$outbuf =~ s/TORQUE_NODESPEC_HERE/1\:ppn\=$procs_per_node/gs;
#			$outbuf =~ s/SLURM_NODESPEC_HERE/-N 1/gs;
#		}

		# updated the batch job template with possible preamble stuff
		if (defined $preamble) {
			$outbuf =~ s/PREAMBLE_HERE/$preamble/gs;
		}
		else {
			$outbuf =~ s/PREAMBLE_HERE/\/bin\/true/gs;
		}

		# update the batch job file with the node_hw_test command line
		$outbuf =~ s/COMMAND_HERE/$nodecmd/gs;

		# here we do all the standard substitutions, some of which are meaningless
		# in this context
		$outbuf = std_substitute($outbuf,$numprocs,$ppn,$numnodes,$runtype,
			$default_walltime,$testset,$jobname);

		# write out the generated job file
		$outfile = "nhwt\-$node\.$batch_extension";
#		(defined $batch) and $outfile = "nhwt\.$batch_extension";
		open (OUT,">$testset_path\/$ident\/$outfile") or die
			"Could not write $testset_path\/$ident\/$outfile ($!)";
		print OUT $outbuf;
		close(OUT);

		(defined $DEBUG and $DEBUG > 1) and print
			"DEBUG: built BATCH script for node_hw_test run on $node\n";

		my $cmd = batch_submit_cmdbuild();
		(defined $batchargs) and $cmd .= " $batchargs ";

		# lsf wants the submit script to be redirected to the submission program bsub
		if ( $batch_extension eq "lsf" ) {
			$cmd .= "< $outfile";
		}
		else {
			$cmd .= "$outfile";
		}


		$DEBUG and print "DEBUG: cmd=$cmd\n";
		system($cmd) unless $DRYRUN;

		# just a simple heuristic to submit jobs in chunks and then pause
		# a bit
		$numsubmitted++;
		if (($numsubmitted % 128) == 0) {
			sleep 2;
		}
	}

	print "Started $numsubmitted jobs in the NODEHWTEST testset (--ident \'$ident\').\n";

	exit;
}

if (defined $offloadmap) {
	# need to break the list of nodes to test apart into roughly equally
	# sized chunks for each offload node
	$num = 0;
	$offload_index = 0;
	%offload_hash = ();

	# prepare the hash corresponding to the first offload node, i.e.
	# index 0 in the @{$offloadnodes{$ident}} array
	my %temp_nodehash = ();
	$offload_hash{$offloadnodes{$ident}[$offload_index]} = \%temp_nodehash;
	(defined $DEBUG and $DEBUG > 1) and print
		"DEBUG: offload_index=$offload_index offloadnode=".
		"$offloadnodes{$ident}[$offload_index] ".
		"$offload_hash{$offloadnodes{$ident}[$offload_index]}\n";
	
	foreach my $node (sort sort_by_nodename keys(%nodehash)) {
		($nodehash{$node} == 0xdead) and next;
		$num++;
		$offload_hash{$offloadnodes{$ident}[$offload_index]}->{$node} = 1;

		if (($num % $num_per_offload) == 0 or $num == $numtestnodes) {
			# we just finished processing a chunk of the overall nodelist
			# so tidy up and prepare for the next chunk
			$offload_index++;
			my %temp_nodehash = ();
			$offload_hash{$offloadnodes{$ident}[$offload_index]} = \%temp_nodehash;
			(defined $DEBUG and $DEBUG > 1) and print
				"DEBUG: num=$num node=$node offload_index=$offload_index ".
				"offloadnode=$offloadnodes{$ident}[$offload_index] ".
				"$offload_hash{$offloadnodes{$ident}[$offload_index]}\n";
		} 
		
		if ($num == $numtestnodes) {
			last;
		}
	}

	# Now we have hashes with a list of nodes that each offload node will
	# be responsible for. So, now we need to loop through each offload node,
	# build a nodehwtest_start_jobs.pl command tailored for the nodes that
	# the offload will be responsible for, and then remotely execute the
	# nodehwtest_start_jobs.pl command on the offload node.  whew....
	foreach $offnode (@{$offloadnodes{$ident}}) {
		my $nodelist = hash_to_pdshlist($offload_hash{$offnode});

		# build the exact command to execute on the offload node
		my $offloadcmd = build_nodehwtest_cmdline(undef,
			"$bench_test/$testset/nodehwtest_start_jobs.pl");
		$offloadcmd .= "--nodelist $nodelist ";
		(defined $remote) and $offloadcmd .= "--remote ";
		(defined $nodebatch) and $offloadcmd .= "--nodebatch ";
		(defined $background) and $offloadcmd .= "--bg ";
		(defined $preamble) and $offloadcmd .= "--preamble \'$preamble\' ";
		(defined $DRYRUN) and $offloadcmd .= "--dryrun ";
		(defined $DEBUG) and $offloadcmd .= "--debug $DEBUG ";
	
		# need a single node pdsh list to build a remote command	
		my %temphash = ( "$offnode" => 1);
		my $templist = hash_to_pdshlist(\%temphash);
		my $cmd = remotecmd_cmdbuild($templist, "export CBENCHOME=$BENCH_HOME\; export CBENCHTEST=$bench_test\; $offloadcmd");
		$cmd = remotecmd_cmdbuild($templist, "export CBENCHSTANDALONEDIR=$BENCH_HOME\; $offloadcmd") if (defined($ENV{CBENCHSTANDALONEDIR}));
		defined $DEBUG and print "DEBUG: offload remote execution command = $cmd\n";

		system("$cmd");
	}
	exit;
}
else {
	# do the final conversion from the master list of nodes to a pdsh style
	# compressed list
	my $nodelist = '';
	$nodelist = hash_to_pdshlist(\%nodehash);

	print "Starting node_hw_test jobs for test identifier \'$ident\' on $nodelist:\n".
		"Start time: $datenow\n";

	if (defined $background) {
		open(OUT,">$bench_test/$testset/$ident/background_start.output");
		print OUT "\n\nStarting node_hw_test jobs for test identifier \'$ident\' on $nodelist:\n".
		"Start time: $datenow\n";
		close(OUT);
	}


	# build the full command line we'll execute to do all the remote execution
	# goodness
	(defined $preamble) and $nodecmd = "$preamble ; $nodecmd";
		my $cmd = remotecmd_cmdbuild($nodelist, "export CBENCHOME=$BENCH_HOME\; export CBENCHTEST=$bench_test\; $nodecmd");
		$cmd = remotecmd_cmdbuild($nodelist, "export CBENCHSTANDALONEDIR=$BENCH_HOME\;  $nodecmd") if (defined($ENV{CBENCHSTANDALONEDIR}));
	defined $DEBUG and print "DEBUG: remote execution command = $cmd\n";

	if (defined $background) {
		my $child;
		unless ($child = fork()) {
			# we are the child and we want to dissolve all ties to
			# out parent so we behave more like a daemon process
			for my $handle (*STDIN, *STDOUT, *STDERR) {
				open($handle, "+<", "/dev/null")
					|| die "can't reopen $handle to /dev/null: $!";
			}

			use POSIX;

			POSIX::setsid( )
   		 		or die "Can't start a new session: $!";

			# need to tack on the end of the command to save the output
			$cmd .= " >> $bench_test/$testset/$ident/background_start.output 2>&1";
			defined $DEBUG and print "DEBUG: child remote execution command = $cmd\n";
			exec($cmd) unless defined $DRYRUN;
		}

		# we are the parent, so just exit and let the child run
	}
	else {
		exec($cmd) unless defined $DRYRUN;
	}
}

chdir $pwd;

sub build_nodehwtest_cmdline {
	my $cmdstring = shift;
	my $command = shift;

	$cmdstring .= "$command --ident $ident ";
	$cmdstring .= join(' ',@ARGV);
	(defined $match) and $cmdstring .= " --match \'$match\' ";
	(defined $exclude) and $cmdstring .= " --exclude \'$exclude\' ";
	(defined $class) and $cmdstring .= " --class \'$class\' ";
	(defined $DEBUG) and $cmdstring .= " --debug $DEBUG ";

	return $cmdstring;
}

sub usage {
    print "USAGE: $0\n" .
	      "Cbench script to start jobs in the $testset test set\n".
          "   --remote             Start jobs via remote command execution in\n" .
		  "                        parallel\n".
		  "   --batch              Start nodehwtest jobs via a batch scheduler that will\n".
		  "                        run wherever the batch system puts them\n".
		  "   --nodebatch          Start nodehwtest jobs targeted for specific list\n".
		  "                        of nodes via a batch scheduler\n".
		  "   --batchargs 'args'   Pass extra arguments to the batch or remote execution\n".
		  "                        methods. For example:\n".
		  "                            --batchargs '-l walltime=08:00:00'\n".
		  "   --background         Background the process that will control\n".
		  "                        starting up of jobs. Useful for starting up\n".
		  "                        long running sequences of jobs such as the\n".
		  "                        node_hw_test processes via remote execution.\n".
          "   --ident <name>       Identifying string for the test\n".
		  "   --preamble           Command string to execute before running the\n".
		  "                        actual hardware tests on each node. For example\n".
		  "                        to pickup the right environment:\n".
		  "                            --preamble '. /etc/profile'\n".
		  "   --class <regex>      Run only tests whose test class matches the\n".
		  "                        provided regex string. For example:\n".
		  "                          --class 'cpu|disk|memory'\n".
		  "                        explicitly specifies the default behavior\n".
		  "                        of node_hw_test\n".
		  "   --match <regex>      Only run hw_test modules that match the\n" .
		  "                        the specified regex string. For example,\n" .
		  "                           --match streams\n" .
		  "                        would only run the streams hw_test module\n" .
		  "   --exclude <regex>    Do NOT run hw_test modules that match the\n" .
		  "                        the specified regex string. For example,\n" .
		  "                           --exclude streams\n" .
		  "                        would only run the streams hw_test module\n" .
		  "   --nodelist <spec>    Run the node level tests on the nodes specified\n".
		  "                        by the Pdsh style compressed node list. For\n".
		  "                        example:\n".
		  "                           --nodelist bn[1-20,25-50]\n".
		  "                        This must be used with the --nodebatch parameter.\n".
		  "   --nodefile <file>    Run the node level tests on the nodes specified\n".
		  "                        in the file provided.  One hostname per line\n". 
		  "   --ignorenodes <spec> Ignore/exclude nodes specified by the Pdsh style\n".
		  "                        compressed node list from running node level tests\n".
		  "                        For example:\n".
		  "                           --ignorenodes bn[33,43]\n".
		  "   --offloadmap <file>  Use the offload map specified by the file. An\n".
		  "                        offload map tells nodehwtest_start_jobs.pl how to\n".
		  "                        offload the work of starting up lots and lots of\n".
		  "                        node level tests. This is needed when a large\n".
		  "                        number of nodes need to be tested in excess of what\n".
		  "                        a single node is able to reliably remotely start\n".
		  "                        Anecdotally, this number was around 512 nodes to be\n".
		  "                        tested started by a single controlling node, i.e. a\n".
		  "                        pdsh command running a complex command on 512 nodes\n".
		  "                        at once. The format of the offload map file is\n".
		  "                        fairly simple:\n".
		  "                           <test ident1>      node1,node2,node3\n".
		  "                           <test ident2>      node4,node5,node6\n".
		  "                        Each line is a test identifier to list of nodes\n".
		  "                        mapping.\n".
		  "   --debug <level>      Turn on debugging at the specified level\n".
          "   --dryrun             Do everything but start jobs to see what would\n".
		  "                        happen\n";
}
