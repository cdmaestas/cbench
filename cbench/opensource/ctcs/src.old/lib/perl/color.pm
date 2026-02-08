#!/usr/bin/perl -w

#
# This program is part of the VA Cerberus Test Control System.
# Unless otherwise noted, Copyright (c) 1999 VA Linux Systems, 
# All Rights Reserved.
# You may distribute this program under the terms of the GNU General
# Public License, Version 2, or, at your option, any later version.
#

use strict;

my %colorhash = (
		 fblack => "30m",
		 fred => "31m",
		 fgreen => "32m",
		 fbrown => "33m",
		 fblue => "34m",
		 fmagneta => "35m",
		 fcyan => "36m",
		 fwhite => "37m",
		 bblack => "40m",
		 bred => "41m",
		 bgreen => "42m",
		 bbrown => "43m",
		 bblue => "44m",
		 bmagneta => "45m",
		 bcyan => "46m",
		 bwhite => "47m",
		 bdefault => "49m",
		 
		 reset => "0m",
		 bold => "1m",
		 boldoff => "22m",
		 blink => "5m",
		 blinkoff => "25m",
		 reverse => "7m",
		 reverseoff => "27m"
);


sub colorstr {
	my $i;
	my $cstring;
	foreach $i (@_) {
		$cstring="$cstring\e[". $colorhash{"$i"};
	}
	return $cstring
}

sub color {
	my $i;

	foreach $i (@_) {
		print "\e[" . $colorhash{"$i"};
	}
}

#print("\e[31m\n");
