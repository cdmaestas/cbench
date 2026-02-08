#!/usr/bin/perl -w

#
# This program is part of the VA Cerberus Test Control System.
# Unless otherwise noted, Copyright (c) 1999 VA Linux Systems, 
# All Rights Reserved.
# You may distribute this program under the terms of the GNU General
# Public License, Version 2, or, at your option, any later version.
#

# convert XdXhXmXs to seconds
sub timetosec {
	my $time = shift;
	my $seconds = 0;
	if ($time =~ /(\d+)d(.*)/) {
		$time = $2;
		$seconds += $1*60*60*24;
	}
	if ($time =~ /(\d+)h(.*)/) {
		$time = $2;
		$seconds += $1*60*60;
	}
	if ($time =~ /(\d+)m(.*)/) {
		$time = $2;
		$seconds = $seconds + $1*60;
	}
	if ($time =~ /(\d+)s(.*)/) {
		$time = $2;
		$seconds = $seconds + $1; 
	}
	if ($time =~ /(\d+)/) {
		$seconds = $time;
	}
	return $seconds;
}

sub sectotime {
	my $seconds = shift;
	my $time = "";
	if ($seconds >= 60*60*24) {
		$time .= int ($seconds / (60*60*24)) . "d";
		$seconds -= (int ($seconds / (60*60*24))*60*60*24);
	}
	if ($seconds >= 60*60) {
		$time .= int ($seconds / (60*60)) . "h";
		$seconds -= (int ($seconds / (60*60))*60*60);
	}
	if ($seconds >= 60) {
		$time .= int ($seconds / (60)) . "m";
		$seconds -= (int ($seconds / (60))*60);
	}
	if ($seconds >= 0) {
		$time .= $seconds . "s";
	}
	return $time;
}

1;
