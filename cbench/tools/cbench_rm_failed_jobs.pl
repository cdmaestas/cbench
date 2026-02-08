#!/usr/bin/perl
###############################################################################
#    Copyright (2009) Sandia Corporation.  Under the terms of Contract
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

use Getopt::Long;

GetOptions(
	'force' => \$force,
	'debug' => \$DEBUG,
);

while (<STDIN>) {
	my $tmp = $_;
	$tmp =~ s/\033\[0m//g;
	(defined $DEBUG) and print "DEBUG: $tmp";
	if ($tmp =~ /\*\*DIAG\*\*\((\S+)\) had a (\S+) with status (.*)$/) {
		$file = $1;
		$status = $2;
		$detail = $3;

		# only deal with ERROR flagged files
		($status !~ /ERROR/) and next;
		(!$force) and print "Would remove: $file\n"; 
		if ($force) {
			print "Removing: $file\n"; 
			system "/bin/rm -f $file";
		}
	}
}
