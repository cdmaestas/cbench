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

# Utility script to generate a skeleton Cbench jobscript using the templated
# structure.

# need to know where everything cbench lives!
BEGIN {
	die "Please define CBENCHOME!\n" if !defined($ENV{CBENCHOME});
}
use lib $ENV{CBENCHOME};
require "cbench.pl";
$CBENCHOME = $BENCH_HOME = $ENV{CBENCHOME};

use Getopt::Long;
use Data::Dumper;

my $skelname = 'setvars';
my $ppn = 1;
my $numprocs = 1;

GetOptions(
	'batch_method=s' => \$batch_method,
	'skelname=s' => \$skelname,
	'ppn=i' => \$ppn,
	'numprocs|procs=i' => \$numprocs,

);

if (defined $help) {
	usage();
	exit;
}

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

#print "$batch_method, $skelname\n";

my $testset = 'skel';
my $numnodes = calc_num_nodes($numprocs,$ppn);

(!defined $ident) and $ident = $cluster_name . "1";

# find and read in the job templates for the testset
my %templates = ();
build_job_templates("SKELETONJOB:$skelname",\%templates);
delete $templates{combobatch};
# by default the list of jobs is the list of templates found
my @job_list = keys %templates;

# if the user passed in a set of runsizes on the command line, convert
# to an array and replace the default @run_sizes array from cbench.pl
(defined $runsizes) and use_custom_runsizes($runsizes);

# iterate over the job templates we need to process
foreach $job (@job_list) {
	# most job templates correspond directly with the name of the job
	my $job_template = $job;


	# build the full job name
	$jobname = "$job-".$ppn."ppn-$numprocs";

	# iterate over batch and interactive job generation
	foreach $runtype (('batch','interactive')) {
		my $captype = uc $runtype;

		# prime the output buffers with the appopriate template
		$outbuf = $templates{$job_template}{$runtype};

		# here we do all the standard substitutions
		$outbuf = std_substitute($outbuf,$numprocs,$ppn,$numnodes,
					$runtype,$default_walltime,$testset,$jobname,$ident,$job);

		# other substitutions
		$outbuf =~ s/TESTDIR_HERE/$testdir/gs;
		$outbuf =~ s/XHPL_BIN_HERE/$xhplbin/gs;
		$outbuf =~ s/HPCC_BIN_HERE/$hpccbin/gs;

		# build the filename
		($runtype eq 'batch') and $outfile = "$jobname\.$batch_extension";
		($runtype eq 'interactive') and $outfile = "$jobname\.sh";

		debug_print(2,"DEBUG: Writing $captype script for $jobname\n");

		# write out the generated job file
		open (OUT,">$outfile") or die
			"Could not write $outfile ($!)";
		print OUT $outbuf;
		close(OUT);

		($runtype eq 'interactive') and
			`/bin/chmod gu+x $outfile`;
	}
}
