#!/usr/bin/perl

$num1 = 0;
@buf = ();
while (defined($l = <STDIN>)) {
	if ($l =~ /VAPI_RETRY_EXC_ERR/) {
		$num1++;
		print "$l";
		$l =~ s/\033\[0m//g;
		$l =~ /\*PARSEMATCH\*\*\((.*)\)\s*\=/;
		$o_file = $1;
		($outid) = $o_file =~ /\.o(\d+)$/;
		$o_file =~ s/\.o$outid/\.e$outid/;
		$cmd = "/apps/contrib/vapi_diag.pl $ENV{'PWD'}\/$o_file | grep -v -P 'First'";
		push @buf, `$cmd`;

	}
}

foreach $l (@buf) {
	if ($l =~ /(\S+) destination VAPI_RETRY_EXC_ERR (\d+) times/) {
		if (! exists $list{$1}) {
			$list{$1} = $2;
		}
		else {
			$list{$1} += $2;
		}
	}
}

$num = 0;
foreach $k (sort {$list{$a} <=> $list{$b}} keys(%list)) {
	print "$k => $list{$k} VAPI_RETRY_EXC_ERR errors\n";
	$num++;
}
print "\nNum unique VAPI_RETRY_EXC_ERR nodes: $num\n";
print "Num VAPI_RETRY_EXC_ERR jobs: $num1\n";
