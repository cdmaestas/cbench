#!/usr/bin/perl -w

#
# This program is part of the VA Cerberus Test Control System.
# Unless otherwise noted, Copyright (c) 2000 VA Linux Systems, 
# All Rights Reserved.
# You may distribute this program under the terms of the GNU General
# Public License, Version 2, or, at your option, any later version.
#

#
# va_detect.pm
# This is a simple detection library for use with Cerberus.
#

use fpdisk;
use File::Basename;
use Cwd;

# run this at startup
sub va_detect_init {
	my $i;
	system("/sbin/rmmod ide-scsi >> /dev/null 2>&1");
	foreach $i ("ide-cd","ide-floppy","ide-tape") {
		system("/sbin/modprobe $i >> /dev/null 2>&1");
	}
}

sub get_preferred_cdrom {
	my @cdrw=get_cdrw_drives();
	my @cdroms=get_cdrom_drives();
	my $i;
	my $j;
	my $prefer;
	my @preferences;

	foreach $i (@cdroms) {
		$prefer=1;
		foreach $j (@cdrw) {
			if ($i eq $j) {
				$prefer=0;
			}
		}
		if ($prefer) {
			push @preferences, $i;
		}
	}
	foreach $j (@cdrw) {
		push @preferences, $j;
	}

	return rationalize_device_names(@preferences);
}	

sub get_cdrom_drives {
	my @cdroms;
	my @cdroms_tmp;
	# find out any cdroms, don't burn them in!
	if ( -e "/proc/sys/dev/cdrom/info" ) {
		$_=`cat /proc/sys/dev/cdrom/info | grep "drive name" | cut -f 2 -d :`;
		@cdroms_tmp = split;
	}
	foreach $_ (@cdroms_tmp) {
		if (/sr(\d)/) {
			push @cdroms, "scd".$1;
		} else {
			push @cdroms, $_;
		}
	}
	return rationalize_device_names(@cdroms);
}

sub get_cdrw_drives {
	my @cdrw;
	# find all SCSI
	my $count=0;
	open SCSI, "/proc/scsi/scsi";
	while (defined($l = <SCSI>)) {
		chomp $l;
		if ($l =~ /Type:\s+CD-ROM/ ) {
			++$count;
		} elsif ($l =~ /Model:\s+CD-Writer/i) {
			push (@cdrw, "scd".$count);
		} elsif ($l =~ /Model:\s+CD-RW/i) {
			push (@cdrw, "scd".$count);
		}
	}
	# TODO: IDE not supported
	return rationalize_device_names(@cdrw);
}

sub ident_ide_floppy {
	my $ide_floppy=shift;
	$_=`cat /proc/ide/$ide_floppy/model`;
	foreach $i ("ZIP 250", "LS-120") {
		if (/$i/) {
			return $i;
		}
	}
}

sub get_ide_floppies {
	my $i;
	my @try_drives;
	$_=`ls -d /proc/ide/hd? 2>/dev/null | cut -f 4 -d / 2>/dev/null`;
	@try_drives=split;
	my @ide_floppies;
	foreach $i (@try_drives) {
		if ( $i =~ /hd/ ) {
			system ("cat /proc/ide/$i/driver | grep \"ide-floppy\" >> /dev/null 2>&1");
			if ( $? == 0 ) {
				push @ide_floppies, $i;
			}
		}
	}
	return rationalize_device_names(@ide_floppies);
}

sub get_scsi_floppies {
        my @scsiflop;
        # Detect all known USB floppy drives (currently only one, mine :))
        # Generally these shouldn't be burned in.
        if ( -e "/proc/scsi/scsi" ) {
                my $count = 0;
                my $l;
                open SCSI, "/proc/scsi/scsi";
                while (defined($l = <SCSI>)) {
                        chomp $l;
                        if ($l =~ /Type:\s+Direct-Access/ ) {
                                ++$count;
                        } elsif ($l =~ /Vendor:\s+Y-E DATA\s+Model:\s+USB-FDU/i) {
                                push (@scsiflop, "sd".chr(ord("a")+$count));
                        }
                }
		close SCSI;
        }
        return rationalize_device_names(@scsiflop);
}

sub get_misc_floppies {
	my @floppydev;
	@floppydev = get_ide_floppies();
	push(@floppydev, get_scsi_floppies());
	return @floppydev;
}


# gets Iomega devices attached to SCSI.
sub get_jaz_drives {
	my @jazzip;
	# Detect everything made by Iomega (TM)
	# Generally these shouldn't be burned in.
	if ( -e "/proc/scsi/scsi" ) {
		# JAZ detection from testproc 1.1.2
		my $count = 0;
		my $l;
		open SCSI, "/proc/scsi/scsi";
		while (defined($l = <SCSI>)) {
			chomp $l;
			if ($l =~ /Type:\s+Direct-Access/ ) {
				++$count;
			} elsif ($l =~ /Vendor:\s+iomega/i) {
				push (@jazzip, "sd".chr(ord("a")+$count));
			}
		}
		close SCSI;
	}
	return rationalize_device_names(@jazzip);
}

# gets all LVM partitions
sub get_lvm_drives {
	my @lvmtab;
	my @vgdir;
	my @lvm_drives;
	my $vg;
	my $lv;

	`vgscan > /dev/null 2>&1`;
	@lvmtab = `ls -1 /etc/lvmtab.d`;
	foreach $vg (@lvmtab) {
		chop $vg;
		@vgdir = `ls -1 /dev/$vg | grep -v group`;
		foreach $lv (@vgdir) {
			chop $lv;
			push @lvm_drives, "$vg/$lv";
		}
	}

	return rationalize_device_names(@lvm_drives);
}

# get all drives
sub get_drives {
	my @drives;
	my @line;
	my $i;
	my $temp;
	my $device;
	my $lvm_flag = 0;
	
	open (PARTITIONS,"/proc/partitions");
	# skip two lines
	<PARTITIONS>;
	<PARTITIONS>;
	
	while (<PARTITIONS>) {
		@line = split;
		$device = $_ = $line[3];
		if ( defined($device) and ((! /\D*\d/) or /c\d*d\d*$/ or /disc$/) and !/lvm/ ) {
			# woohoo! no more calling fdisk directly!
			my %partinfo = get_all_partition_info($device);
			my @types;
			foreach $i (keys %partinfo) {
				# get the second element of each list
				push @types, ${${partinfo}{$i}}[1];
			}
			if(grep /LVM/, @types) {
				$lvm_flag = 1;
			} else {
				push @drives, $device;
			}
		}
	}
	
	if ($lvm_flag == 1) {
		push @drives, get_lvm_drives();
	}

	return rationalize_device_names(@drives);
}

# get_makej_parameter is now get_numcpus.  duh.
sub get_numcpus {
	# * 1 to quickly clear out the extra spaces
	return `cat /proc/cpuinfo  | grep processor | wc -l` * 1;
}

sub get_linux_partitions {
	my @drives = @_;
	my @partitions;
	my $part;
	my $drive;

	foreach $drive (@drives) {
		my %parthash = get_all_partition_info($drive);
		foreach $part (keys %parthash) {
			# we'll key off the volume name
			my $ident = ${$parthash{$part}}[1];
			if ($ident eq "Linux" or $ident eq "Linux Native") {
				push(@partitions,$part);
			}
		}
	}

	if (`grep -i lvm /proc/partitions | wc -l` != 0) {
		push @partitions, get_lvm_drives();
	}
	
	return rationalize_device_names(@partitions);
}

sub get_swap {
	my $swapram = 0;
	open (SWAP, "/proc/meminfo");
	while (<SWAP>) {
		if ( /SwapTotal:\s*(\d*)\skB/ ) {
			$swapram += $1;
		}
	}
	return $swapram;
}

sub get_ram {
	my $kbram = 0;
	open (MEMORY, "/proc/meminfo");

	while (<MEMORY>) {
		if ( /MemTotal:\s*(\d*)\skB/ ) {
			$kbram += $1;
		}
	}
	return $kbram;
}


# We need to rationalize symlinks in order to insure that we aren't
# misidentifying drives twice or trying to compare /dev/ide/bus* to /dev/hda,
# for example.  It's easy to get this sort of thing subtlely wrong, so..
sub get_real_name {
	my $suspect = shift;
	my $name = "";
	my $dir;

	# We use changing the directory to rationalize the filenames.
	# There is a better way, but it is much more complex to code and
	# I don't see the need.
	my $origdir = getcwd();
	my $flag = 0;

	# I always want to process the suspect string once.
	# That's because it might _not_ be a symbolic link,
	# but contain symbolic links in the path.
	while (-l $name or not $flag) {
		$dir = dirname($suspect);
		if (!chdir($dir)) {
			warn("Attempted to rationalize a non-existent file/directory $dir");
			return;
		}
		$dir = getcwd();
		$name = basename($suspect);
		# why not -L like in sh?  bah...  if they're going to be
		# backwards compatible, get it right.
		if (-l $name) {
			$suspect = readlink($name);
		}
		$flag = 1;
	}
	# go back home
	chdir ($origdir);
	if ($dir eq "/") {
		return($dir . $name);
	} else {
		return($dir . "/" . $name);
	}
}

# Correct a list of filenames, eliminating all symlinks from the pathname.
# Call this on a collection of device names before comparing it to anything
# else or returning it.
sub rationalize_device_names {
	my @source = @_;
	my @dest;
	my $suspect;
	my $olddir = getcwd();

	# all of our device names are relative to /dev, at least ;)
	chdir("/dev");

	while ($suspect = shift(@source)) {
		if($suspect = get_real_name($suspect)) {
			# in order to remain backwards compatible with
			# anyone who is using this library, dev inodes outside
			# of /dev are not supported.  Who would do that,
			# anyway?
			$suspect =~ /\/dev\/(.*)/;
			push(@dest,$1);
		}
	}
	chdir($olddir);
	return @dest;
}

va_detect_init;
#print get_ide_floppies;
#print "\n";
#print get_drives;
#print "\n";
#print get_cdrom_drives;
#print "\n";
#print get_jaz_drives;
#print "\n";
#foreach $i (get_ide_floppies) {
#	print "$i: ";
#	print ident_ide_floppy($i);
#	print "\n";
#}
1;
