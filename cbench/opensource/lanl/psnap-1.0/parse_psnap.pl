#!/usr/bin/perl

$total = 0;
$count = 0;
$bins = 0;
while (<STDIN>) {
	if (/^(\d+)\s+(\d+)\s+(\d+)\s+(\S+)$/) {
		$total += ($2 * $3);
		$count += $3;
		$bins++;
	}
}

$wave = $total / $count;
print "wave=$wave bins=$bins\n";
#0 1000 4 dn906
