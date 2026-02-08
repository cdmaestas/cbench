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

unshift @INC, "$BENCH_HOME";
require "cluster.def";

use Data::Dumper;
use Term::ANSIColor qw(:constants color colored);

# The Cbench release version. This isn't necessarily the exact version of the
# Cbench code because it could be a Subversion checkout, but this is the
# closest release in the lineage. This better match what is in the VERSION
# file or someone borked the release. 
$cbench_version = "1.2.2";

# where to find schedutils' taskset
$TASKSET = "/usr/bin/taskset";


#
# this is a list of all the supported Cbench testsets that will
# be installed in the absence of the user picking specific ones
$core_testsets = "bandwidth linpack rotate nodehwtest mpioverhead latency collective io iosanity hpcc mpisanity shakedown mpigraph hpccg npb trilinos lammps amg irs sweep3d phdmesh sppm graph500";


# An array of run sizes (number of processes) that can be used in
# generation loops. It includes powers of 2, perfect squares, some nice
# even numbers to increase resolution, and whatever else is desired.
@run_sizes = (1,2,4,8,9,16,25,32,36,49,64,72,81,96,100,110,112,121,128,
	144,169,192,200,225,256,289,300,324,361,384,400,441,462,
	468,484,500,506,512,529,576,600,625,650,676,700,729,768,
	784,800,841,850,900,960,961,992,1000,1024,1089,1100,1156,1200,
	1225,1296,1300,1369,1400,1444,1500,1521,1600,1600,1681,1700,1728,1764,
	1800,1849,1900,1920,1936,2000,2025,2048,2100,2116,2200,2209,2300,2304,
	2400,2401,2500,2500,2600,2601,2700,2704,2800,2809,2900,2916,3000,
	3025,3072,3100,3136,3200,3249,3300,3364,3400,3481,3500,3600,3700,
	3721,3800,3840,3844,3900,3969,4000,4096,6912,8192,10240,12288,13824);

# Determine the file extension that should be used for batch scripts
if (defined $batch_method) {
	my $funcname = "$batch_method\_batch_extension";
	*func = \&$funcname;
	$batch_extension = func();
	if (!defined $batch_extension) {
		warning_print("Couldn't determine batch job script extension.  Defaulting to \".pbs\"");
		$batch_extension = "pbs";
	}
}

###########################################################
#
# This section has all the subroutines that support the
# various "job launch" methods that Cbench supports.
# Everything in the subroutine name before
# '_joblaunch_cmdbuild' is
# the actual Cbench name for the job launch method, i.e.
# what is used in cluster.def.
#
#
###########################################################

###########################################################
# Support for the OpenMPI "orterun" job launch method
#
#

# routine to build launch command lines
sub openmpi_joblaunch_cmdbuild {
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;

	my $cmd;
	if (length $joblaunch_cmd > 1) {
		$cmd = $joblaunch_cmd;
	}
	else {
		$cmd = "orterun";
	}
	
	# set this to support Openmpi 1.2 and newer features
	my $openmpi12_stuff = 1;

	# if we use nolocal, and fail to specify extra job nodes, set it
	$extra_job_nodes = 1 if !$extra_job_nodes and $joblaunch_extraargs =~ /nolocal/;

	if ($openmpi12_stuff) {
		($max_nodes > 1) and ($cmd .= " -npernode $ppn");
	}
	else {
		($ppn == 1) and $cmd .= " -bynode";
		($ppn == 2) and $cmd .= " -bynode";
		($ppn == 4) and $cmd .= " -byslot";
		($ppn == 8) and $cmd .= " -byslot";
	}
	
	$cmd .= " -np $numprocs ";

	# putting this last so that it can act as extra launcher arguments, or as
	# a wrapper of some sort (numa_wrapper, valgrind, etc)
	(length $joblaunch_extraargs > 1) and $cmd .= " $joblaunch_extraargs";

	return $cmd;
}

# routine used to describe what standard file descriptor(s) openmpi
# writes its rank-to-node mapping information too
sub openmpi_ranktonode_files {
	# we turn an array of keyword(s) 
	return qw/STDERR/;
}

# routine used to parse the passed in buffer(s) for nodelist information,
# i.e. the rank-to-nodename mapping, for mpiexec
sub openmpi_ranktonode_parse {
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


###########################################################
# Support for the "mpiexec" job launch method
#
#

# routine to build launch command lines
sub mpiexec_joblaunch_cmdbuild {
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;

	my $cmd;
	if (length $joblaunch_cmd > 1) {
		$cmd = $joblaunch_cmd;
	}
	else {
		$cmd = "mpiexec";
	}
	
	# if we use nolocal, and fail to specify extra job nodes, set it
	$extra_job_nodes = 1 if !$extra_job_nodes and $joblaunch_extraargs =~ /nolocal/;
	
	($ppn == 1) and $cmd .= " -pernode";
	
	$cmd .= " -np $numprocs ";

	# putting this last so that it can act as extra launcher arguments, or as
	# a wrapper of some sort (numa_wrapper, valgrind, etc)
	(length $joblaunch_extraargs > 1) and $cmd .= " $joblaunch_extraargs";

	return $cmd;
}

sub slurm_joblaunch_cmdbuild {
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;

	my $cmd;
	if (length $joblaunch_cmd > 1) {
		$cmd = $joblaunch_cmd;
	}
	else {
		$cmd = "srun";
	}

	# if we use nolocal, and fail to specify extra job nodes, set it
	#FIXME - does slurm support this?
	#$extra_job_nodes = 1 if !$extra_job_nodes and $joblaunch_extraargs =~ /nolocal/;

	#FIXME - how should we handle each MPI-specific launch style under slurm?
	# see: https://computing.llnl.gov/linux/slurm/quickstart.html#mpi
	$cmd .= " -n $numprocs --ntasks-per-node $ppn ";

	# putting this last so that it can act as extra launcher arguments, or as
	# a wrapper of some sort (numa_wrapper, valgrind, etc)
	(length $joblaunch_extraargs > 1) and $cmd .= " $joblaunch_extraargs";

	return $cmd;
}

# routine used to describe what standard file descriptor(s) mpiexec
# writes its rank-to-node mapping information too
sub mpiexec_ranktonode_files {
	# we turn an array of keyword(s) 
	return qw/STDERR/;
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


###########################################################
# Support for the "mpirun" job launch method
#
sub mpirun_joblaunch_cmdbuild {
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;

	my $cmd;
	if (length $joblaunch_cmd > 1) {
		$cmd = $joblaunch_cmd;
	}
	else {
		$cmd = "mpirun";
	}

	# if we use nolocal, and fail to specify extra job nodes, set it
	$extra_job_nodes = 1 if !$extra_job_nodes and $joblaunch_extraargs =~ /nolocal/;

	#($ppn == 1) and $cmd .= " -pernode";

	$cmd .= " -np $numprocs ";

	# putting this last so that it can act as extra launcher arguments, or as
	# a wrapper of some sort (numa_wrapper, valgrind, etc)
	(length $joblaunch_extraargs > 1) and $cmd .= " $joblaunch_extraargs";

	return $cmd;
}


###########################################################
# Support for the "yod" job launch method
#
#

# routine to build launch command lines
sub yod_joblaunch_cmdbuild {
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;

	my $cmd;
	if (length $joblaunch_cmd > 1) {
		$cmd = $joblaunch_cmd;
	}
	else {
		$cmd = "yod";
	}
	
	# if we use nolocal, and fail to specify extra job nodes, set it
	$extra_job_nodes = 1 if !$extra_job_nodes and $joblaunch_extraargs =~ /nolocal/;
	
	$cmd .= " -VN$ppn";
	
	$cmd .= " -sz $numprocs ";

	# putting this last so that it can act as extra launcher arguments, or as
	# a wrapper of some sort (numa_wrapper, valgrind, etc)
	(length $joblaunch_extraargs > 1) and $cmd .= " $joblaunch_extraargs";

	return $cmd;
}


###########################################################
# Support for the "alps" job launch method
# This is the Cray Application Level Placement Scheduler on CLE 3.x+
#

# routine to build launch command lines
sub alps_joblaunch_cmdbuild {
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;

	my $cmd;
	if (length $joblaunch_cmd > 1) {
		$cmd = $joblaunch_cmd;
	}
	else {
		$cmd = "aprun";
	}
	
	# if we use nolocal, and fail to specify extra job nodes, set it
	$extra_job_nodes = 1 if !$extra_job_nodes and $joblaunch_extraargs =~ /nolocal/;
	
	$cmd .= " -n $numprocs -N $ppn";

	# putting this last so that it can act as extra launcher arguments, or as
	# a wrapper of some sort (numa_wrapper, valgrind, etc)
	(length $joblaunch_extraargs > 1) and $cmd .= " $joblaunch_extraargs";

	return $cmd;
}


###########################################################
#
# This section has all the subroutines that support the
# various batch systems that Cbench knows about.
# Everything in the subroutine name before
# '_batchsubmit_cmdbuild' is the actual Cbench name for the
# batch submission method, i.e. what is used in cluster.def.
#
###########################################################

###########################################################
# Support for the "pbspro" batch system
#
sub pbspro_batchsubmit_cmdbuild {
	my $cmd;
	if (length $batch_cmd > 1) {
		$cmd = $batch_cmd;
	}
	else {
		$cmd = "qsub";
	}
	
	(length $batch_extraargs > 1) and $cmd .= " $batch_extraargs";
	
	return "$cmd ";
}

sub pbspro_nodespec_build {
	# a reference to an array of nodes
	my $nodearray = shift;
	return torque_nodespec_build($nodearray);
}

sub pbspro_query {
	my $regex = shift;

	my %jobdata = (
		'QUEUED' => 0,
		'RUNNING' => 0,
		'TOTAL' => 0,
	);

	my $cmd = 'qstat -a';
	(defined $DEBUG) and print "DEBUG:pbspro_query() cmd=$cmd\n";
	my @buf = `$cmd`;
	(defined $DEBUG and $DEBUG > 3) and print "DEBUG:pbspro_query() buffer dump:@buf";
	foreach my $l (@buf) {
		chomp $l;
		# filter out job lines that don't match the incoming regex
		(defined $regex and $l !~ /$regex/) and next;
		# filter by user name as well
		my $uname = getpwuid($<);
		($l !~ /$uname/) and next;

		(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pbspro_query() l=$l\n";

		#                                           Time In Req'd  Req'd   Elap
		#Job ID Username Queue    Jobname    SessID  Queue  Nodes  Time  S Time
		#------ -------- -------- ---------- ------ ------- ------ ----- - -----
		#26897  bob      standard routecheck   4850  000:03    225 02:00 R 00:01
		#26898  bob      standard routecheck   4607  000:03    236 02:00 R 00:01
		if ($l =~ /(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
			my $state = $9;
			my $name = $4;
			(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pbspro_query() l=$l state=$state name=$name\n";

			if ($state eq 'Q') {
				$jobdata{$name} = 'queued';
				$jobdata{'QUEUED'}++;
				$jobdata{'TOTAL'}++;
			}
			elsif ($state eq 'R') {
				$jobdata{$name} = 'running';
				$jobdata{'RUNNING'}++;
				$jobdata{'TOTAL'}++;
			}
			else {
				$jobdata{$name} = $state;
				$jobdata{'TOTAL'}++;
				(defined $DEBUG) and print "DEBUG:pbspro_query() ".
					"job $name had odd state $state\n";
			}
		}
	}

	if (defined $DEBUG and $DEBUG > 1) {
		print "DEBUG:DEBUG:pbspro_query() Dump of \%jobdata:\n";
		print Dumper (\%jobdata);
	}

	return %jobdata;
}

sub pbspro_batch_extension {
	return "pbs";
}


###########################################################
# Support for the "slurm" batch system
#
sub slurm_batchsubmit_cmdbuild {
	my $cmd;
	if (length $batch_cmd > 1) {
		$cmd = $batch_cmd;
	}
	else {
		$cmd = "sbatch";
	}

	(length $batch_extraargs > 1) and $cmd .= " $batch_extraargs";

	# make slurm's output filename look like PBS's
	$cmd .= " --no-requeue --output='slurm.o\%j'";

	return "$cmd ";
}

sub slurm_nodespec_build {
	# a reference to an array of nodes
	my $nodearray = shift;

	return join(',', @$nodearray);
}

sub slurm_query {
	my $regex = shift;

	my %jobdata = (
		'QUEUED' => 0,
		'RUNNING' => 0,
		'TOTAL' => 0,
	);

	my $cmd = "squeue -o \"%.7i %.9P %.25j %.8u %.8T %.9M %.9l %.6D %R\" -u $ENV{USER}";
	debug_print(2, "DEBUG:slurm_query() cmd=$cmd\n");
	my @buf = `$cmd`;
	debug_print(3, "DEBUG:slurm_query() buffer dump:@buf");
	foreach my $l (@buf) {
		chomp $l;
		# filter out job lines that don't match the incoming regex
		(defined $regex and $l !~ /$regex/) and next;
		# filter by user name as well
		my $uname = getpwuid($<);
		($l !~ /$uname/) and next;

		debug_print(3, "DEBUG:slurm_query() l=$l\n");
		#  JOBID PARTITION                      NAME     USER    STATE      TIME TIMELIMIT  NODES NODELIST(REASON)
		#     8717    pbatch                       rEX  bob  PENDING      0:00 3-00:00:00      8 (JobHeld)

		if ($l =~ /(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
			my $jobid = $1;
			my $state = $5;
			my $name = $3;
			debug_print(3, "DEBUG:slurm_query() l=$l jobid=$1 state=$state name=$name\n");

			if ($state =~ 'PENDING') {
				$jobdata{$name} = 'queued';
				$jobdata{$jobid} = 'queued';
				$jobdata{'QUEUED'}++;
				$jobdata{'TOTAL'}++;
			}
			elsif ($state  =~ 'RUNNING|COMPLETING') {
				$jobdata{$name} = 'running';
				$jobdata{$jobid} = 'running';
				$jobdata{'RUNNING'}++;
				$jobdata{'TOTAL'}++;
			}
			else {
				$jobdata{$name} = $state;
				$jobdata{$jobid} = $state;
				$jobdata{'TOTAL'}++;
				debug_print(1, "DEBUG:slurm_query() ".
					"job $name had odd state $state\n");
			}
		}
	}

	if (defined $DEBUG and $DEBUG > 1) {
		print "DEBUG:slurm_query() Dump of \%jobdata:\n";
		print Dumper (\%jobdata);
	}

	return %jobdata;
}

sub slurm_batch_extension {
	return "slurm";
}

###########################################################
# Support for the "lsf" batch system
#
sub lsf_batchsubmit_cmdbuild {
	my $cmd;
	if (length $batch_cmd > 1) {
		$cmd = $batch_cmd;
	}
	else {
		$cmd = "bsub";
	}

	$cmd .= " -o 'lsf.o\%J' ";
	
	(length $batch_extraargs > 1) and $cmd .= " $batch_extraargs";
	
	return "$cmd ";
}
sub lsf_nodespec_build {
	# a reference to an array of nodes
	my $nodearray = shift;

	my $list;

	foreach my $n (@$nodearray) {
		$list .= "-m $n ";
	}
	# remove trailing '+'
	$list =~ s/\+$//;

	return $list;
}
sub lsf_query {
	my $regex = shift;
	die "Error: UNIMPLEMENTED lsf_query() ...";
}
sub lsf_batch_extension {
	return "lsf";
}

###########################################################
# Support for the "Load Leveler" batch system
#
sub loadleveler_batchsubmit_cmdbuild {
	my $cmd;
	if (length $batch_cmd > 1) {
		$cmd = $batch_cmd;
	}
	else {
		$cmd = "llsubmit";
	}

	# transform the output file on the submission script to include the job name
	die "Error: loadleveler_batchsubmit_cmdbuild() transform the output file on the submission script to include the job name";
	
	(length $batch_extraargs > 1) and $cmd .= " $batch_extraargs";
	
	return "$cmd ";
}
sub loadleveler_nodespec_build {
	die "Error: UNIMPLEMENTED lsf_nodespec_build() ...";
}
sub loadleveler_query {
	my $regex = shift;
	die "Error: UNIMPLEMENTED loadleveler_query() ...";
}
sub loadleveler_batch_extension {
	return "loadleveler";
}

###########################################################
# Support for the "moab/msub" batch system
#
sub moab_batchsubmit_cmdbuild {
	my $cmd;
	if (length $batch_cmd > 1) {
		$cmd = $batch_cmd;
	}
	else {
		$cmd = "msub";
	}

	# make moab's output filename look like PBS's
	# and make sure we don't requeue
	$cmd .= " -r n -o 'moab.o\%j'";
	
	(length $batch_extraargs > 1) and $cmd .= " $batch_extraargs";
	
	return "$cmd ";
}

sub moab_nodespec_build {
	# a reference to an array of nodes
	my $nodearray = shift;
	return torque_nodespec_build($nodearray);
}

sub moab_query {
	my $regex = shift;
	die "Error: UNIMPLEMENTED moab_query() ...";
}

sub moab_batch_extension {
	return "moab";
}

###########################################################
# Support for the "cletorque" batch system
#
# That is Torque running in the Cray Linux Environment (CLE)
sub cletorque_batchsubmit_cmdbuild {
	return torque_batchsubmit_cmdbuild();
}

sub cletorque_nodespec_build {
	# a reference to an array of nodes
	my $nodearray = shift;
	return torque_nodespec_build($nodearray);
}

sub cletorque_query {
	my $regex = shift;
	return torque_query($regex);
}

sub cletorque_batch_extension {
	return "pbs";
}

###########################################################
# Support for the "torque" batch system
#
sub torque_batchsubmit_cmdbuild {
	my $cmd;
	if (length $batch_cmd > 1) {
		$cmd = $batch_cmd;
	}
	else {
		$cmd = "qsub";
	}
	
	(length $batch_extraargs > 1) and $cmd .= " $batch_extraargs";
	
	return "$cmd ";
}

sub torque_nodespec_build {
	# a reference to an array of nodes
	my $nodearray = shift;

	my $list;

	foreach my $n (@$nodearray) {
		$list .= "$n\:ppn=$procs_per_node+";
	}
	# remove trailing '+'
	$list =~ s/\+$//;

	return $list;
}

sub torque_query {
	my $regex = shift;

	my %jobdata = (
		'QUEUED' => 0,
		'RUNNING' => 0,
		'TOTAL' => 0,
	);

	my $cmd = "qstat -u $ENV{USER}";
	(defined $DEBUG) and print "DEBUG:torque_query() cmd=$cmd\n";
	my @buf = `$cmd`;
	(defined $DEBUG and $DEBUG > 3) and print "DEBUG:torque_query() buffer dump:@buf";
	foreach my $l (@buf) {
		chomp $l;
		# filter out job lines that don't match the incoming regex
		(defined $regex and $l !~ /$regex/) and next;
		# filter by user name as well
		my $uname = getpwuid($<);
		($l !~ /$uname/) and next;

		(defined $DEBUG and $DEBUG > 2) and print "DEBUG:torque_query() l=$l\n";
		if ($l =~ /(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)/) {
			my $state = $10;
			my $name = $4;
			my ($jobid) = $1 =~ /(\d+)\./;
			(defined $DEBUG and $DEBUG > 2) and print "DEBUG:torque_query() l=$l state=$state name=$name jobid=$jobid\n";

			if ($state eq 'Q') {
				$jobdata{$name} = 'queued';
				$jobdata{$jobid} = 'queued';
				$jobdata{'QUEUED'}++;
				$jobdata{'TOTAL'}++;
			}
			elsif ($state eq 'R') {
				$jobdata{$name} = 'running';
				$jobdata{$jobid} = 'running';
				$jobdata{'RUNNING'}++;
				$jobdata{'TOTAL'}++;
			}
			elsif ($state eq 'C') {
				$jobdata{$name} = 'completing';
				$jobdata{$jobid} = 'completing';
				$jobdata{'TOTAL'}++;
			}
			else {
				$jobdata{$name} = $state;
				$jobdata{'TOTAL'}++;
				(defined $DEBUG) and print "DEBUG:torque_query() ".
					"job $name had odd state $state\n";
			}
		}
	}

	if (defined $DEBUG and $DEBUG > 1) {
		print "DEBUG:torque_query() Dump of \%jobdata:\n";
		print Dumper (\%jobdata);
	}

	return %jobdata;
}

sub torque_batch_extension {
	return "pbs";
}

##########################################################
#
# This section has all the subroutines that support the
# various remote command execution methods that Cbench
# knows about.
# Everything in the subroutine name before
# '_remote_cmdbuild' is the actual Cbench name for the
# remote method, i.e. what is used in cluster.def.
#
###########################################################

###########################################################
# Support for PDSH remote command execution
#
sub pdsh_remote_cmdbuild {
	my $nodelist = shift;
	my $remotecmd = shift;
	my $cmd;

	$cmd = "pdsh ";
	(length $remotecmd_extraargs > 1) and $cmd .= "$remotecmd_extraargs ";
	$cmd .= "-w $nodelist \"$remotecmd\"";
	
	return "$cmd ";
}



###########################################################
#
# Here are all the Cbench reusable core subroutines
# (and some misc global variables)
#
###########################################################

# some Cbench global vars
%main::childpids = ();
$cbench_mark_prefix = "=====<Cbench>==========>";
$main::INTsignalled = 0;

# This routine builds the job templates (batch and interactive)
# job file generation done in the *_gen_jobs.pl scripts
#
# params:
#  1) testset name
#  2) hash reference to hold the templates
sub build_job_templates {
	my $testset = shift;
	my $templates = shift;

	my $bench_test = get_bench_test();
	my $testset_path = "$bench_test/$testset";

	# read in the appropriate batch system header template
	my $file = "$bench_test\/templates/$batch_method\_header.in";
	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	my $batch_header = <IN>;
	close(IN);
	$/ = "\n";

	# read in the appropriate interactive job header template
	$file = "$bench_test\/templates/interactive_header.in";
	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	my $interactive_header = <IN>;
	close(IN);
	$/ = "\n";

	# read in the preamble job header template
	$file = "$bench_test\/templates/preamble_header.in";
	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	my $preamble_header = <IN>;
	close(IN);
	$/ = "\n";

	# read in the appropriate common job header template
	$file = "$bench_test\/templates/common_header.in";
	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	my $common_header = <IN>;
	close(IN);
	$/ = "\n";

	# read in the appropriate common job footer template
	$file = "$bench_test\/templates/common_footer.in";
	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	my $common_footer = <IN>;
	close(IN);
	$/ = "\n";

	# Here we build the core template(s) we will use to do all our
	# substitutions below. We look in the test set directory for files
	# named TESTSET_BINARYNAME.in where TESTSET is the test set name,
	# i.e. 'bandwidth', 'xhpl', and BINARYNAME is the name of the specific
	# benchmark to be run
	my @temp = `/bin/ls -1 $testset_path\/$testset\_*\.in 2>&1`;
	
	# we also want to build the internal Cbench "job" used by the combination
	# batch (--combobatch start_jobs mode)
	push @temp, `/bin/ls -1 $bench_test\/templates/combobatch.in`;

	# if the cbench_make_skel_jobscript.pl called us to generate just a
	# skeleton job script, use the skeleton hello world job template
	if ($testset =~ /^SKELETONJOB:(\S+)/) {
		@temp = ("$bench_test\/templates/skeleton_$1.in");
	}

	foreach (@temp) {
		chomp $_;
		my $jobname = "";
		my $jobfile = "";
		if (/(\S+)\/($testset)_(\S+)\.in/) {
			$jobname = $3;
			$jobfile = "$testset_path\/$testset\_$jobname.in";
		}
		elsif (/combobatch.in/) {
			$jobname = "combobatch";
			$jobfile = "$bench_test\/templates/combobatch.in";
		}
		elsif (/(skeleton_\S+.in)/) {
			$jobname = "skel";
			$jobfile = "$bench_test\/templates/$1";
		}
		else {
			next;
		}

		# read in the job template so we can add it
		open (JOBFILEIN,"<$jobfile") or die
			"Could not open $jobfile ($!)";
		undef $/;
		$job_template = <JOBFILEIN>;
		close(JOBFILEIN);
		$/ = "\n";


		# start building the job templates
		$templates->{$jobname}{'batch'} = $batch_header;
		$templates->{$jobname}{'interactive'} = $interactive_header;

		# add the preamble header
		$templates->{$jobname}{'batch'} .= $preamble_header;
		$templates->{$jobname}{'interactive'} .= $preamble_header;
		# add the common header
		$templates->{$jobname}{'batch'} .= "\n######## Cbench $bench_test\/common_header.in ########\n";
		$templates->{$jobname}{'batch'} .= $common_header;
		$templates->{$jobname}{'interactive'} .= "\n######## Cbench $bench_test\/common_header.in ########\n";
		$templates->{$jobname}{'interactive'} .= $common_header;

		# continue building the job templates
		$templates->{$jobname}{'batch'} .= "\n######## Cbench $jobfile ########\n";
		$templates->{$jobname}{'batch'} .= $job_template;
		$templates->{$jobname}{'interactive'} .= "\n######## Cbench $jobfile ########\n";
		$templates->{$jobname}{'interactive'} .= $job_template;

		if ($DEBUG and $DEBUG <= 3) {
			print "DEBUG: found and processed job template $testset\_$jobname.in\n";
		}
		elsif ($DEBUG > 3) {
			print "DEBUG:  batch job template $testset\_$jobname.in\n" .
				"====================================================\n".
				$templates->{$jobname}{'batch'} .
				"====================================================\n";
		}

		# add the common footer
		$templates->{$jobname}{'batch'} .= "\n######## Cbench $bench_test\/common_footer.in ########\n";
		$templates->{$jobname}{'batch'} .= $common_footer;
		$templates->{$jobname}{'interactive'} .= "\n######## Cbench $bench_test\/common_footer.in ########\n";
		$templates->{$jobname}{'interactive'} .= $common_footer;

	}
}

#
# This routine checks for the existence and executability of a binary file found in
# a job script.  It is passed in the test name, batch extension, current working directory,
# and a reference to a hash containing error messages for this benchmark so that all errors
# are printed at once at the end of submission for that test.
sub check_bin {
    my $test = shift;
    my $batch_extension = shift;
    my $pwd = shift;
    my $not_started_ref = shift; # reference to actual %not_started hash

    my $binary = "";

    debug_print(2," DEBUG:check_bin() checking $test\n");

    # iterate over each script and look for the necessary job binary
    for my $script ("sh","$batch_extension") {

        debug_print(3, " DEBUG: check_bin() checking $test/$test.$script\n");

        # parse each job script and pull out the specified job binary name
        open(FILE, "$pwd/$test/$test.$script") or print "Could not open $pwd/$test/$test.$script: $!\n" and return 1;
        while (<FILE>) {
            $_ =~ /Cbench job binary:\s+(\S+)\s*$/ and $binary = $1;
        }
        close(FILE);

        debug_print(3, " DEBUG: check_bin() binary: $binary\n");
        
        # something went wrong - every template should specify the job binary
        ($binary eq "") and error_print("'# Cbench job binary:' directive missing in $test/$test.$script\n") and return 1;

        # check for existence and executability of specified binary file
        if (!(-e $binary)) {
            $$not_started_ref{$test} = "$binary does not exist: $!\n";
            return 1;
        }
        if (!(-x $binary)) {
            $$not_started_ref{$test} = "$binary is not executable by user\n";
            return 1;
        }
    }
    return 0;
}


# 
# This routine contains the core functionality for the various
# *_start_jobs.pl scripts. We assume we are already in the
# directory containing the job scripts or directories of
# job scripts (like linpack or hpcc).
sub start_jobs {
	my $start_method = shift;
	my $match = shift;
	my $delay = shift;
	my $poll_delay = shift;
	my $maxprocs = shift; # not to be confused with $max_procs from cluster.def
	my $minprocs = shift;
	my $repeat = shift;
	my $batchargs = shift;
	my $optdata = shift; # optional, additional option data starting modes might need
        my $exclude = shift;

	# lsf wants the submit script to be redirected to the submission program bsub
	if ( $batch_extension eq "lsf" ) {
		$batchargs = $batchargs . " < ";
	}

	debug_print(1,"DEBUG:start_jobs() method=$start_method delay=$delay repeat=$repeat ".
		"max=$maxprocs min=$minprocs polldelay=$poll_delay match=\'$match\' exclude=\'$exclude\'\n");

	my %scripts = ();
	my %bench_list = ();
    my %not_started = ();
	my $total_jobs = 0;
	my @buf;
	my $cmd;
	my $maxprocs_scanned = 0;
	my $maxppn_scanned = 0;
	# we'll have to adjust when the 10000 core chips come :)
	my $minppn_scanned = 9999; 

	# get a master list of potential job scripts to execute
	$cmd = '/bin/ls -d1 *-*ppn-*';
	@buf = `$cmd 2>&1`;

	my $pwd = `pwd`;
	chomp $pwd;

	# parse the list of potential job scripts to execute
	foreach my $i (@buf) {
		chomp $i;
		$i =~ s/\.$batch_extension|\.sh//;

		# check the format of the job name
		($i !~ /^(\S+)\-(\S+)ppn\-(\d+)$/) and next;

		# process the filename based on regexes in $match and $exclude
		my $matchstr = "$match";
                my $excludestr = "$exclude";
		next unless ($i =~ /$matchstr/) and ($i !~ /$excludestr/);

		# number of processors in the job
		my ($bench,$ppn,$num_proc) = ($i =~ /^(\S+)\-(\S+)ppn\-(\d+)$/);
		$bench_list{$bench} = 1;

        # don't go over max number of procs as configured in cluster.def
        ($num_proc > $max_procs) and next;

		# if --nodes, --minnodes, or -maxnodes parameters were given, filter jobs that don't meet
		# the specified number of nodes
		my $numnodes = calc_num_nodes($num_proc,$ppn);
		if (exists $$optdata{numnodes}) {
			if ($numnodes != $$optdata{numnodes}) {
				debug_print(1,"DEBUG: Jobname $i (numnodes=$numnodes) doesn't".
					" match number of nodes required ($$optdata{numnodes})\n");
				next;
			}
		}
		if (exists $$optdata{minnumnodes}) {
			if ($numnodes < $$optdata{minnumnodes}) {
				debug_print(1,"DEBUG: Jobname $i (numnodes=$numnodes) cedes".
					" min number of nodes required ($$optdata{minnumnodes})\n");
				next;
			}
		}
		if (exists $$optdata{maxnumnodes}) {
			if ($numnodes > $$optdata{maxnumnodes}) {
				debug_print(1,"DEBUG: Jobname $i (numnodes=$numnodes) exceeds".
					" max number of nodes required ($$optdata{maxnumnodes})\n");
				next;
			}
		}

        # if $maxprocs is defined, don't run jobs bigger than that
		if (defined $maxprocs and $num_proc > $maxprocs) {
			debug_print(1,
				"DEBUG: Jobname $i (numprocs=$num_proc) exceeds max number of processes to use ($maxprocs)\n");
			next;
		}
        # if $minprocs is defined, don't run jobs smaller than that
		if (defined $minprocs and $num_proc < $minprocs) {
			debug_print(1,
				"DEBUG: Jobname $i (numprocs=$num_proc) cedes min number of processes to use ($minprocs)\n");
			next;
		}
       
        # check to see if specified binary exists and is executable
        if (check_bin($i,$batch_extension,$pwd,\%not_started)) {
			if ($start_method !~ /^batch/) {
				print "Skipping job".BOLD WHITE,"$i -- ".RESET,"$not_started{$i}";
			}
			next;
		}

		$scripts{$i} = $repeat;
		$total_jobs += $repeat;
		($num_proc > $maxprocs_scanned) and $maxprocs_scanned = $num_proc;
		($ppn > $maxppn_scanned) and $maxppn_scanned = $ppn;
		($ppn < $minppn_scanned) and $minppn_scanned = $ppn;
	}

	debug_print(1,"DEBUG:start_jobs() total_jobs=$total_jobs maxprocs_scanned=$maxprocs_scanned maxppn_scanned=$maxppn_scanned minppn_scanned=$minppn_scanned\n");

	if (defined $DEBUG and $DEBUG > 1) {
		print "DEBUG:start_jobs() Dump of \%bench_list:\n";
		print Dumper (\%bench_list);
		print "DEBUG:start_jobs() Dump of \%scripts:\n";
		print Dumper (\%scripts);
	}
   
	if ($start_method =~ /throttled/) {
		(defined $DRYRUN) and $poll_delay = 5;
		my $stamp = get_timestamp();
		print "($stamp) Intiating Throttled Batch mode with $$optdata{throttled_jobwidth} concurrent jobs:\n";
		print "($stamp) Total jobs to submit = $total_jobs\n";
		my $start = time;
		
		# build a regex to pass to batch_query to help better identify
		# the jobs we are interested in, i.e. cut down on the noise
		my $regex = '';
		foreach my $k (keys %bench_list) {
			$regex .= "$k|";
		}
		$regex =~ s/\|$//;
		(defined $DEBUG) and print "DEBUG:start_jobs(throttled) batch_query regex \'$regex\'\n";

		# throttledbatch starting mode, this is more complicated to pull off
		# since we need to poll the the batch scheduling system.
		my $all_jobs_submitted = 0;
		my %jobs = ();
		my $last_job_script = 'NADA';
		my $loops = 0;
		my $numscripts = keys %scripts;
		my $first_job_script =  (sort sort_by_numprocs keys(%scripts))[0];
		#print "DEBUG $first_job_script\n";

		while (! $all_jobs_submitted) {
			# query the batch system
			%jobs = batch_query($regex);

			my $stamp = get_timestamp();
			# The 'TOTAL' key in the %jobs hash will summarize how many running and
			# queued jobs there are for the user id running start_jobs for jobs
			# matching the $regex.  All that to say, the total of jobs we are
			# interested in tracking.
			my $num = $jobs{'TOTAL'};
			my $delta = $$optdata{throttled_jobwidth} - $num;

			# generate the throttled batch status line
			my $runtime = (time() - $start) / 60;
			print "($stamp) STATUS: Running=$jobs{'RUNNING'} Queued=$jobs{'QUEUED'} Unsubmitted=$total_jobs ";
			printf "Runtime(minutes)=%0.1f\n",$runtime;
			
			# figure out if we have submitting work to do
			if ($delta <= 0) {
				print "($stamp) At least $$optdata{throttled_jobwidth} jobs already running/queued...\n";
				# sleep until next poll cycle
				sleep $poll_delay;
				next;
			}
			my $tmpnum = ($delta < $total_jobs) ? $delta : $total_jobs;
			print "($stamp) Submitting $tmpnum more jobs...\n"
				unless ($last_job_script =~ /BACKTOTOP/);
			
			# if delta is > zero, then we have new jobs we need to submit 
			my $foundit = 0;
			my $deltaloops = 1;
			# if the number of job scripts is less than the number of jobs we need to
			# submit, we need to do the %scripts loop multiple times
			($numscripts < $delta) and ($deltaloops = int($delta/$numscripts) + 1);
			for (1..$deltaloops) {
				my $scripthash_index = 0;
			foreach my $i (sort sort_by_numprocs keys(%scripts)) {
				$scripthash_index++;

				# catch loop exit conditions
				($delta <= 0 or $total_jobs <= 0) and next;

				# look for the place in the script list we left off at...
				(defined $DEBUG and $DEBUG > 1) and print "DEBUG:start_jobs(throttled) loop=$loops d=$delta t=$total_jobs l=$last_job_script i=$i dl=$deltaloops n=$numscripts shidx=$scripthash_index\n";
				if ($last_job_script =~ /NADA|BACKTOTOP/) {
					$foundit = 1;
				}
				elsif (($i eq $last_job_script) and ($scripthash_index == $numscripts)) {
					# Since we matched the LAST job we submitted, we really want to pickup on
					# the next loop through %scripts which will get the next script name. However,
					# if the last script name was the last script in the sorted list of %scripts
					# keys, then we need to start at the top of the list.
						$last_job_script = 'BACKTOTOP';
				}
				elsif ($i eq $last_job_script) {
					$foundit = 1;
					# Since we matched the LAST job we submitted, we really want to pickup on
					# the next loop through %scripts which will get the next script name.
					($numscripts > 1) and next;
				}
				($foundit == 0) and next;
				(defined $DEBUG) and print "DEBUG:start_jobs(throttled) starting job submissions at $i\n";

				# check to see if we are done with this job already
				if ($scripts{$i} == 0) {
					(defined $DEBUG) and print "DEBUG:start_jobs(throttled) job $i has already been submitted $repeat times\n";
					next;
				}

				# ok, so now know what jobs to start submitting 
				# chdir into the job's directory
				(! -d $i) and next;
				(defined $DEBUG) and print "DEBUG:start_jobs(throttled) chdir $i\n";
				chdir $i;

				$stamp = get_timestamp();
				print "($stamp) Starting jobname $i ...\n";
				my $cmd = batch_submit_cmdbuild();
				$cmd .= "$batchargs $i\.$batch_extension";
				(defined $DEBUG) and print "DEBUG:start_jobs(throttled) cmd=$cmd\n";
				system($cmd) unless $DRYRUN;
				chdir $pwd;

				# keep track that we submitted this job and general stats
				$scripts{$i}--;
				$last_job_script = $i;
				$delta--;
				$total_jobs--;

				# be nice to the system and wait a sec
				(!defined $DRYRUN and defined $delay) and sleep $delay;

				#print "here2 d=$delta t=$total_jobs l=$last_job_script\n";
				# generate the throttled batch status line
				my $runtime = (time() - $start) / 60;
				print "($stamp) STATUS: Running=$jobs{'RUNNING'} Queued=$jobs{'QUEUED'} Unsubmitted=$total_jobs ";
				printf "Runtime(minutes)=%0.1f\n",$runtime;
			}
			}

			# check to see if we are done
			if ($total_jobs == 0) {
				# we are done
				$all_jobs_submitted = 1;
				next;
			}

			# sleep until next poll cycle
			if ($last_job_script !~ /BACKTOTOP/) {
				print "($stamp) Sleeping $poll_delay seconds until next poll...\n";
				sleep $poll_delay;
				$loops++;
			}
		}

		# Check to see if the --waitall option was given. If so, we wait until all
		# jobs have left the batch system (either run or deleted from queue)  before
		# exiting.
		if ($start_method =~ /waitall/) {
			while (1) {
				# query the batch system
				%jobs = batch_query($regex);

				my $stamp = get_timestamp();
				# The 'TOTAL' key in the %jobs hash will summarize how many running and
				# queued jobs there are for the user id running start_jobs for jobs
				# matching the $regex.  All that to say, the total of jobs we are
				# interested in tracking.
				my $num = $jobs{'TOTAL'};

				# if zero jobs total in the batch system, we can exit
				if ($num == 0) {
					print "($stamp) All jobs have exited the batch system...exiting.\n";
					last;
				}
				else {
					my $runtime = (time() - $start) / 60;
					print "($stamp) STATUS: Running=$jobs{'RUNNING'} Queued=$jobs{'QUEUED'} Unsubmitted=$total_jobs ";
					printf "Runtime(minutes)=%0.1f\n",$runtime;
					sleep $poll_delay;
					$loops++;

				}
			}
		}
	}
	elsif ($start_method =~ /combobatch/) {
		# combination batch mode
		#print Dumper (\%$optdata);

		# get into the combobatch test ident dir because we want to
		# build and submit jobs from here
		debug_print(2,"DEBUG:start_jobs(combo) chdir $$optdata{comboident_path}\n");
		chdir $$optdata{comboident_path};

		#
		# build the batch script we'll use to combine the multiple Cbench jobs
		# into a single batch job

		# find and read in the job templates. we don't really care about the job
		# templates
		my %templates = ();
		build_job_templates($$optdata{testset},\%templates);

		# init the buffer that will become the actual script
		my $outbuf = $templates{combobatch}{batch};

		# figure out how many nodes we'll actually need to contain the job
		# with the largest number of processors
		my $numnodes = calc_num_nodes($maxprocs_scanned,$minppn_scanned);

		# build a unique name for the combo job script
		my @combofiles = `ls -1 combobatch-????.$batch_extension 2>&1`;
		my $maxnum = 0;
		for (@combofiles) {
			(/no such file/) and last;
			chomp $_;
			my ($num) = $_ =~ /^combobatch-(\d+)\.$batch_extension$/;
			if ($num > $maxnum) {
				$maxnum = $num;
			}
			debug_print(3,"DEBUG:start_jobs(combo) $_, $num, $maxnum\n");
		}
		$maxnum++;
		my $jobname = sprintf "combobatch-%04d",$maxnum;

		# build the detail of the invocation data we'll tuck away in the 
		# batch script we are building
		my $timestamp = `/bin/date 2>&1`;
		chomp $timestamp;
		my $combodetails = "\n# timestamp: $timestamp\n";
		$combodetails .= "# commandline: $$optdata{commandline}\n".
		"# CBENCHOME: $$optdata{CBENCHOME}\n".
		"# CBENCHTEST: $$optdata{CBENCHTEST}\n".
		"# combobatch ident: $$optdata{comboident}\n".
		"# combobatch jobname: $jobname\n".
		"# maxnodes required: $numnodes\n".
		"# maxprocs_scanned: $maxprocs_scanned\n".
		"# maxppn_scanned: $maxppn_scanned\n".
		"# minppn_scanned: $minppn_scanned\n".
		"# total jobs matched: $total_jobs\n".
		"#\n";
		debug_print(2,"DEBUG:start_jobs(combo) combodetails=\n$combodetails");

		# here we do all the standard substitutions
		$outbuf = std_substitute($outbuf,$maxprocs_scanned,$minppn_scanned,$numnodes,
					'batch',$default_walltime,$$optdata{testset},$jobname,$ident,'combobatch');

		# custom substitutions
		$outbuf =~ s/COMBOBATCH_DETAILS_HERE/$combodetails/gs;
		$outbuf =~ s/CBENCHOME_HERE/$$optdata{CBENCHOME}/gs;
		$outbuf =~ s/CBENCHTEST_HERE/$$optdata{CBENCHTEST}/gs;
		$outbuf =~ s/MAXPROCS_HERE/$maxprocs_scanned/gs;
		$outbuf =~ s/MINPROCS_HERE/$minprocs/gs;
		$outbuf =~ s/REPEAT_HERE/$repeat/gs;
		$outbuf =~ s/MATCH_HERE/\'$match\'/gs;

		# write out the batch script for the combined batch run
		my $outfile = "$$optdata{comboident_path}\/$jobname\.$batch_extension";
		debug_print(1,"DEBUG:start_jobs(combo) outfile=$outfile");
		open (OUT,">$outfile") or die
			"Could not write $outfile ($!)";
		print OUT $outbuf;
		close(OUT);

		# so now we have our batch script, submit it....
		my $stamp = get_timestamp();
		print "Starting combination batch job $jobname ($stamp)...\n";
		my $cmd = batch_submit_cmdbuild();
		$cmd .= "$batchargs $jobname\.$batch_extension";
		debug_print(1, "DEBUG:start_jobs(combo) cmd=$cmd\n");
		system($cmd) unless $DRYRUN;

		chdir $$optdata{origpwd};
	}
	else {
		# plain old batch or interactive start mode
		my $job_count = 0;
		print "Found $total_jobs jobs to start in the ".uc($$optdata{testset})." testset\n";
		for my $iter (1..$repeat) {
			foreach $i (sort sort_by_numprocs keys(%scripts)) {
				# chdir into the job's directory
				(! -d $i) and next;
				debug_print(2,"DEBUG:start_jobs() chdir $i\n");
				chdir $i;

				my $stamp = get_timestamp();
				print "Starting jobname $i ($stamp)...\n";
				if ($start_method =~ /batch/) {
					my $cmd = batch_submit_cmdbuild();
					$cmd .= "$batchargs $i\.$batch_extension";
					debug_print(1, "DEBUG:start_jobs() cmd=$cmd\n");
					system($cmd) unless $DRYRUN;
				}
				else {
					my $cmd = "./$i\.sh";
					($$optdata{echooutput}) and $cmd = "CBENCH_ECHO_OUTPUT=YES $cmd";
					($$optdata{gazebo}) and $cmd = "CBENCH_GAZEBO=YES $cmd";
					debug_print(1, "DEBUG:start_jobs() cmd=$cmd\n");
					system($cmd) unless $DRYRUN;
				}

				chdir $pwd;

				$job_count++;

				# if the --delay parameter exists, then just sleep $delay between
				# jobs. otherwise submit jobs in a "bursty" way by submitting N
				# jobs without any sleep, and then between batches of N job submissions
				# sleep for a bit
				if (!defined $delay and ($start_method =~ /batch/)) {
					# submit jobs in a bursty way
					((($job_count % 32) == 0) and sleep 2) unless $DRYRUN;
				}
				elsif ($start_method =~ /interactive/) {
					(!defined $delay) and $delay = 1;
					sleep $delay;
				}
				else {
					sleep $delay unless $DRYRUN;
				}
			}
		}
		print "Started $job_count jobs in the ".uc($$optdata{testset})." testset (--ident \'$ident\').\n";
        # print error information for those jobs that failed check_bin()
        (keys(%not_started) > 0) and
			print RED BOLD " THE FOLLOWING JOBS WERE NOT STARTED DUE TO MISSING BINARIES:",RESET,"\n";

        for my $key (sort keys %not_started) {
            print BOLD WHITE "  $key -- ",RESET,"$not_started{$key}";
        }
        print "\n";

		return $job_count;
	}

}

sub sort_by_numprocs {
	my ($a_job, $a_ppn, $a_num) = $a =~ /^(\S+)-(\S+)-(\d+)$/;
	my ($b_job, $b_ppn, $b_num) = $b =~ /^(\S+)-(\S+)-(\d+)$/;

	$a_num <=> $b_num
}

sub sort_by_nodename {
	my ($a_pre, $a_num) = $a =~ /^(\D+)(\d+)$/;
	my ($b_pre, $b_num) = $b =~ /^(\D+)(\d+)$/;

	$a_pre cmp $b_pre
		or
	$a_num <=> $b_num
}



# This routine will run an instance the specfied command line
# per CPU that linux sees and return a collated buffer with
# the resulting output.
#
# If an optional third argument is given and evaluates to true (1 will do),
# we will try to use linux CPU affinity calls to restrict which CPU each
# process can be scheduled on.  Currently we do a 1-1 mapping of processes to
# CPUs, but other mappings are possible (and may become useful in the future
# if we become multi-core/hyperthreading-aware).
#
# If an optional fourth argument is given and is true, only a single process
# will be run as opposed to a process per cpu.
#
# Thanks to Nathan Dauchy and his work on CIT for the core
# of this multiprocess output groking code.
sub run_process_per_cpu {
	my $cmd = shift;  # command string
	my $bufref = shift; #array reference where output will be put
	my $cpu_affinity = shift; # whether or not CPU affinity calls are used
	my $single = shift;

	# if we've already caught an INT signal, don't run anything else
	if ($main::INTsignalled) {
		debug_print(1,"DEBUG:run_process_per_cpu() SIGINT seen...exiting\n");
		$$bufref[0] = "Exiting due to SIGINT...\n";
	}

	use IPC::Open3;
	use IO::Select;
	use Symbol;
	use POSIX ":sys_wait_h";
	
	(defined $DEBUG and $single) and print
		"DEBUG:run_process_per_cpu() single process only mode\n";

	# we need a hash to save the mapping of file descriptor fileno values
	# to the forked process
	my %filehash = ();
	
	# store the output from each process in this
	my %outbuf = ();
	
	my $selector = IO::Select->new();

	# create a forked instance of $cmd per cpu unless $single is true
	my $numcpus;
	if ($single) {
		$numcpus = 1;
	}
	else {
		$numcpus = linux_num_cpus();
	}

	for $cpu (1..$numcpus) {
		my ($in, $out, $err) = (undef, undef, gensym);

		if ($cpu_affinity) {
			(defined $DEBUG) and print
				"DEBUG:run_process_per_cpu() CPU affinity mode\n";

			# The CPU bitmask to use for taskset.  Currently
			# we do a 1-1 mapping of processes to processors.
			my $cpumask = 1 << ($cpu - 1);

			if ( -x $TASKSET ) {
				$cmd = "$TASKSET $cpumask " . $cmd;
			} else {
				warn "Warning: taskset utility ($TASKSET) not found.  No CPU affinity calls will be made.";
			}
		}
		
		my $t = time;
		(defined $DEBUG) and print "DEBUG:run_process_per_cpu($t) cpu=$cpu cmd=$cmd\n";

		# fork off a child to run the command
		unless ($child = open3($in, $out, $err, "$cmd")) {
			# we are a child
			exit;
		}

		# we are the parent
		$main::childpids{$child} = 1;
		my $t = time;
		(defined $DEBUG and $DEBUG > 1 ) and print 
			"DEBUG:run_process_per_cpu($t) started child process $child\n";

		# close stdin handle immediately to avoid deadlocks
		close $in;

		# save the fileno information
		$filehash{fileno($out)} = $cpu;
		$filehash{fileno($err)} = $cpu;

		(defined $DEBUG and $DEBUG > 1 ) and print 
			"DEBUG:run_process_per_cpu() cpu$cpu stdout fileno " .
			fileno($out) . "\n";
		(defined $DEBUG and $DEBUG > 1 ) and print
			"DEBUG:run_process_per_cpu() cpu$cpu sterr fileno " .
			fileno($err) . "\n";

		# add the filehandles to the select polling list
		$selector->add($out,$err);
	}

	my $t = time;
	debug_print(2,"DEBUG:run_process_per_cpu($t) started all children\n");

	# poll for the output from all the remote forked processes
	while (my @ready = $selector->can_read) {
		foreach (@ready) {
			if (eof($_)) {
				$selector->remove($_);
			} else {
				# cat the output to the appropriate buffer
				$outbuf{$filehash{fileno($_)}} .= scalar <$_>;
			}

		}
	}

	my $t = time;
	debug_print(2,"DEBUG:run_process_per_cpu($t) exited forked process polling loop\n");

	# wait for the children to finish in a non-blocking fashion
	for (keys %main::childpids) {
		if (waitpid($_,&WNOHANG)) {
			# child is gone
			delete $main::childpids{$_};
			
			my $t = time;
			(defined $DEBUG and $DEBUG > 1) and print
				"DEBUG:run_process_per_cpu($t) child $_ is gone\n";
		}
		sleep 1;
	}

	# now we need to return a nice collated buffer with a little
	# bit of delimiting so the caller knows what output is from
	# which process
	for $cpu (sort {$a <=> $b} (keys %outbuf)){
		(defined $DEBUG and $DEBUG > 1 ) and print 
			"DEBUG:run_process_per_cpu() adding process $cpu output\n";

		push @$bufref, "====> process $cpu\/$numcpus begin\n" unless $single;
		foreach (split("\n",$outbuf{$cpu})) {
			push @$bufref, "$_\n";
		}
		push @$bufref, "====> process $cpu\/$numcpus end\n" unless $single;
	}
}


# Run a single process regardless of CPU count using the infrastructure already
# provided by run_process_per_cpu().
sub run_single_process {
	my $cmd = shift;  # command string
	my $bufref = shift; #array reference where output will be put

	(defined $DEBUG) and print "DEBUG:run_single_process() cmd=$cmd\n";
	run_process_per_cpu($cmd,$bufref,0,1);
}
	
# Get the number of physical cores Linux sees. This could be misleading
# depending on Hyperthreading and multi-core chips.
#
# takes an optional boolean parameter that tells us to return
# the number of logical cpus
sub linux_num_cpus {
	my $use_logical = shift;

	my $num_logical_cpus = 0;
	my $num_physical_cpus = 0;
	my $num_cores = 0;

	if (defined $NUMCPUS) {
		debug_print(2,"DEBUG:linux_num_cpus() overriding by NUMCPUS var, num=$NUMCPUS\n");
		return $NUMCPUS;
	}

	my @buf = `/bin/cat /proc/cpuinfo`;

	my %cpumap = linux_parse_cpuinfo(\@buf);

	# decode what the cpumap hash tells us
	foreach (keys %cpumap) {
		($_ =~ /model/) and next;
		$num_physical_cpus++;
		$num_cores += $cpumap{$_}{'cores'};
		$num_logical_cpus += scalar @{$cpumap{$_}{'logical'}};
	}

	# if we didn't see anything about physical ids, we assume that the number of logical
	# cpus is the number of actual cpu cores
	if (exists $cpumap{'COUNT'}) {
		$num_physical_cpus = $num_cores = $num_logical_cpus = $cpumap{'COUNT'};
	}

	debug_print(2,"DEBUG:linux_num_cpus() physical=$num_physical_cpus ".
			"logical=$num_logical_cpus num_cores=$num_cores\n");

	if ($num_cores < 1) {
		warning_print("linux_num_cpus() Weird...num_cores < 0\n");
		$num_cores = 1;
	}

	if (defined $use_logical and $use_logical) {
		return $num_logical_cpus;
	}
	else {
		return $num_cores;
	}
}

# Get the number of physical sockets Linux sees. This could be misleading
# depending on Hyperthreading and multi-core chips.
sub linux_num_sockets {

	my $num_logical_cpus = 0;
	my $num_physical_cpus = 0;
	my $num_cores = 0;

	my @buf = `/bin/cat /proc/cpuinfo`;

	my %cpumap = linux_parse_cpuinfo(\@buf);

	# decode what the cpumap hash tells us
	foreach (keys %cpumap) {
		($_ =~ /model/) and next;
		$num_physical_cpus++;
		$num_cores += $cpumap{$_}{'cores'};
		$num_logical_cpus += scalar @{$cpumap{$_}{'logical'}};
	}

	# if we didn't see anything about physical ids, we assume that the number of
	# logical cpus is the number of actual sockets. not necessarily the right
	# assumption potentially...
	if (exists $cpumap{'COUNT'}) {
		$num_physical_cpus = $num_cores = $num_logical_cpus = $cpumap{'COUNT'};
	}

	debug_print(2,"DEBUG:linux_num_sockets() sockets=$num_physical_cpus ".
			"logical=$num_logical_cpus num_cores=$num_cores\n");

#	if ($num_cores < 1) {
#		warning_print("linux_num_sockets() Weird...num_cores < 0\n");
#		$num_cores = 1;
#	}

	return $num_physical_cpus;
}

# grok /proc/cpuinfo on Linux into a hierarchical hash
sub linux_parse_cpuinfo {
	my $buf = shift;

	# /proc/cpuinfo behaves differently depending on kernel versions and even
	# with the same kernel version on differing generations of the same AMD/Intel
	# processors. So we have to check several things...

	my %cpumap = ();
	my $physcal_context;
	my $logical_context;
	my $found_physical = 0;
	my $num_logical_cpus = 0;
	
	foreach (@$buf) {	
    	if (/processor\s+:\s*(\d+)\s*\S*/i) {
			$logical_context = $1;
			$num_logical_cpus++;
		}
    	elsif (/physical id\s+:\s*(\d+)\s*/i) {
			$physical_context = $1;
			$found_physical = 1;
			push @{$cpumap{"physical $physical_context"}{'logical'}}, $logical_context;
		}
    	elsif (/siblings\s+:\s*(\d+)\s*/i) {
			($found_physical) and $cpumap{"physical $physical_context"}{'siblings'} = $1;
		}
    	elsif (/core id\s+:\s*(\d+)\s*/i) {
			($found_physical) and push @{$cpumap{"physical $physical_context"}{'coreids'}}, $1;
		}
    	elsif (/cpu cores\s+:\s*(\d+)\s*/i) {
			($found_physical) and $cpumap{"physical $physical_context"}{'cores'} = $1;
		}
		elsif (/model name\s+:\s+(.*)$/i) {
			push @{$cpumap{'model'}}, $1;
		}
		elsif (/cpu MHz\s+:\s+(.*)$/i) {
			${$cpumap{'model'}}[$num_logical_cpus-1] .= ", $1 MHz";
		}

	}

	(defined $DEBUG and $DEBUG > 2 ) and do {
		debug_print(3,"DEBUG:linux_parse_cpuinfo()\n===================\n");
		print Dumper (\%cpumap);
		debug_print(3,"===================\n");
	};

	# if we didn't see anything about physical ids, we assume that the number of logical
	# cpus is the number of actual cpu cores
	if (!$found_physical) {
		$cpumap{'COUNT'} = $num_logical_cpus;
		debug_print(1,"DEBUG:linux_parse_cpuinfo() No physical, core info found\n");
	}

	return %cpumap;
}

# Get the memory picture from Linux and figure out how much
# useable memory there is to be allocated
sub linux_useable_memory {
	my $vals = parse_meminfo();
	my $buffer_reuse_factor = 0.1;

	if (defined $MAXMEM) {
		debug_print(2,
			"DEBUG:linux_useable_memory() overriding by MAXMEM var, num=$MAXMEM\n");
		return ($MAXMEM * 1024);
	}

	# amount of memory to target to hold in reserve, in MBytes
	my $reserved_target = 256 * (1024);

	# if the vm.min_free_kbytes value is larger that $reserved_target,
	# then use it 
	if ( -f '/proc/sys/vm/min_free_kbytes' ) {
		$min_free = `cat /proc/sys/vm/min_free_kbytes`;
		chomp $min_free;
		if ($min_free =~ /^\d+$/) {
			if ($min_free > $reserved_target) {
				$reserved_target = $min_free + (100 * 1024);
				defined $DEBUG and print
					"DEBUG: linux_useable_memory() using min_free_kbytes of $reserved_target".
					" for reserved memory target\n";
			}
		}
	}

	my $useable = $vals->{'MemFree'} - $reserved_target;

	# sometimes diskless type nodes may not have swap. if this is
	# the case then we can't be quite as aggressive with using all
	# of free memory.
	#
	# trying to preserve about 100MB of extra free virtual memory as a guess
	my $reserved = 100 * (1024);
	if ($vals->{'SwapFree'} < $reserved) {
		my $tmp = $reserved - $vals->{'SwapFree'};
		$useable -= $tmp;
		defined $DEBUG and print
			"DEBUG: linux_useable_memory() reserving an extra $tmp KB of ".
			"memory due to low virtual memory\n";
	}
	
	$useable += int ($vals->{'Buffers'} * $buffer_reuse_factor);

	# even out the number 
	(($useable % 2) == 1) and $useable--;

	(defined $DEBUG and $DEBUG > 1 ) and print 
		print "DEBUG:linux_useable_memory() useable=$useable KB\n";

	return $useable;
}

# Get the memory picture from Linux and figure out how much
# total RAM is seend
sub linux_total_memory {
	my $vals = parse_meminfo();

	(defined $DEBUG and $DEBUG > 1 ) and print 
		"DEBUG:linux_total_memory() total=$vals->{'MemTotal'} KB\n";

	return $vals->{'MemTotal'};
}

# parse the output of Linux's /proc/meminfo
sub parse_meminfo {
	my %vals = ();

	my @buf = `/bin/cat /proc/meminfo`;
	foreach (@buf) {
		if (/Mem:[\s+\d+]+|Swap:[\s+\d+]+|\s+total:\s+used:/) {
			# this is Linux 2.4 specific syntax, we don't want
			# to parse it
			next;
		}
		elsif (/(\S+):\s+(\d+)\s+/) {
			# these lines seem to be consistent between 2.4 and
			# 2.6 linux kernels
			$vals{$1} = $2;

			(defined $DEBUG and $DEBUG > 2 ) and print 
				"DEBUG:parse_meminfo() $1 => $2\n";
		}
	}

	return \%vals;
}


# Find all the 'local' filesystems on a node and return a
# hash listing them. Local could be a debateable definition
# but for our purposes we'll say that local filesystems are
# those originating from a block device we can see on the
# node such as a SCSI/IDE disk or a Fibre Channel attached
# lun.
# By default we only report local filesystems that are
# writeable at the root of the filesystem for the current
# userid.
sub find_local_filesystems {
	# List of physical devices we think we've seen. This is a little
	# different from the block devices in that we try to find only
	# one filesystem per physical device.
	my %physical = ();

	# we need to try to figure out which filesystems are mounted on 
	# block devices local to this node
	#my @partitions = `/bin/cat /proc/partitions`;
	#my @mounts = `/bin/cat /proc/mounts`;
	my @mounts = `/bin/mount`;
	my %fslist = ();
	foreach (@mounts) {
		chomp $_;
		# right now we only know about certain filesystems
		next unless (/\s+(ext2|ext3|reiserfs|xfs)\s+/);
		# don't test /boot filesystems since they are generally
		# small
		(/\/boot/) and next;

		# split up the mount output
		my @fields = split(" ",$_);
		my $opts = $fields[5];
		my ($physdev) = $fields[0] =~ /(\D+)\d+/;

		# sanity check for a non-rw mounted fs
		if (!($opts =~ /rw/)) {
			debug_print(2,"DEBUG:find_local_filesystems() $fields[2] is not read-write,".
				" ignoring...\n");
			next;
		}

		if (! exists $physical{$physdev}) {
			# check to see if we have write permissions
			if (!path_is_writeable("$fields[2]")) {
				# we can't write to at least the root of the filesystem, so ignore it
				# because we can't figure out in general where to look
				debug_print(2,"DEBUG:find_local_filesystems() do not have write permissions ".
					" for $fields[2], ignoring...\n");
				next;
			}

			$physical{$physdev} = 1;
			$fslist{$fields[2]}{'dev'} = $fields[0];
			debug_print(1,"DEBUG:find_local_filesystems() added $fields[2], ".
				"dev=$fields[0],physdev=$physdev,$opts\n");
		}
		else {
			debug_print(2,"DEBUG:find_local_filesystems() ignored $fields[2], ".
				"dev=$fields[0],physdev=$physdev,$opts\n");
		}
	}
	return %fslist;
}


# Check to see if the given path seems to reside on a local disk
sub path_is_on_localdisk {
	my $testpath = shift;

	# try to figure out where the path is mounted
	my @mounts = `/bin/df -T $testpath`;
	my %fslist = ();
	foreach (@mounts) {
		chomp $_;
		# right now we only know about certain filesystems
		next unless (/\s+(ext2|ext3|reiserfs|xfs)\s+/);
		# don't test /boot filesystems since they are generally small
		(/\/boot/) and next;
		my @fields = split(" ",$_);
		debug_print(2,"DEBUG:path_is_on_localdisk() $testpath is on localdisk $fields[0]\n");
		return 1;
	}
	debug_print(2,"DEBUG:path_is_on_localdisk() $testpath is NOT on localdisk\n");
	return 0;
}

# Test if we have write permissions to the given path
sub path_is_writeable {
	my $testpath = shift;
	
	debug_print(1,"DEBUG:path_is_writeable() testpath=$testpath\n");

	# we need a temp file in the path to play with
	my $tmppath = $testpath;
	$tmppath =~ s/\///g;
	my $tmpfile = "$testpath/.cbench_hw-test_iozone_$tmppath\_$$";
	debug_print(2,"DEBUG:path_is_writeable() tmpfile=$tmpfile\n");

	if (open(TESTOUT,">$tmpfile")) {
		my $result = print TESTOUT "testing 1 2 3.............\n";	
		close(TESTOUT);
		unlink($tmpfile);
		($result) and return 1;
		return 0;
	}
	else {
		debug_print(2,"DEBUG:path_is_writeable() open failed with \'$!\' for $tmpfile\n");
		return 0;
	}
}

# Search for and attempt to load all modules found in the
# Cbench gen_jobs library. This subroutine provides the core
# of the dynamic 'plug-in' functionality for the Cbench
# job generating framework.
#
# The routine expects a reference to a hash as input.
#
# The routine populates the hash with keys named for a
# genjobs module that was successfully loaded and values
# that are a reference to a parse  object that was created
# with the loaded module.
sub load_genjobs_modules {
	die "load_genjobs_modules() takes one arguments as input"
		if (@_ != 1);
	
	my $href = shift;

	@raw_modules = ();

	# Get a list of all the Perl modules in the Cbench genjobs library,
	# CBENCHOME/perllib/gen_jobs by default. We also look in a list
	# of locations specified by the CBENCHADDON environment variable.
	my @dirs = ("$BENCH_HOME/perllib/gen_jobs");
	my $addon = get_cbench_addon();
	if (defined $addon) {
		push @dirs, "$addon/perllib/gen_jobs";
		# add this to the Perl lib path
		unshift @INC, "$addon/perllib";
	}
	debug_print(3, "DEBUG:load_genjobs_modules() dirs=@dirs");
	foreach my $dir (@dirs) {
		if (opendir(BIN, $dir)) { 
			while( defined (my $file = readdir BIN) ) {
				next if $file =~ /^\.\.?$/;  # skip . and ..
				next unless $file =~ /^\S+\.pm$/;  # only process .pm files
				debug_print(2, "DEBUG: found $file\n");
				($mod) = $file =~ /(\S+)\.pm/;
				push @raw_modules, $mod;
			}
			closedir(BIN);
		}
		else {
			debug_print(1,"WARNING: Can't open $dir: $!");
		}
	}

	# For each parse module we found, try to 'require' it and see if
	# we can use it properly. Need to make sure that CBENCHADDON directories
	# are in the lib path
	for (@raw_modules) {
		eval "require gen_jobs::$_";
		#require gen_jobs::purple;
		if ($@ =~ /Can't locate gen_jobs/) {
			warning_print("$_ gen_jobs module not supported.  (gen_jobs::$_ not found)\n");
		} elsif ($@) {
			warning_print("Error loading 'gen_jobs::$_'.\n\n$@\n");
		}
		else {
			my $tobj = "gen_jobs::$_"->new();
			if ($tobj) {
				# success! save the module name and object ref
				$$href{$_} = $tobj;
				debug_print(1, "DEBUG: loaded gen_jobs::$_ module\n");
			}
			else {
				warning_print("Error initializing gen_jobs::$_ object!\n");
			}
		}
	}
}


# Search for and attempt to load all modules found in the
# Cbench hw_test library. This subroutine provides the core
# of the dynamic 'plug-in' functionality for the Cbench
# hw_test framework.
#
# The routine expects a reference to a hash and a filehandle
# as input.
#
# The routine populates the hash with keys named for a
# hw_test module that was successfully loaded and values
# that are a reference to a hw_test object that was created
# with the loaded module.
sub load_hwtest_modules {
	die "load_hwtest_modules() takes two arguments as input"
		if (@_ != 2);
	
	my $href = shift;
	my $ofh = shift;

	@raw_modules = ();

	# Get a list of all the Perl modules in the Cbench hw_test library,
	# CBENCHOME/lib/hw_test.
	$dir = "$BENCH_HOME/perllib/hw_test";
	opendir(BIN, $dir) or die "Can't open $dir: $!";
	while( defined ($file = readdir BIN) ) {
		next if $file =~ /^\.\.?$/;  # skip . and ..
		next unless $file =~ /^\S+\.pm$/;  # only process .pm files
		(defined $DEBUG and $DEBUG > 1) and print "DEBUG: found $file\n";
		($mod) = $file =~ /(\S+)\.pm/;
		push @raw_modules, $mod;
	}
	closedir(BIN);

	# For each hw_test module we found, try to 'require' it and see if
	# we can use it properly.
	for (@raw_modules) {
		eval "require hw_test::$_";
		#require hw_test::$_;
		if ($@ =~ /Can't locate hw_test/) {
			print "$_ test module not supported.  (hw_test::$_ not found)\n";
		} elsif ($@) {
			print "Error loading 'hw_test::$_'.\n\n$@\n";
		}
		else {
			my $tobj = "hw_test::$_"->new($ofh);
			if ($tobj) {
				# success! save the module name and object ref
				$$href{$_} = $tobj;
				defined $DEBUG and print
					"DEBUG: loaded hw_test::$_ module, test_class=" .
					$tobj->test_class . "\n";
			}
			else {
				print "Error initializing hw_test::$_ object!\n";
			}
		}

	}
}


# Search for and attempt to load all modules found in the
# Cbench output_parse library. This subroutine provides the core
# of the dynamic 'plug-in' functionality for the Cbench
# output parsing framework.
#
# The routine expects a reference to a hash as input.
#
# The routine populates the hash with keys named for a
# hw_test module that was successfully loaded and values
# that are a reference to a parse  object that was created
# with the loaded module.
sub load_parse_modules {
	die "load_parse_modules() takes one arguments as input"
		if (@_ != 1);
	
	my $href = shift;

	@raw_modules = ();

	# Get a list of all the Perl modules in the Cbench parse library,
	# CBENCHOME/perllib/output_parse.
	my @dirs = ("$BENCH_HOME/perllib/output_parse");
	my $addon = get_cbench_addon();
	if (defined $addon) {
		push @dirs, "$addon/perllib/output_parse";
		# add this to the Perl lib path
		unshift @INC, "$addon/perllib";
	}
	debug_print(3, "DEBUG:load_parse_modules() dirs=@dirs");
	foreach my $dir (@dirs) {
		if (opendir(BIN, $dir)) { 
			while( defined ($file = readdir BIN) ) {
				next if $file =~ /^\.\.?$/;  # skip . and ..
				next unless $file =~ /^\S+\.pm$/;  # only process .pm files
				(defined $DEBUG and $DEBUG > 1) and print "DEBUG: found $file\n";
				($mod) = $file =~ /(\S+)\.pm/;
				push @raw_modules, $mod;
			}
			closedir(BIN);
		}
		else {
			debug_print(1,"WARNING: Can't open $dir: $!");
		}
	}

	# For each parse module we found, try to 'require' it and see if
	# we can use it properly.
	for (@raw_modules) {
		eval "require output_parse::$_";
		#require output_parse::$_;
		if ($@ =~ /Can't locate output_parse/) {
			print "$_ output_parse module not supported.  (output_parse::$_ not found)\n";
		} elsif ($@) {
			print "Error loading 'output_parse::$_'.\n\n$@\n";
		}
		else {
			my $tobj = "output_parse::$_"->new($ofh);
			if ($tobj) {
				# success! save the module name and object ref
				$$href{$_} = $tobj;
				defined $DEBUG and print
					"DEBUG: loaded output_parse::$_ module\n";
			}
			else {
				print "Error initializing output_parse::$_ object!\n";
			}
		}

	}
}


# Search for and attempt to load all modules found in the
# Cbench parse_filter library.
#
# The routine expects a reference to a hash as input.
#
# The routine populates the hash with keys named for a
# parse_filter module that was successfully loaded and values
# that are a reference to a parse  object that was created
# with the loaded module.
sub load_parse_filter_modules {
	die "load_parse_filter_modules() takes one arguments as input"
		if (@_ != 1);
	
	my $href = shift;

	@raw_modules = ();

	# Get a list of all the Perl modules in the Cbench parse library,
	# CBENCHOME/perllib/parse_filter.
	$dir = "$BENCH_HOME/perllib/parse_filter";
	opendir(BIN, $dir) or die "Can't open $dir: $!";
	while( defined ($file = readdir BIN) ) {
		next if $file =~ /^\.\.?$/;  # skip . and ..
		next unless $file =~ /^\S+\.pm$/;  # only process .pm files
		(defined $DEBUG and $DEBUG > 1) and print "DEBUG: found $file\n";
		($mod) = $file =~ /(\S+)\.pm/;
		push @raw_modules, $mod;
	}
	closedir(BIN);

	# For each parse module we found, try to 'require' it and see if
	# we can use it properly.
	for (@parse_filter_include) {
		eval "require parse_filter::$_";
		#require "parse_filter::$_";
		if ($@ =~ /Can't locate parse_filter/) {
			print "$_ parse_filter module not supported.  (parse_filter::$_ not found)\n";
		} elsif ($@) {
			print "Error loading 'parse_filter::$_'.\n\n$@\n";
		}
		else {
			local $symname = "parse_filter::". $_ ."::parse_filters";
			*sym = \%$symname;
			#print Dumper (\%sym),"\n";
			foreach my $k (keys %sym) {
				$$href{$k} = $sym{$k};
			}

			defined $DEBUG and print
				"DEBUG: loaded parse_filter::$_ filters\n";
		}
	}
	#print Dumper (\%main::parse_filters);
}


# Subroutine to convert a "list" of node names stored as a hash
# with the names as the keys to a pdsh style compressed list
sub hash_to_pdshlist {
	my $hashref = shift;
	
	my $lastpre = 'NADA';
	my $lastnum = 0xdeadbeef;
    my $firstnum = 0xdeadbeef;
	my $inrange = 0;
	my $nodelist = '';
	my $pre;
	my $num;

	if ( -x "$BENCH_HOME/sbin/hostlist" ) {
		(defined $DEBUG) and print "DEBUG:pdshlist_to_hash() list=$nodelist found hostlist in $BENCH_HOME/sbin/hostlist ... tight!\n";
		foreach my $node (keys (%{$hashref})) {
			$nodelist .= $node . " ";
		}
		$nodelist = `$BENCH_HOME/sbin/hostlist -c $nodelist`;
		chomp $nodelist;
#		open (DATA, "$BENCH_HOME/sbin/hostlist -e $nodelist|") or die "Failed to run $BENCH_HOME/sbin/hostlist $nodelist ... $!";
#		my @data = <DATA>;
#		close DATA;
		#foreach my $n (@data) {
		#	chomp $n;
		#	$hashref->{$n} = 1;
			#$num++;
		#}
	} else {

	foreach my $node (sort sort_by_nodename keys(%{$hashref})) {
		($pre, $num) = $node =~ /(\D+)(\d+)/;
		# ignore nodes that have been excluded from the hash, like
		# nodehwtest_start_jobs.pl does for instance
		($hashref->{$node} == 0xdead) and next;

		(defined $DEBUG and $DEBUG > 2) and print "DEBUG:hash_to_pdshlist() ".
			"node=$node pre=$pre num=$num\n";

		if ($lastpre eq 'NADA') {
			$nodelist .= "$pre\[";
			$lastpre = $pre;
		}
		elsif ($pre ne $lastpre) {
			if ($inrange) {
				$nodelist .= "\-$lastnum\],$pre\[";
			}
			else {
				$nodelist .= "\],$pre\[";
			}
			$lastpre = $pre;
            $lastnum = 0xdeadbeef;
		}

		if ($lastnum == 0xdeadbeef) {
			$nodelist .= "$num";
			$lastnum = $num;
			$firstnum = $num;            
		}
		elsif ($num > ($lastnum + 1)) {
        	if ($firstnum == $lastnum) {
			    $nodelist .= ",$num";            
            }
            else {
			    $nodelist .= "\-$lastnum,$num";
            }
			$lastnum = $num;
            $firstnum = $num;
			$inrange = 0;
		}
		elsif ($num == ($lastnum + 1)) {
			$lastnum = $num;
			$inrange = 1;
		}
		(defined $DEBUG and $DEBUG > 2) and print "DEBUG:hash_to_pdshlist() ".
			"nodelist=$nodelist\n";
	}

	if ($inrange) {
		$nodelist .= "\-$num\]";
	}
	else {
		$nodelist .= "\]";
	}

	}

	return $nodelist;
}


# Subroutine to convert a pdsh style compressed node list, e.g.
#   an[1-10,20,21-40],bn[1-24]
# to a hash with a unique list of node names.
sub pdshlist_to_hash {
	my $nodelist = shift;
	my $hashref = shift;

	(defined $DEBUG) and print "DEBUG:pdshlist_to_hash() list=$nodelist\n";

	my $num = 0;

	if ( -x "$BENCH_HOME/sbin/hostlist" ) {
		(defined $DEBUG) and print "DEBUG:pdshlist_to_hash() list=$nodelist found hostlist in $BENCH_HOME/sbin/hostlist ... tight!\n";
		open (DATA, "$BENCH_HOME/sbin/hostlist -e $nodelist|") or die "Failed to run $BENCH_HOME/sbin/hostlist $nodelist ... $!";
		my @data = <DATA>;
		close DATA;
		foreach my $n (@data) {
			chomp $n;
			$hashref->{$n} = 1;
			$num++;
		}
	} else {

	my $pre;
	my @sub = split ',', $nodelist;
	foreach (@sub) {
		(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pdshlist_to_hash() ".
			"sub=$_\n";
		if (/^(\D+)\[(\d+)\-(\d+)\]*$/) {
			$pre = $1;
			my $begin = $2;
			my $end = $3;
			for my $i ($begin..$end) {
				my $n = $pre.$i;
				$hashref->{$n} = 1;
				$num++;
			}
			(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pdshlist_to_hash() ".
				"$pre\[$begin\-$end  #1\n";
		}
		elsif (/^(\D+)\[(\d+)\]$/) {
			$pre = $1;
			my $n = $pre.$2;
			$hashref->{$n} = 1;
			$num++;
			(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pdshlist_to_hash() ".
				"$pre\[$begin\]  #2\n";
		}
		elsif (/^(\D+)\[(\d+)$/) {
			$pre = $1;
			my $n = $pre.$2;
			$hashref->{$n} = 1;
			$num++;
			(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pdshlist_to_hash() ".
				"$pre\[$2  #3\n";
		}
		elsif (/^(\D+)(\d+)$/) {
			$pre = $1;
			my $n = $pre.$2;
			$hashref->{$n} = 1;
			$num++;
			(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pdshlist_to_hash() ".
				"$pre"."$begin  #4\n";
		}
		elsif (/^(\d+)\-(\d+)\]*$/) {
			my $begin = $1;
			my $end = $2;
			for $i ($begin..$end) {
				my $n = $pre.$i;
				$hashref->{$n} = 1;
				$num++;
			}
			(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pdshlist_to_hash() ".
				"$begin\-$end  #5\n";
		}
		elsif (/^(\d+)\]$/) {
			my $n = $pre.$1;
			$hashref->{$n} = 1;
			$num++;
			(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pdshlist_to_hash() ".
				"$1\]  #6\n";
		}
		elsif (/^(\d+)$/) {
			my $n = $pre.$1;
			$hashref->{$n} = 1;
			$num++;
			(defined $DEBUG and $DEBUG > 2) and print "DEBUG:pdshlist_to_hash() ".
				"$1  #7\n";
		}
		else {
			(defined $DEBUG and $DEBUG > 1) and print "DEBUG:pdshlist_to_hash() ".
				"$_ did not match any cases...\n";
		}
	}

	}

	if (defined $DEBUG and $DEBUG > 2) {
		foreach my $k (keys %$hashref) {
			print "DEBUG:pdshlist_to_hash() node=$k\n";
		}
	}
	(defined $DEBUG) and print "DEBUG:pdshlist_to_hash() $num nodes in list\n";
}


# Build a remote execution command based on cluster.def
sub remotecmd_cmdbuild {
	my $funcname = "$remotecmd_method\_remote_cmdbuild";
	*func = \&$funcname;
	($DEBUG and $DEBUG > 1) and print "DEBUG: using $funcname for remotecmd substitution\n";
	return func(@_);
}


# Build a batch submission command based on cluster.def
sub batch_submit_cmdbuild {
	my $funcname = "$batch_method\_batchsubmit_cmdbuild";
	*func = \&$funcname;
	($DEBUG and $DEBUG > 1) and print "DEBUG: using $funcname for batch submit substitution\n";
	return func();
}

# Build a string for a batch system to specify specific nodes to
# use in a batch script.  Hopefully other batch systems functionality
# for this can be capture by building a simple string like Torque/PBS
# does. 
sub batch_nodespec_build {
	# ref to array of a list of nodes
	my $nodearray = shift;

	my $funcname = "$batch_method\_nodespec_build";
	*func = \&$funcname;
	($DEBUG and $DEBUG > 1) and print "DEBUG: using $funcname for batch nodespec building\n";
	return func($nodearray);
}

# Build a batch system query command based on cluster.def and return a hash of information
# about what is running
sub batch_query {
	my $funcname = "$batch_method\_query";
	*func = \&$funcname;
	($DEBUG and $DEBUG > 1) and print "DEBUG: using $funcname for batch submit substitution\n";
	return func(@_);
}

# Do the standard cbench substitutions on the given string
sub std_substitute {
	my $string = shift;
	my $numprocs = shift;
	my $ppn = shift;
	my $numnodes = shift;
	my $runtype = uc shift;
	my $walltime = shift;
	my $testset = shift;
	my $jobname = shift;
	my $ident = shift;
	my $benchmark = shift;  # aka job name

	my $benchtest = get_bench_test();	
	if (defined $JOBCBENCHTEST) {
		defined ($DEBUG) and
			print "DEBUG: overriding CBENCHTEST with $JOBCBENCHTEST in substitutions\n";
		$benchtest = $JOBCBENCHTEST;
	}

	# build the job launching command and substitute
	my $funcname = "$joblaunch_method\_joblaunch_cmdbuild";
	*func = \&$funcname;
	($DEBUG > 1) and print "DEBUG: using $funcname for job launch substitution\n";
	my $jobcmd = func($numprocs,$ppn,$numnodes);
	$string =~ s/JOBLAUNCH_CMD_HERE/$jobcmd/gs;

	$string =~ s/BENCH_HOME_HERE/$BENCH_HOME/gs;
	$string =~ s/CBENCHOME_HERE/$BENCH_HOME/gs;
	my $temp = $benchtest;
	$string =~ s/BENCH_TEST_HERE/$temp/gs;
	$string =~ s/CBENCHTEST_HERE/$temp/gs;
	(defined $BINIDENT) and $temp .= "\/bin.$BINIDENT";
	(!defined $BINIDENT) and $temp .= "\/bin";
	$string =~ s/CBENCHTEST_BIN_HERE/$temp/gs;
	$temp = $benchtest . "\/$testset";
	$string =~ s/TESTSET_PATH_HERE/$temp/gs;
	$string =~ s/TESTSET_NAME_HERE/$testset/gs;
	$string =~ s/RUN_TYPE_HERE/$runtype/gs;
	$string =~ s/JOBLAUNCHMETHOD_HERE/$joblaunch_method/gs;
	$string =~ s/WALLTIME_HERE/$walltime/gs;
	$string =~ s/NUM_PROC_HERE/$numprocs/gs;
	$string =~ s/NUM_PROCS_HERE/$numprocs/gs;
	$string =~ s/NUM_NODES_HERE/$numnodes/gs;
	$string =~ s/NUM_PPN_HERE/$ppn/gs;
	$temp = calc_num_threads($numprocs,$ppn);
	$string =~ s/NUM_THREADS_PER_PROCESS_HERE/$temp/gs;
	$string =~ s/JOBNAME_HERE/$jobname/gs;
	$string =~ s/JOBSCRIPT_HERE/$jobname\.$batch_extension/gs;
	$string =~ s/BENCHMARK_NAME_HERE/$benchmark/gs;
	$string =~ s/IDENT_HERE/$ident/gs;
	$string =~ s/TORQUE_NODESPEC_HERE/$numnodes\:ppn\=$procs_per_node/gs;
	$temp = $numnodes * $procs_per_node;
	$string =~ s/BSUB_NODESPEC_HERE/-n $temp -R span[ptile=$procs_per_node]/gs;
	$string =~ s/SLURM_NODESPEC_HERE/-N $numnodes/gs;
	$temp =join(',',@memory_util_factors);
	$string =~ s/MEM_UTIL_FACTORS_HERE/$temp/gs;


	return $string;
}

# Calculate the number of nodes needed for a job based on the number of
# procs needed and the number of processors per node to use
sub calc_num_nodes {
	my $procs = shift;
	my $ppn = shift;
	
	($ppn <= 0) and (warning_print("calc_num_nodes() ppn param is bad!") and return 1);

	my $num_nodes = int $procs/$ppn;
	(($num_nodes * $ppn) < $procs) and $num_nodes++;

	(defined $extra_job_nodes and $extra_job_nodes > 0) and $num_nodes += $extra_job_nodes;
	
	return $num_nodes;
}

# Calculate the number of threads we think we want to use per process (MPI
# or non-mpi process). We attempt to control this ultimately by setting
# the OMP_NUM_TRHEADS environment variable, but not in this subroutine.
# We by default assume we want to utilize all cores on a node
# which we can get from procs_per_node in cluster.def
sub calc_num_threads {
	my $numprocs = shift;
	my $ppn = shift;

	my $temp = int ($procs_per_node / (($numprocs < $ppn) ? $numprocs : $ppn));
	(defined $OMPNUMTHREADS) and $temp = $OMPNUMTHREADS;

	return $temp;
}


# Replace the default @run_sizes array (from the top of
# cbench.pl) with a custom one probably from values
# passed in on the command line
sub use_custom_runsizes {
	my $runsizes = shift;
    
    # we expect a comma separated list
    @run_sizes = split(',',$runsizes);
}


# print out a nicely colored string about a job failure found during
# output parsing. this is used in the output_parse modules
sub print_job_err {
	my $fileid = shift;
	my $err = shift;
	my $status = shift;
	my $extra = shift;

	# if this is a Cbench NOTICE message, check the $SHOWNOTICES global
	($err =~ /NOTICE/ and !$SHOWNOTICES) and return;

	$status =~ s/\n$//;

	# check cached jobdata from Slurm, job might be RUNNING and thus in an
	# ERROR state with respect to what an output_parse module is looking for.
	#
	# updated with more generic support to recognize RUNNING jobs
	if (exists $main::batch_jobdata{$JOBID} and $main::batch_jobdata{$JOBID} eq 'running') {
		print BOLD RED "**DIAG**";
		print BOLD WHITE "(";
		print GREEN "$fileid";
		print BOLD WHITE ") is still ";
		print BOLD GREEN "RUNNING";
		print RESET "\n";
	}
	else {
		print BOLD RED "**DIAG**";
		print BOLD WHITE "(";
		print GREEN "$fileid";
		print BOLD WHITE ") had a ";
		print BOLD RED "$err ";
		print BOLD WHITE "with status ";
		print BOLD RED "$status";
		(defined $extra) and print " ($extra)";
		print RESET "\n";
	}
}


# detect whether colorized text is supported in the context we
# are running and set the ANSI_COLORS_DISABLED environment variable
# appropriately for Term::ANSIColor
sub detect_color_support {
	# check to see if stdout is a pipe, if so no color please
	if (-p STDOUT) {
		$ENV{'ANSI_COLORS_DISABLED'} = 1;
		return;
	}

	$ttytest = `/usr/bin/tty`;
	chomp $ttytest;
	#print "DEBUG: $ttytest\n";

	if ($ttytest =~ /not a tty/) {
		$ENV{'ANSI_COLORS_DISABLED'} = 1;
		return;
	}

	# if we aren't going to disable color, turn on autoreset
	$Term::ANSIColor::AUTORESET = 1;
}


# Figure out what testset name a script is running on behalf of based
# on the name of the script. All testset scripts have the convention of
# TESTSET_blah.pl
sub find_testset_identity {
	my $fullname = shift;

	# strip of path stuff
	$fullname =~ s/^.*\/*\S*\///;
	debug_print(2,"DEBUG: fullname = $fullname\n");
	if ($fullname =~ /^(\S+)\_(gen_jobs|output_parse|start_jobs)\.pl$/) {
		debug_print(1,"DEBUG: testset identity is $1\n");
		return $1;
	}
	else {
		warning_print("Cannot determine testset identity.");
		return "TESTSET";
	}
}


# install files in a list to a given directory
sub install_filelist {
	my $list = shift;
	my $destpath = shift;
	my $verbosecp = shift;

	my $cmd = "/bin/cp -p ";
	(defined $verbosecp and $verbosecp == 1) and $cmd .= "-v ";

	(! -d $destpath) and mkdir $destpath,0750;
	
	foreach $item (@$list) {
		system("$cmd $BENCH_HOME\/$item $destpath\/\.");
		$DEBUG and print "INSTALLING $BENCH_HOME\/$item to $destpath...\n";
	}
}

# rsync files in a list to a given directory
sub rsync_filelist {
	my $list = shift;
	my $srcpath = shift;
	my $destpath = shift;
	my $verbosecp = shift;

	my $cmd = "/usr/bin/rsync -auC ";
	if (defined $verbosecp and $verbosecp == 1) {
		$cmd .= "-v ";
	}
	else {
		$cmd .= "-q ";
	}

	(! -d $destpath) and mkdir $destpath,0750;
	
	foreach $item (@$list) {
		system("$cmd $srcpath\/$item $destpath\/\. 2>/dev/null");
		debug_print(1,"DEBUG:rsync_filelist() syncing $srcpath\/$item to $destpath...");
	}
}

# install a Cbench template utility script (from tools directory)
# into its final resting place
#
# params:
# 1) script source template name
# 2) script destination name
# 3) testset name
sub install_util_script {
	my $src = shift;
	my $dest = shift;
	my $testset = shift;

	# read in source template
	open (IN,"<$BENCH_HOME/$src") or die
		"Could not open $BENCH_HOME/$src ($!)";
	undef $/;
	my $buf = <IN>;
	close(IN);
	$/ = "\n";

	# replace template values
	$buf =~ s/TESTSET_NAME_HERE/$testset/gs;

	# write out destination file
    print "writing to $dest\n";
	open (OUT,">$dest") or die
		"Could not open $dest for write ($!)";
	print OUT $buf;
	close(OUT);
	
	# make executable
	system("/bin/chmod gu+x $dest");
}

# used to install things into testsets via symlinking to the top
# of the cbench testing tree
# params:
# 1) source file (relative to the top of the CBENCHTEST tree)
# 2) destination file name
sub testset_symlink_file {
	my $src = shift;
	my $dest = shift;
	my $force = shift;

	# if the symlink exists remove it first
	if (-l "$dest") {
		unlink "$dest";
	}
	elsif (-f "$dest" and !$force) {
		info_print("testset_symlink_install() $dest is not a symlink, we will not touch it");
		return;
	}
	elsif (-f "$dest" and $force) {
		info_print("testset_symlink_install() $dest is not a symlink and FORCE specified, removing it");
		unlink "$dest";
	}

	system("/bin/ln -s ../$src $dest");
}


# make sure a directory exists in the Cbench testing tree for the given
# test set
sub mk_test_dir {
	my $testset = shift;
	my $bench_test = shift;
	
	(! -d $bench_test) and mkdir $bench_test,0750;
	(! -d "$bench_test\/$testset") and mkdir "$bench_test\/$testset",0750;
}

# process the CBENCHADDON environment variable
sub get_cbench_addon {
	if ($ENV{CBENCHADDON}) {
		debug_print(2,"DEBUG: found CBENCHADDON: $ENV{CBENCHADDON}\n");
		return $ENV{CBENCHADDON};
	}
	else {
		debug_print(2,"DEBUG: no CBENCHADDON found\n");
		return;
	}
}


# return a correct BENCH_TEST/CBENCHTEST path
sub get_bench_test {

	if ($ENV{CBENCHSTANDALONEDIR}) {
		debug_print(2,"DEBUG: found CBENCHSTANDALONEDIR environment variable\n");
		return $ENV{CBENCHSTANDALONEDIR};
	} 
	elsif ($ENV{CBENCHTEST}) {
		debug_print(2,"DEBUG: found CBENCHTEST environment variable\n");
		return $ENV{CBENCHTEST};
	}
	elsif ($ENV{CBENCHOME}) {
		debug_print(2,"DEBUG: found CBENCHHOME environment variable\n");
		return "$ENV{CBENCHOME}";
	}
	else {
		debug_print(2,"DEBUG: Failed to find appropriate CBENCHOME environment variable\n");
		exit 1;
	}
}

# build a nice timestamp
sub get_timestamp {
    my ($sec, $min, $hour, $day, $mon, $year, $wday, $yday, $isdst) = localtime;

    $year = $year + 1900;
    $stamp = sprintf "%02d/%02d/%02d %02d:%02d:%02d",$mon+1,$day,$year,$hour,$min,$sec;
    return $stamp;
}

# return true if the scalar is a perfect square
sub perfect_square {
	my $nprocs = shift;
	
	my $root = int sqrt($nprocs);
	(($root * $root) == $nprocs) and return 1;
	return 0;
}

# return true if the scalar is a power of two
sub power_of_two {
	my $nprocs = shift;
	
	my $power = log2($nprocs);
	((2 ** $power) == $nprocs) and return 1;
	return 0;
}

# return the base 2 logarithm of a scalar as an Integer
sub log2 {
	my $n = shift;
	
	my $power = log($n)/log(2);
	return int $power;
}

# returns the max of two scalars
sub max {
	my $v1 = shift;
	my $v2 = shift;
	
	($v1 > $v2) and return $v1;
	return $v2;
}

# returns the min of two scalars
sub min {
	my $v1 = shift;
	my $v2 = shift;
	
	($v1 < $v2) and return $v1;
	return $v2;
}

# Compute the N value(s) for the HPL.dat files.
# N is computed based on the total memory available
# per processor and a memory utlization factor (or array of factors
# which will generate multiple N values for HPL.dat).
sub compute_N {
	my $numprocs = shift;
	my $ppn = shift;
	my @Nvals = ();

	(! defined $ppn) and $ppn = 1;

	my $numnodes = int($numprocs/$ppn);
	(($numnodes * $ppn) < $numprocs) and $numnodes++;
	my $total_memory = $memory_per_node * $numnodes * 1024 * 1024;
	
	for $factor (@memory_util_factors) {
		my $N = sqrt($total_memory / 8) * $factor;
		$N = int ($N * 1.02);
		push @Nvals, $N;
	}
	(defined $DEBUG) and print "DEBUG: compute_N() @Nvals\n";
	return @Nvals;
}

# Compute the P and Q values for the HPL.dat files.
# P and Q are computed based on the heuristic that HPL "likes" a P:Q ratio
# of 1:k with k in [1..3].
sub compute_PQ {
	my $numprocs = shift;

	my @PQ = (0, 0);
	my $numproc_sqrt = int sqrt($numprocs);

	# is the proc count a perfect square?
	if (($numproc_sqrt * $numproc_sqrt) == $numprocs) {
		@PQ = ($numproc_sqrt, $numproc_sqrt);
		debug_print(1,"DEBUG: compute_PQ() @PQ\n");
		return @PQ;
	}

	for ($Q = $numproc_sqrt+1; $Q <= $numproc_sqrt*3; $Q++) {
		$P = int($numprocs / $Q);
		if (($P * $Q) == $numprocs) {
			@PQ = ($P, $Q);
			debug_print(1,"DEBUG: compute_PQ() @PQ\n");
			return @PQ;
		}
	}

	debug_print(1,"compute_PQ() failed for numprocs=$numprocs\n");
	return @PQ;
}

# return the integer cube root of an integer
# the cube root must an even integer or return 0
sub int_cube_root {
	my $num = shift;

	# this is just laziness to get around Perl floating-point rounding
	# stuff
	my %cuberoots = (
		8 => 2,
		27 => 3,
		64 => 4,
		125 => 5,
		216 => 6,
		343 => 7,
		512 => 8,
		729 => 9,
		1000 => 10,
		1331 => 11,
		1728 => 12,
		2197 => 13,
		2744 => 14,
		3375 => 15,
		4096 => 16,
		4913 => 17,
		5832 => 18,
		6859 => 19,
		8000 => 20,
		9261 => 21,
		10648 => 22,
		12167 => 23,
		13824 => 24,
		15625 => 25,
	);

	(defined $cuberoots{$num}) and return $cuberoots{$num};
	return 0;
}

# return a triplet of integer factors for a given integer
# used for decomposing a number of processors to x,y,z
# integer components
sub three_int_factors {
	my $num = shift;

	my %fact = (
		2 => '2,1,1',
		4 => '2,2,1',
		8 => '2,2,2',
		16 => '4,2,2',
		32 => '4,4,2',
		64 => '4,4,4',
		128 => '8,4,4',
		256 => '8,8,4',
		512 => '8,8,8',
		784 => '16,7,7',
		1024 => '16,8,8',
		1296 => '16,9,9',
		1920 => '16,12,10',
		2048 => '16,16,8',
		3840 => '16,16,15',
		3920 => '20,14,14',
		4096 => '16,16,16',
		8192 => '32,16,16',
	);
	(defined $fact{$num}) and return $fact{$num};
	return '';
}

# Kill children that have been forked by Cbench testing
# that Cbench is keeping track of. Takes a single optional
# boolean argument that if true will tell us to use 
# SIGKILL instead of SIGINT.
sub kill_kids {
	my $signal = shift;
	for (keys %main::childpids) {
		defined $DEBUG and print "kill_kids() killing $_\n";
		if ($signal) {
			kill( KILL ,$_);
		}
		else {
			kill( INT ,$_);
		}
		delete $main::childpids{$_};
	}
}

# Conditional debug output printing routine.
#
# Arg1 : minimum debug level to print at
# Args : string of what to print
sub debug_print {
	my $level = shift;
	my $msg = shift;

	# a common pain is calling debug_print with newline in the string
	# and then we add one here, so strip the ending one off
	$msg =~ s/\n$//;
	if (defined $DEBUG and $DEBUG >= $level) {
    	print MAGENTA BOLD $msg,RESET,"\n";
	}
}

# print out cbench warnings
sub warning_print {
	my $msg = shift;
	$msg =~ s/\n$//;
    print YELLOW BOLD "WARNING: $msg",RESET,"\n";
}

# print out cbench info messages
sub info_print {
	my $msg = shift;
	$msg =~ s/\n$//;
    print BLUE BOLD "INFO: $msg",RESET,"\n";
}

# print out cbench error messages
sub error_print {
	my $msg = shift;
	$msg =~ s/\n$//;
    print RED BOLD "ERROR: $msg",RESET,"\n";
}



#
# The subroutines below were taken completely or in large measure
# from the Sandia National Laboratories Cluster Integration
# Toolkit (CIT), http://www.cs.sandia.gov/cit
#
#

#
# Find an external program on the local system.
#
# INPUTS: program name, list of absolute paths (directories) to look in
#	The path list may include the keyword "which", to look for
#	the program in the system search paths.
# OUTPUT: full path to program, or undef if not found.
#
sub find_bin {
	my $name = shift;
	for (@_) {
		my $path = $_;
		my $location;
		if ($path eq "which") {
			$location = `which $name 2>/dev/null`;
			$location or next;
			chomp $location;
		} elsif ($path !~ /^\//) {
			print STDERR "find_bin(): '$path' must be an absolute path.\n";
			next;
		} else {
			$path =~ /\/$/ or $path .= "/";  # must end with "/"
			$location = $path.$name;
		}
		if (-e $location and -x $location) {
			return $location;
		}
	}
	return;
}

#
# pass a sub ref and fork it off in a child process.
# keep track of the childrens pids in a hash whose
# key is the reference to the code passed in. This
# will stay unique. CAN use it later with waiter, or
# collect the pids yourself, the sub returns the child's
# pid back to the parent process.
#
sub background {
	my ($cref) = shift;
	my (@args) = @_;


	die 'Usage: background($cref, <$arg1, $arg2, ..>)' 
	    unless ref($cref) eq "CODE";

	my $pid;
	if ($pid = fork()) { # parent
		push(@{$main::_tasks{$cref}},$pid);
		$DEBUG and 
	    	    print "FORK -> PID $pid \n";
		return $pid;
	} else {
		return undef unless defined $pid; # problem forking 
		$#args > 0 ? &$cref(@args) : &$cref;
		exit;
	}
}

# used in conjunction with background() to wait for backgrounded
# processes to finish
sub waiter {

	my $cref = shift;
	my $time = shift;
	my $sig = shift;

	die 'Usage: waiter($cref, <$time>)' unless ref($cref) eq "CODE";

	$time = 120 unless defined $time; 

	my @done;
		
	for (@{$main::_tasks{$cref}}) { 
		eval {
			local $SIG{ALRM} = sub { die "PID\n" };
			alarm $time;
			push @done, waitpid($_,0); 
			$time = alarm 0;
		};
	}

	#
	# find out which ones didn't fini
	#
	my @not_done;
	$#{$main::_tasks{$cref}} != $#done and do {
	    my %seen;
	    @seen{@done} = ();
	    for (@{$main::_tasks{$cref}}) {
		    push @not_done, $_ unless exists $seen{$_}; 
	    }
	    $DEBUG and 
		print STDERR "DEBUG: wait failed on @not_done\n";
	    #
	    # if user passed a signal we will pass it to the children
	    # that are still around
	    #
	    $sig and return clean_up($sig, @not_done);
	};

	@not_done ? return @not_done : return 1;

}

sub clean_up {
	my $sig = shift;
	my @pids = @_;
	my @not_killed;

	print STDERR "Killing PIDS @pids\n";
	for (@pids) {
		(kill $sig, $_ eq 1) or push @not_killed, $_;
	}
	@not_killed and 
	    print STDERR "Couldn't kill pids @not_killed\n" and
	    return @not_killed;

	return 1;
}


#
# Set up Signal handler to clean up hanging children
# Taken from Tom Christiansen's perlipc man page. Thanks Tom! (JHL)
#
sub REAPER {
	my $waitedpid = wait;
	$SIG{CHLD} = \&REAPER;  # loathe sysV
	#debug_print(3,"DEBUG:REAPER() reaped $waitedpid" . ($? ? " with exit $?" : '') . "\n");
}

sub CATCH {
	my $signame = shift;
        #if ($signame =~ /INT|QUIT/) {
		for (keys %main::childpids) {
			print "\nCATCH(pid $$) Caught SIG$signame, Killing child $_\n";
			kill($signame, $_);
		}
		$main::INTsignalled = 1;
		# make sure our whole process group gets the signal
		kill(-$signame,$$);
#	}
#	else {
#		print "CATCH(pid $$) Caught SIG$signame...\n";
#	}
}


#
# Substitute the absolute path of the data file into the in.* file
# for certain LAMMPS jobs
#
sub lammps_file_substitute {
	#my $lammps_bench = "$ENV{CBENCHTEST}/lammps/bench";
	my $lammps_bench = shift;

	#LAMMPS benchmark/example codes requiring data files are:
	# rhodo, chute, chain, meam, rigid, peptide, and micelle

	 my @codes = qw/rhodo rhodo.scaled chute chute.scaled chain chain.scaled meam meam.shear rigid peptide micelle/;

	for my $code_name (@codes) {
		my $input_file = "$lammps_bench/in.$code_name";

		debug_print(3,"DEBUG: lammps_file_substitute for $input_file\n");

		#check for and open data file; skip if not present
		(-e $input_file) and open(IN, "<$input_file") or next;
		
		#change the read_data line to include the full path of the data file
		$/ = undef;
		my $string = <IN>;
		close(IN);
		$/ = "\n";
		$string =~ s/read_data.*data/read_data\t$lammps_bench\/data/gs;

		#overwrite in.$codename with new file
		open(OUT, ">$input_file");
		print OUT $string;
		close(OUT);
	}
}

#copy the input files into a job file
sub lammps_copy_files {
	my $input_file_dest = shift;
	my $code_name = shift;
	my $lammps_bench = "$ENV{CBENCHTEST}/lammps/bench";

	my $input_file = "$lammps_bench/in.$code_name";

     #check for input file; skip if not present
     (-e $input_file) or print "Could not locate $input_file: $?\n" and next;
     debug_print(3, "DEBUG: lammps_copy_file for $input_file\n");

	#check for scaled version of input deck
	if ( -e "$lammps_bench/in.$code_name.scaled" ) {
		$input_file = "$lammps_bench/in.$code_name.scaled";

		system("cp $input_file $input_file_dest") == 0 or die("Could not copy $input_file: $?\n");
	}
    
	#copy the in.whatever file to the new jobdir
	system("cp $input_file $input_file_dest") == 0 or die("Could not copy $input_file: $?\n");
}

#return the desired scaling parameters based on the size of the job being generated
sub lammps_get_scaling_params {
    my $numprocs = shift;
    my $scaled_factor = shift;

    if (not defined $scaled_factor) {
        $scaled_factor = "1 1 1";
    }

    #there's probably a better way to split directly into the desired variables, but this works 
    @factors = split /\s/, $scaled_factor;

    my $x = $factors[0];
    my $y = $factors[1];
    my $z = $factors[2];

    #create scaling parameters for use with the LAMMPS scaling jobs
    #   These parameters are based on a static list of scaling parameters from Sandia benchmarking
    #   efforts.  Future work will allow the user to provide a list of desired scaling parameters,
    #   but right now it only uses the static rules below.

    if ( $numprocs <= 1 ) {
        my $scaling_params = "-var x " . 1*$x . " -var y " . 1*$y . " -var z " . 1*$z;
        return $scaling_params;
    }
    elsif ( $numprocs <= 2 ) { 
        my $scaling_params = "-var x " . 2*$x . " -var y " . 1*$y . " -var z " . 1*$z;
        return $scaling_params;
    }
    elsif ( $numprocs <= 4 ) { 
        my $scaling_params = "-var x " . 2*$x . " -var y " . 2*$y . " -var z " . 1*$z;
        return $scaling_params;
    }
    elsif ( $numprocs <= 8 ) { 
        my $scaling_params = "-var x " . 2*$x . " -var y " . 2*$y . " -var z " . 2*$z;
        return $scaling_params;
    }
    elsif ( $numprocs <= 16 ) { 
        my $scaling_params = "-var x " . 4*$x . " -var y " . 2*$y . " -var z " . 2*$z;
        return $scaling_params;
    }
    elsif ( $numprocs <= 32 ) { 
        my $scaling_params = "-var x " . 4*$x . " -var y " . 4*$y . " -var z " . 2*$z;
        return $scaling_params;
    }
    elsif ( $numprocs <= 64 ) { 
        my $scaling_params = "-var x " . 4*$x . " -var y " . 4*$y . " -var z " . 4*$z;
        return $scaling_params;
    }
    elsif ( $numprocs <= 128 ) { 
        my $scaling_params = "-var x " . 8*$x . " -var y " . 4*$y . " -var z " . 4*$z;
        return $scaling_params;
    }
    elsif ( $numprocs <= 256 ) { 
        my $scaling_params = "-var x " . 8*$x . " -var y " . 8*$y . " -var z " . 4*$z;
        return $scaling_params;
    }
    elsif ( $numprocs <= 512 ) { 
        my $scaling_params = "-var x " . 8*$x . " -var y " . 8*$y . " -var z " . 8*$z;
        return $scaling_params;
    }
    else {
        my $scaling_params = "-var x " . 16*$x . " -var y " . 8*$y . " -var z " . 8*$z;
        return $scaling_params;
    }
}

1;
