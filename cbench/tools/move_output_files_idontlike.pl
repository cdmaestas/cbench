#!/usr/bin/perl

use Getopt::Long;

my $dest = "$ENV{PWD}/ARCHIVE$$";

GetOptions(
	'dest=s' => \$dest,
	'debug' => \$debug,
);

while (<STDIN>) {
	$l = $_;
	$l =~ s/\033\[\d+m//g;
	if ($l =~ /\((\S+)\)/) {
		$outfile = $1;
		($dir,$jobid) = $outfile =~ /^(\S+)\/slurm\.o(\d+)$/;

		#print "$outfile, $dir, $jobid\n";

		my $cmd = "mkdir -p $dest/$dir; mv -v $outfile $dest/$dir/slurm.o$jobid";
		($debug) and print "$cmd\n";
		system($cmd);
		print "---------------------------------------------------\n";
	}
}
