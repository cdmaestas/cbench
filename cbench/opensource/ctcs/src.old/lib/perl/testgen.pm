#!/usr/bin/perl

#
# This program is part of the VA Cerberus Test Control System.
# Unless otherwise noted, Copyright (c) 1999 VA Linux Systems,
# All Rights Reserved.
# You may distribute this program under the terms of the GNU General
# Public License, Version 2, or, at your option, any later version.
#

#
# testgen.pm: High level interface for generating control file lines.
# All functions should return a list of strings containing control
# file lines.  This can be then printed or done whatever with by
# the calling program.
#

# Generate a badblocks test.
# parameters:  (parallel (int) ,sleep (bool), destruct (bool), @drives)
# If parallel = 0, run one badblock in the foreground.
sub badblocks {
	my $parallel = shift;
	my $sleep = shift;
	my $destruct = shift;
	my @drives = @_;
	my @tcflines;
	my $drive;
	my $i;
	my $testcommand;
	my $tcfcommand;

	if ($parallel) {
		$tcfcommand = "bg 0";
	} else {
		$tcfcommand = "fg 1";
	}

	if ($destruct) {
		$testcommand = "destructiveblocktst";
	} else {
		$testcommand = "blockrdtst";
	}

	if ($sleep) {
		$testcommand = "s" . $testcommand;
	}

	foreach $drive (@drives) {
		# slashes in key names are bad (think RAID)
		my $key = $drive;
		$key =~ s/\///g;
		for($i=0;$i < $parallel; $i++) {
			push @tcflines,"$tcfcommand BB".$key."N$i $testcommand /dev/$drive";
		}
	}
	return @tcflines;
}


# Create data read/write test. 
# If parallel = 0, run however many data tests needed according to
#  partfrac and maxfilesize.  If maxfilesize = 0, run however many data
#  tests needed according to partfrac and parallel.  If both = 0, run
#  one data test according to partfrac.
# 0 < partfrac < 1 , fraction of free space to test.  Too high
# and you might run out of disk space. 
sub datarw {
	my @tcflines;
	my $parallel = shift;
	my $sleep = shift;
	my $partfrac = shift;
	my $maxfilesize = (shift) * 1024;
	my @partitions = @_;
	my $partition;
	my $i;
	my $testcommand = "data";

	if ($sleep) {
		$testcommand = "s".$testcommand;
	}

	if (!$partfrac) {
		return;
	}

	if (!$maxfilesize and !$parallel) {
		$parallel = 1;
	}

	foreach $partition (@partitions) {
		my $key = $partition;
		my $msize = 0;
		my $size = 0;
		my $p=0;
		$key =~ s(/)()g;
		# The runin directory shouldn't be hardcoded like this.
		my @partinfo = split /\s/, `cd runin && ./data-info /dev/$partition`;
		$partinfo[3] = $partinfo[3] * $partfrac;

		if (!$maxfilesize) {
			$msize = $partinfo[3] / $parallel;
		} else {
			$msize = $maxfilesize;
		}
		if ($parallel < $partinfo[3]/$msize) {
			$p = int($partinfo[3] / $msize) + 1;
		} else {
			$p = $parallel;
		}
		
		$size = int($partinfo[3] / $p);
		if ($size > $msize) {
			$size = $msize;
		}
#debug code
#		print "$partition outof $partinfo[3] parallel  $p max $msize size $size\n";
		for($i=0;$i<$p;$i++) {
			if ($size <= $partinfo[3]) {
				$partinfo[3] -= $size;
			} else {
				$size = $partinfo[3];
				$partinfo[3] = 0;
			}
			push @tcflines, "bg 0 DT".$key."N$i $testcommand /dev/$partition $size";
		}
	}
	return @tcflines;
}

1;
