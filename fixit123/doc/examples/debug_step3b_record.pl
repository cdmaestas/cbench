#!/usr/bin/perl

use Date::Manip;
use Getopt::Long;

GetOptions(
	'debug' => \$DEBUG,
	'name=s' => \$logname,
    'status' => \$status,
    'record' => \$record,
);


$DIR="/apps/breakfix-testing";
$LOGDIR="$DIR/logs_step123";
$MAINLOG="$LOGDIR/breakfix_step3.log";
$STEP3ADIR="$LOGDIR/step3a";

$HWTDIR="/scratch3/cbench-test-tbird/nodehwtest";

$CBENCHOME="/apps/cbench";
$CBENCHTEST="/scratch3/cbench-test-tbird";

$job_running = 0;
$job_finished = 0;
$minmimum_runtime = 20 * 60; # in minutes
$finish_stamp = 99;
$delta_min = -99;

# find the most recent step3a log file
$latest_log = `cd $STEP3ADIR; ls -1rt *.log | tail -1`;
chomp $latest_log;
die "Could not find a STEP3A log file" unless ($latest_log =~ /\.log/);
($step3basename) = $latest_log =~ /(\S+)\.log/;

(defined $logname) and $step3basename = $logname;
$step3logfile = "$STEP3ADIR\/$step3basename\.log";

print "Found step3 run tagged: $step3basename\n";



$status = 'PASSED, READY for REINTEGRATION';

# if --record is specified, record the results of the step3 run
# in the breakfix log for step3
if (defined $record) {
    $nodefile = "$STEP3ADIR\/$step3basename\.nodelist";
    open (IN,"<$nodefile") or die
	    "Could not open $nodefile ($!)";
    @nodebuf = <IN>;
    close(IN);

	# open the step3 breakfix log

    open (OUT,">>$MAINLOG") or die
	    "Could not open $MAINLOG ($!)";

    # record log entries
    foreach $l (@nodebuf) {
	    chomp $l;
        printf OUT "%s NODE %s => STEP3B %s, step3a tag %s\n",
    		get_timestamp(),$l,$status,$step3basename;
    }

    close(OUT);

}
else {
	print "STEP3B result was NOT recorded to the step3 breakfix log, use\n".
    	"the --record option to do so\n";
}



sub get_timestamp {
	my ($sec, $min, $hour, $day, $mon, $year, $wday, $yday, $isdst) = localtime;
    
    $year = $year - 100;
    $stamp = sprintf "%02d/%02d/%02d %02d:%02d",$mon+1,$day,$year,$hour,$min;
    return $stamp;
}
