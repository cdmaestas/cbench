#!/usr/bin/perl

use Getopt::Long;

GetOptions(
	'version=s' => \$version,
	'hwtype=s' => \$hwtype,
	'fwtype=s' =>  => \$fwtype,
	'debug' => \$DEBUG,
);

my %data = (
	'ilo' => {
		'1.89' => 'CP007118.scexe',
	},
	'bios' => {
		'dl360g4' => {
			'02/14/2006' => 'cp006555.scexe',
		},
		'dl360g3' => {
			'03/03/2005' => 'CP005348.scexe',
		},
		'dl380g3' => {
			'03/03/2005' => 'dunno.scexe',
		},
	},
	'storage' => {
		'SMART6I' => {
			'2.76' => 'CP007624.scexe'
		},
		'SMART5I' => {
			'2.66' => 'CP006721.scexe'
		},
	},
	'nic' => {

	},
);

if ($fwtype =~ /ilo/ and exists $data{$fwtype}{$version}) {
	print "$data{$fwtype}{$version}\n";
}
elsif (exists $data{$fwtype}{$hwtype}{$version}) {
	print "$data{$fwtype}{$hwtype}{$version}\n";
}
else {
	print "ERROR: Can't find what you are looking for\n";
	exit 1;
}


