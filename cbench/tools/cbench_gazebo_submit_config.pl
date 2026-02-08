#!/usr/bin/perl

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
# vim: syntax=perl tabstop=4

# need to know where everything cbench lives!
BEGIN {
    die "Please define CBENCHOME!\n" if !defined($ENV{CBENCHOME});
}
use lib $ENV{CBENCHOME};
require "cbench.pl";
$CBENCHOME = $BENCH_HOME = $ENV{CBENCHOME};

# add Cbench perl library to the Perl search path
use lib "$ENV{CBENCHOME}\/perllib";

use Getopt::Long;

# get the default list of Cbench testsets to hook
# don't hook shakedown unless asked
(my $testsets = $core_testsets) =~ s/shakedown //;

my $gazebo_config = 'cbench_config';
my $ident = 'gazebo';

GetOptions( 'ident=s' => \$ident,
			'debug:i' => \$DEBUG,
			'help' => \$help,
			'testsets=s' => \$testsets,
			'gazebohome|gzhome|gazhome=s' => \$gazebo_home,
			'gazeboconfig|gzconfig|gazconfig=s' => \$gazebo_config, 
			'gazebodebug|gzdebug|gazdebug' => \$gazebo_debug, 
			'minprocs=i' => \$minprocs,
			'maxprocs=i' => \$maxprocs,
			'procs=i' => \$procs,
);

if (defined $help) {
	usage();
	exit;
}
if (!defined $gazebo_home) {
	warning_print("--gazebohome paramter is required");
	usage();
	exit;
}


# clean out existing submit_config if there is one
system("/bin/rm -f $gazebo_home/submit_configs/$gazebo_config 1>/dev/null 2>&1");

# go to the top of the Cbench testing tree
my $cbenchtest = get_bench_test();
chdir $cbenchtest;


my @testset_list = split(' ',$testsets);
debug_print(1,"DEBUG: testsets= $testsets");
foreach my $set (@testset_list) {
	# always ignore nodehwtest test set
	($set =~ /nodehwtest/i ) and next;
	if (!chdir($set)) {
		next;
	}

	print "Hooking Cbench ".uc($set)." testset into Gazebo\n";
	# --gazebo --testset latency --maxprocs 16 --gazhome /home/jbogden/tlcc/gazebo+cbench/Gazebo --gazeboconfig config_cbench
	my $cmd = "./$set\_gen_jobs.pl --ident $ident --gazebo --gazhome $gazebo_home --gazeboconfig $gazebo_config";
	(defined $minprocs) and $cmd .= " --minprocs $minprocs";
	(defined $maxprocs) and $cmd .= " --maxprocs $maxprocs";
	(defined $procs) and $cmd .= " --procs $procs";
	(defined $gazebo_debug) and $cmd .= " --gzdebug";
	(defined $DEBUG and $DEBUG > 1) and $cmd .= " --debug $DEBUG";

	debug_print(1,"DEBUG: cmd= $cmd");
	system("$cmd");

	chdir $cbenchtest;
}

print "Wrote Gazebo submit config here: $gazebo_home/submit_configs/$gazebo_config\n";


sub usage {
    print "USAGE: $0 \n";
    print "Cbench script to hook a Cbench testing tree into the Gazebo test framework\n".
          "   --ident           Identifying string for the testing. Defaults to \'gazebo\'\n".
		  "   --testsets <list> Comma separated list of Cbench testset names to hook\n".
		  "                     into Gazebo. For example:\n".
		  "                       --testsets 'bandwidth latency'\n".
		  "                     The default list is:\n".
		  "                     \"$testsets\"\n\n".
		  "   --gazebohome <path>    Where the Gazebo tree is located\n".
		  "   --gazeboconfig <name>  Name of the Gazebo submit_config that will be APPENDED to\n".
          "   --maxprocs       The maximum number of processors to generate\n".
          "                    jobs for\n".
          "   --minprocs       The minimum number of processors to generate\n".
          "                    jobs for\n".
          "   --procs          Only generate jobs for a single processor count\n".
          "   --debug <level>  Turn on debugging at the specified level\n";
}
