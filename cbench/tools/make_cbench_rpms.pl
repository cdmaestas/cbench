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

# This utiltity script is to make various flavors of RPMs to package Cbench
# in various ways.  RPM packaging certainly isn't perfect, especially for shared
# NFS installations, but I didn't really find anything at all better.  So,
# this is the shortest distance for versioned Cbench packaging for now.

# need to know where everything cbench lives!
BEGIN {
	die "Please define CBENCHOME!\n" if !defined($ENV{CBENCHOME});
}
use lib $ENV{CBENCHOME};
require "cbench.pl";
$CBENCHOME = $BENCH_HOME = $ENV{CBENCHOME};

use Getopt::Long;
use File::Find;

GetOptions(
	'testingtree' => \$testingtree,
	'srcdir=s' => \$srcdir,
	'destdir=s' => \$destdir,
	'release=s' => \$release,
	'namesuffix=s' => \$namesuffix,
	'owner=s' => \$owner,
	'changelog=s' => \$changelog,
	'clusterdef=s' => \$clusterdef,
	'nodehwtestvals=s' => \$nodehwtestvals,
	'help' => \$help,
	'debug=i' => \$DEBUG,
);

if (defined $help) {
	usage();
	exit;
}

(! defined $testingtree) and die "Need to specify --testingtree or --sourcetree";
(!defined $srcdir or !defined $destdir or !defined $release) and
	die "--srcdir, --destdir, and --release parameters are required";
(!defined $owner) and $owner = 'root';

# read in the RPM spec files for building the cbench-test tree rpm
$file = "$BENCH_HOME\/templates/cbench-test.spec.in";
open (IN,"<$file") or die
	"Could not open $file ($!)";
undef $/;
$cbench_test_spec = <IN>;
close(IN);
$/ = "\n";

if (defined $changelog) {
	# read in the changelog text
	$file = "$changelog";
	open (IN,"<$file") or die
		"Could not open $file ($!)";
	undef $/;
	$changelog_txt = <IN>;
	close(IN);
	$/ = "\n";
}
else {
	$changelog_txt = "\n";
}


my $rpm_file_list = '';
my $install_file_list = '';
if (defined $testingtree) {
	my $rpmname = "cbench-test";
	(defined $namesuffix) and $rpmname .= "-$namesuffix";

	$install_file_list .= "mkdir -p \$\{RPM_BUILD_ROOT\}/$destdir\n";

	# need to build a list of files for the RPM with some files tagged with
	# appropriate rpm macros for the %files section
	find(\&find_cbenchtest_files, $srcdir);
	#print "$install_file_list\n";

	if (defined $clusterdef) {
		$install_file_list .= "/bin/cp $clusterdef \$\{RPM_BUILD_ROOT\}/$destdir/cluster.def\n";
	}
	if (defined $nodehwtestvals) {
		$rpm_file_list .= "\%config $destdir/nodehwtest/cluster_target_values\n";
		$install_file_list .= "/bin/cp $nodehwtestvals \$\{RPM_BUILD_ROOT\}/$destdir/nodehwtest/cluster_target_values\n";
	}

	# if mpich is involved gotta fix the stinkin paths
	if ($rpm_file_list =~ /mpich/) {
		$install_file_list .= "$BENCH_HOME/tools/reconfig_mpich_paths.sh $srcdir $destdir \$\{RPM_BUILD_ROOT\}/$destdir/mpich\n";
	}

	# now edit the spec template
	$cbench_test_spec =~ s/RPM_NAME_HERE/$rpmname/gs;
	$cbench_test_spec =~ s/RPM_VERSION_HERE/$cbench_version/gs;
	$cbench_test_spec =~ s/RPM_RELEASE_HERE/$release/gs;
	$cbench_test_spec =~ s/INSTALL_STUFF_HERE/$install_file_list/gs;
	$cbench_test_spec =~ s/FILES_STUFF_HERE/$rpm_file_list/gs;
	$cbench_test_spec =~ s/OWNER_HERE/$owner/gs;
	$cbench_test_spec =~ s/CHANGELOG_STUFF_HERE/$changelog_txt/gs;
	$cbench_test_spec =~ s/CBENCHTEST_DESTDIR_HERE/$destdir/gs;

	# build a temporary directory tree for RPM building containment
	my $tmpdir = "/tmp/$ENV{'USER'}/cbench_rpm_stuff.$$";
	print "Creating temporary RPM building directory tree here: $tmpdir\n";
	system("mkdir -p $tmpdir/\{BUILD,RPMS,SOURCES,SPECS,SRPMS\}");
	system("mkdir -p $tmpdir/BUILD/$destdir");

	# create the Cbench environ init files for the isolated Cbench Testing tree
	# AT THE DESTINATION location
	my $cbinitfile="$tmpdir/BUILD/$destdir/cbench-init";
	open (CBINIT, ">$cbinitfile.sh") or die "Can't create CBENCH INIT FILE $cbinitfile.sh $!";
	print CBINIT "#!/bin/sh\n".
	"CBENCHOME=$destdir
	CBENCHTEST=$destdir
	export CBENCHOME
	export CBENCHTEST\n";
	close (CBINIT);
	open (CBINIT, ">$cbinitfile.csh") or die "Can't create CBENCH INIT FILE $cbinitfile.sh $!";
	print CBINIT "#!/bin/csh\n".
	"setenv CBENCHOME $destdir
	setenv CBENCHTEST $destdir
	\n";
	close (CBINIT);

	# write the generated spec file
	my $specfile = "$tmpdir/SPECS/cbench-test-$$.spec";
	open (OUT,">$specfile") or die
		"Could not open $specfile ($!)";
	print OUT $cbench_test_spec;
	close(OUT);

	my $cmd = "rpmbuild --nodeps --define=\'_topdir $tmpdir\' --buildroot=$tmpdir/BUILD -bb ";
	(defined $DEBUG) and $cmd .= "-v ";
	$cmd .= "$specfile";
	(defined $DEBUG) and print "DEBUG: rpmbuild cmd= $cmd\n";
	system("$cmd");

	print "Wrote specfile to $specfile\n";

	# cleanup the biggest part of the build process
	system("/bin/rm -rf $tmpdir/BUILD/*") unless defined $DEBUG;
}



sub find_cbenchtest_files {
	#print "DEBUG: $File::Find::name \n";
    if ($File::Find::name =~ /^$srcdir[\/]*(\S+)$/) {
		my $relative_part = $1;
		my @patharray = split '/', $relative_part;
        my $file = $patharray[$#patharray];
		my $depth = $#patharray;

		my $relative_path = '';
		my $tmp = $#patharray - 1;
		if ($tmp >= 0) {
			for $i (0..$tmp) {
				$relative_path .= "$patharray[$i]/";
			}
		}

		# don't need to process directories
		if (-d "$File::Find::name") {
			$depth++;
			(defined $DEBUG and $DEBUG > 1) and
				print "DEBUG: new directory $File::Find::name == depth $depth\n";
			if (($depth <= 1) or ($patharray[0] =~ /bin|perllib|mpich/)) {
				$rpm_file_list .= "\%dir $destdir/$relative_part\n";
				$install_file_list .= "mkdir -p \$\{RPM_BUILD_ROOT\}/$destdir/$relative_part\n";
			}
			return;
		}
		
		# we want to avoid processing a bunch of test identifiers and run data
		if ($depth > 1) {
			($patharray[0] !~ /bin|perllib|mpich/) and return;
		}

	 	(defined $DEBUG and $DEBUG > 1) and print 
			"DEBUG: $File::Find::name == $1 == @patharray == $file == $depth == $File::Find::dir\n";

		if ($file =~ /\.in$|\.def$|^cbench.pl$/) {
			# tag config files as such for rpm
			$rpm_file_list .= "\%config $destdir/$relative_part\n";
			$install_file_list .= "mkdir -p \$\{RPM_BUILD_ROOT\}/$destdir/$relative_path\n";
			$install_file_list .= "/bin/cp $srcdir/$relative_part \$\{RPM_BUILD_ROOT\}/$destdir/$relative_part\n";
		}
		elsif ($file =~ /^cbench-init\./) {
			# these files have to be handled differently as we need to build them
			# for the $destdir target location
			$rpm_file_list .= "\%config $destdir/$relative_part\n";
		}
		else {
			$rpm_file_list .= "$destdir\/$relative_part\n";
			$install_file_list .= "mkdir -p \$\{RPM_BUILD_ROOT\}/$destdir/$relative_path\n";
			$install_file_list .= "/bin/cp --no-dereference -p $srcdir/$relative_part \$\{RPM_BUILD_ROOT\}/$destdir/$relative_part\n";
		}
	}
}


sub usage {
    print	"USAGE: $0 \n";
	print	"Cbench script to build Cbench custom rpms\n".
			"    --testingtree       Build a Cbench Testing Tree rpm\n".
			"    --srcdir            Path to the source tree that will be made into\n".
			"                        an rpm\n".
			"    --destdir           The destination path for the rpm to install the\n".
			"                        source tree\n".
			"    --release           Release string for the rpm which is tacked on to\n".
			"                        the end of the Cbench version that is found\n".
			"    --namesuffix        Suffix string to use in naming the rpm. For example\n".
			"                        building a testing tree rpm with the suffix openmpi123\n".
	        "                        results in an rpm named: cbench-test-openmpi123\n".
			"    --owner             UID/name of the account who should own the files when\n".
			"                        the rpm is installed\n".
			"    --changelog         A filename pointing to a changelog to include in the rpm\n".
			"    --clusterdef        A filename pointing to a specfic cluster.def file to use in a\n".
			"                        Cbench Testing Tree rpm\n".
			"    --nodehwtestvals    A filename pointing to a target hardware values file\n".
			"                        to be included in the nodehwtest test set (i.e. the Cbench\n".
			"                        node-level testing. The file will be named cluster_target_values\n".
            "    --debug <level>     Debug level\n".
			"\n".
			"Example:\n".
			"  $0  --testingtree --src \$CBENCHTEST  --destdir /scratch3/cbench-test-tbird --namesuffix tbird --release 1 --owner cbench --changelog /path/to/changelog.thunderbird --clusterdef /path/to/cluster.def.thunderbird --nodehwtestvals /path/to/cluster_target_values.thunderbird\n";
}
