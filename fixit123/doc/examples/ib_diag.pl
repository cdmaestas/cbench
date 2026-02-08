#!/usr/bin/perl -w

use strict;
use warnings;
use Carp;
use Getopt::Long;
use Term::ANSIColor qw(color :constants);

my ($threshold, $vmessage, $debug, $verbose) = (0, undef, 0, 0);
my %ib_messages;
GetOptions(
    'threshold=i' => \$threshold,
    'verbose=i' => \$verbose,
    'debug=i' => \$debug,
);

#
# maybe make a threshold variable when to print a suspect
#
$threshold=1 unless $threshold;

my $file = $ARGV[0] or croak "Usage: $0 pbs_error_file";

open (LIST,"<$file") or die "ERROR: Could not open $file for reading\n";
my (@tmp,$k,%srcndct,%destndct,$src,$dest);
while(<LIST>) {
        chomp;

	# VAPI_PORT_ERROR 

	if (/VAPI_PORT_ERROR/) { 
		# if we get a port error, we want to ignore threshold
		$threshold=1;
print "$_\n" if $debug >= 9;
		$vmessage = "VAPI_PORT_ERROR";
		# maybe match to end of line after getting dest (null) -cdm
		#[175] Abort: [dn611:175] Got an asynchronous event: VAPI_PORT_ERROR (VAPI_EV_SYNDROME_NONE) dest rank = [(null):512] *
		@tmp = /\[(\d+)\] (\S+:) \[(.n\d+):(\d+)\] (\S+ \S+ \S+ \S+:) (\S+ \(\S+\)) (\S+ \S+ \=) \[(\(\S+)\):(\d+)\] */;
		$src = $tmp[2];

		#[an445] : [an445:121] Got an asynchronous event: VAPI_PORT_ERROR (VAPI_EV_SYNDROME_NONE) dest rank = [(null):184] at line 174 in file viainit.c
		if (!@tmp) {
			@tmp = /\[(.n\d+)\] : \[(.n\d+):(\d+)\] (\S+ \S+ \S+ \S+:) (\S+ \(\S+\)) (\S+ \S+ \=) \[(\(\S+)\):(\d+)\] */;
			$src = $tmp[0]; 
		}
		#[dn585:30] Got an asynchronous event: VAPI_PORT_ERROR (VAPI_EV_SYNDROME_NONE) dest rank = [(null):32] at line 174 in file viainit.c
		if (!@tmp) {
			@tmp = /\[(.n\d+):(\d+)\] (\S+ \S+ \S+ \S+:) (\S+ \(\S+\)) (\S+ \S+ \=) \[(\(\S+)\):(\d+)\]/; 
			$src = $tmp[0]; 
		}
		if (!@tmp) {
			print "NEW VAPI PORT ERROR MESSAGE TO MATCH! $_\n";
			$src="UNKNOWN";
		}
		$dest = "null";
print "$src ... $dest\n" if $debug >= 5;

#########	print "$src ... $dest\n";
	#[204] Abort: [an677:204] Got completion with error, code=VAPI_RETRY_EXC_ERR, vendor code=81 dest rank=[an900:0]
	#[947] Abort: [bn851:947] Got completion with error, code=VAPI_RETRY_EXC_ERR, vendor code=81 dest rank=[bn997:930]
	#[928] Abort: [cn119:928] Got completion with error, code=VAPI_RETRY_EXC_ERR, vendor code=81, dest rank=[bn997:931]
	#[25] Abort: [dn632:25] Got completion with error, code=VAPI_RETRY_EXC_ERR, vendor code=81, dest rank=[dn866:27]
	# or
	#[an687:190] Got completion with error, code=VAPI_RETRY_EXC_ERR, vendor code=81 dest rank=[an900:0]
	} elsif (/VAPI_RETRY_EXC_ERR/) { 
print "$_\n" if $debug >= 9;
		$vmessage = "VAPI_RETRY_EXC_ERR";
        	@tmp = /\[(\d+)\] (\S+): \[(.n\d+):(\d+)\] (\S+ \S+ \S+ \S+), (\S+\=\S+, \S+ \S+\=\d+), (\S+) (\S+)\=\[(.n\d+):(\d+)\]/;
		if ($tmp[2]) {
print "1st case $_\n" if $debug >= 2;
			$src=$tmp[2];
			$dest=$tmp[8]; 
		} else { # other case
print "2nd case $_\n" if $debug >= 2 and !$tmp[2];
			@tmp = /\[(.n\d+):(\d+)\] (\S+ \S+ \S+ \S+,) (\S+\=\S+, \S+ \S+\=\d+) (\S+) (\S+)\=\[(.n\d+):(\d+)\]/;
			$src=$tmp[0];
			$dest=$tmp[6];
		}
	} elsif (/VAPI/) {
		print "NEW VAPI ERROR!\n";
		print "$_\n";
	} elsif (/Catastrophic/) {
		print "VAPI CATASTROPHIC ERROR!\n";
		print "$_\n";
		next;
#[0,1,41][btl_openib_component.c:894:mca_btl_openib_component_progress] from dn162 to: dn294 error polling HP CQ with status RETRY EXCEEDED ERROR status number 12 for wr_id 47537860 opcode 0
#[0,1,41][btl_openib_component.c:894:mca_btl_openib_component_progress] from dn162 to: dn294 error polling HP CQ with status WORK REQUEST FLUSHED ERROR status number 5 for wr_id 26306726 opcode 0
	} elsif (/btl_openib_component.c:894:mca_btl_openib_component_progress/) {
		print "OFED/OMPI ERROR!\n";
		print "$_\n";
	} else {
		next;
	}

	# setup a hash where vmessage is key and has an array of source dest ndoes
	my $vsource = "SOURCE:$src";
	if ($dest ne "null") {
		my $vdest = "DEST:$dest" if $dest ne "null";
		my $vsd = "SOURCE::$src<->DEST::$dest";
		# check if vdest and vsd is defined
		if (!defined $ib_messages{$vmessage}{$vdest}) {
			$ib_messages{$vmessage}{$vdest} = 1;
		} else {
			$ib_messages{$vmessage}{$vdest}++;
		}
		if (!defined $ib_messages{$vmessage}{$vsd}) {
			$ib_messages{$vmessage}{$vsd} = 1;
		} else {
			$ib_messages{$vmessage}{$vsd}++;
		}
	}

	if (!defined $ib_messages{$vmessage}{$vsource}) {
		$ib_messages{$vmessage}{$vsource} = 1;
	} else {
		$ib_messages{$vmessage}{$vsource}++;
	}
}

# https://www.linuxnotes.net/perlcd/prog/ch09_04.htm
foreach my $vm (sort keys %ib_messages) {
	print BOLD RED "$vm\n";
	my ($nd,$cnt);
	foreach $nd (sort keys %{$ib_messages{$vm}}) {
		print "$ib_messages{$vm}{$nd} < $threshold\n" if $debug >= 5;
		next if $ib_messages{$vm}{$nd} < $threshold;
		print RESET "NODE: ";
		print BOLD BLUE "$nd ";
		print RESET "COUNT: ";
		print BOLD YELLOW ON_BLUE "$ib_messages{$vm}{$nd}";
		print RESET "\n";
	}
}

