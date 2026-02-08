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

# add Fixit123 perl library to the Perl search path
use lib ($ENV{FIXIT123_HOME} ? "$ENV{FIXIT123_HOME}\/perllib" :
    "$ENV{HOME}\/fixit123\/perllib");


use Getopt::Long;
use Data::Dumper;
use XML::Simple;

GetOptions(
	'file=s' => \$file,
);


my $xml = XMLin($file, ForceArray => 0 );
#print Dumper ($xml);

foreach $j (keys %{$xml}) {
	print "$j";
	if (ref $xml->{$j} eq 'SCALAR') {
		print "= $xml->{$j}\n";
	}
	else {
		print "\n";
	}
	(ref $xml->{$j} eq 'ARRAY') and enumerate_array($xml->{$j},$j);
	(ref $xml->{$j} eq 'HASH') and enumerate_hash($xml->{$j},$j);
}


sub enumerate_hash {
	my $href = shift;
	my $tag = shift;

	foreach $j (keys %{$href}) {
		my $newtag = "$tag $j";
		($j =~ /HASH/) and $newtag = "$tag";
		print "H $newtag";
		if (ref $href->{$j} eq '') {
			print "=$href->{$j}\n";
		}
		else {
			print "\n";
		}

		(ref $href->{$j} eq 'ARRAY') and enumerate_array($href->{$j},"$newtag");
		(ref $href->{$j} eq 'HASH') and enumerate_hash($href->{$j},"$newtag");
	}
}

sub enumerate_array {
	my $aref = shift;
	my $tag = shift;

	foreach $j (@$aref) {
		my $newtag = "$tag $j";
		($j =~ /HASH/) and $newtag = "$tag";
		print "A $newtag";
		if (ref $j eq '') {
			print "=$j\n";
		}
		else {
			print "\n";
		}

		(ref $j eq 'ARRAY') and enumerate_array($j,"$newtag");
		(ref $j eq 'HASH') and enumerate_hash($j,"$newtag");
	}
}



# some LibXML messing...
=pod

use XML::LibXML;
my $parser = XML::LibXML->new;
$doc = $parser->parse_file("$file");

# find title elements
#my @nodes = $doc->findnodes("/books/book/title");
my @nodes = ();
if (defined $find) {
	@nodes = $doc->findnodes("$find");
}
else {
	@nodes = $doc->findnodes("Firmware");
}


# print the text in the title elements
foreach my $node (@nodes) {
	print $node->nodeName, "== \n";
	print $node->firstChild->nodeName," ", $node->firstChild->data, "\n";
}
=cut
