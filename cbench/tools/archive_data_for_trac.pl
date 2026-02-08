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

use Getopt::Long;

GetOptions(
	'filebasename=s' => \$filebasename,
	'urlbase=s' => \$urlbase,
	'urldir=s' => \$urldir,
	'destdir=s' => \$destdir,
	'destbasename=s' => \$destbasename,
	'indent=i' => \$indent,
	'description=s' => \$description,
);

(!defined $destdir) and $destdir = "$ENV{PWD}/tmp";
(! -d "$destdir") and mkdir "$destdir",0770;
(! -f "$destdir/wiki.txt") and system "touch $destdir/wiki.txt";

(!defined $urlbase) and $urlbase = "URLBASE";
(!defined $urldir) and $urldir = "htdocs";
(!defined $filebasename) and $filebasename = "foo";
(!defined $destbasename) and $destbasename = $filebasename;
(!defined $description) and $description = "$destbasename Cbench data";

# buffer to build the wiki text in
my @wikitext = ();

# build a string with proper number of indent spaces
(!defined $indent) and $indent = 1;
my $indentstr = "";
for (1..$indent) {
	$indentstr .= " ";
}
push @wikitext, "$indentstr"."* $description\n";
push @wikitext, "$indentstr"."  * raw files for graph below\n";
my $rawfiles = "$indentstr"."    * ";

foreach $ext ('cmd', 'dat', 'ps', 'png') {
	my $filedescr = "";
	($ext =~ /cmd/) and $filedescr = "gnuplot script";
	($ext =~ /dat/) and $filedescr = "gnuplot data";
	($ext =~ /ps|png/) and $filedescr = "$ext image";

	(! -f "$filebasename\.$ext") and
		(print "$filebasename\.$ext does not exist!\n" and next);
	
	# copy file to destination directory with its possibly new name
	system "/bin/cp -vf $filebasename\.$ext $destdir/$destbasename\.$ext";

	# add to wikitext buffer to point to raw file
	$rawfiles .= "[/$urldir//$destbasename\.$ext $filedescr], ";
}

# finish the rawfiles wiki text
push @wikitext, "$rawfiles\n";

# add image macro to wikitext
push @wikitext, "\n$indentstr"."    [[Image($urlbase/$urldir/$destbasename\.jpg)]]\n\n";

open(WIKITEXT,">>$destdir/wiki.txt") or print "Error ($!) opening $destdir/wiki.txt\n";
print WIKITEXT @wikitext;
close(WIKITEXT);

# need to convert the ps to jpg
system "convert -rotate 90 $destdir/$destbasename\.ps $destdir/$destbasename\.jpg";
