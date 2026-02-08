#!/usr/bin/perl -w

# There are a lot of different partitioning formats out there, and
# we need information about them.  Previously, I parsed fdisk.
# We will continue to do that for now but we will wrap the evil nasty
# fdisk parsing in here.

# set this to non-zero to get additional debugging information.
# (not normally needed).
my $fpdisk_debug = 0;

my $fdisk_type_cache;


# These hashes make it sane to call get_partition_info LOTS of times.
# Otherwise, these calls become very, very wasteful.
# for each disk partition, an array of information about that partition
# in the format returned by get_partition_info
my %partition_info_cache;

# for each disk, an array of information about that disk in the format
# returned by get_disk_info
my %disk_info_cache;

# call this with the device in question.
sub fdisk_type {
	my $device = shift;
	# at least TRY to speed this up if it gets called a lot
	if (defined($fdisk_type_cache)) {
		return $fdisk_type_cache;
	}
	if (! $device =~ /\/dev\//) {
		$device = "/dev/" . $device;
	}

	system("which pdisk >>/dev/null 2>/dev/null");
	if ($? != 0) {
		return "fdisk";
	}

	# at this point, it could still be either, if they are mixing
	# partitioning types.  so check with fdisk.

	if (!(`LC_ALL=C fdisk -l 2>/dev/null | grep "valid partition"` =~ /doesn.t contain a valid partition table/)) {
		if ($? == 0) {
			return "fdisk";
		}
	}
	# if it did match without errors, we must be needing pdisk.

	if (`pdisk -v 2>/dev/null` =~ /^version /) {
		return "pdisk-linux";
	} else {
		return "pdisk-darwin";
	}
}


# Returns the block device of a specified partition of a disk.
# We can't depend on just adding the partition number onto the end anymore,
# and the special cases are getting out of hand to put into every function
# that needs them.
# Thank you SO very much, BSD, devfs, and DAC960.
sub get_partition_of {
	my $disk = shift;
	my $partition_number = shift;


	# The order of these cases matter.  Put more general regexp matches
	# at the end.
	# Some of the cases aren't as general as they could be, because
	# I'm paranoid.

	#Other RAID
	if ($disk =~ /ida\/c\d+d\d+$/) {
		return $disk . "p" . $partition_number ;
	}
	#DAC960 RAID
	if ($disk =~ /rd\/c\d+d\d+$/) {
		return $disk . "p" . $partition_number ;
	}
	#Darwin/BSD
	if ($disk =~ /disk\d+$/) {
		return $disk . "s" . $partition_number ;
	}
	#devfs
	if ($disk =~ /^(.*?\/)disc$/) {
		return $1 . "part" . $partition_number;
	}
	#Old Linux
	if ($disk =~ /\w\w\w$/) {
		return $disk . $partition_number;
	}
	warn("Unable to calculate partition filename for $disk partition $partition_number");
	return;
}


# Returns the disk device of a partition.
# Calling this with a disk device instead of a partition device
# will result in bad things, don't do that.  You'll just confuse it.
sub get_disk_of {
	my $partition = shift;
	# Funky RAID style
	if ($partition =~ /(^.*?rd\/c\d+d\d+)p\d+/) {
		return $1;
	}
	# Other RAID style
	if ($partition =~ /(^.*?ida\/c\d+d\d+)p\d+/) {
		return $1;
	}
	# Darwin/BSD style
	if ($partition =~ /(^.*?disk\d+)s\d+/) {
		return $1;
	}
	# devfs Linux style
	if ($partition =~ /(^.*?)part\d+/) {
		return $1 . "disc";
	}
	# Old Linux Style
	if ($partition =~ /(^.*?\w\w\w+?)\d+/) {
		return $1;
	}
	warn("Unable to determine disk name for disk with partition $partition.");
}

# get the fdisk partitioning information.
sub get_partition_info_fdisk {
	my $partition = shift;
	my $disk = get_disk_of($partition);
	my $partnumber;

	$partition =~ /(\d+)$/;
	$partnumber = $1;


	open FDISK, 'LC_ALL=C fdisk -l ' . $disk . ' 2>&1 |';
	$_ = <FDISK>;
	while (defined($_) and not (/^\/dev\//)) {
		$_ = <FDISK>;
	}

	# don't skip a line here like on pdisk, this is actually
	# the line we want.
	# Understand this regexp and I'll send you a iCard.  :)
	while ( defined($_) and /^\/dev\/.*?(\d+)\s+\**\s+\d+\s+\d+\s+(\d+)\+*\s+(\d+)\s+(.*)/ ) {
		if ($1 == $partnumber) {
			($id, $volname, $size) = ($3, $4, $2);
		}
		my $key = get_partition_of($disk,$1);
		$partition_info_cache{$key} = [$3, $4, $2];
		$_ = <FDISK>;
	}
	return ($id, $volname, $size);
}

# almost the same as linux.  sigh.
sub get_partition_info_pdisk {
	my $partition = shift;
	my $diskopenline = shift;
	my $disk = get_disk_of($partition);
	my $partnumber;
	my ($id, $volname, $size);
	my @line;

	$partition =~ /(\d+)$/;
	$partnumber = $1;

	open PDISK, $diskopenline;
	$_ = <PDISK>;
	while (defined ($_) and not (/#: /)) {
		$_ = <PDISK>;
	}
	$_ = <PDISK>;

	# I'd really like to use split, but thanks to the * in the middle
	# of everything plus the spaces in the middle of one of the fields..
	# erk..  I can't decide which is uglier.
	while (defined($_) and /^\s*(\d+):\s+(\S*?)[\*\s](\D*?)\s+(\d+)/) {
		if ($1 == $partnumber) {
			($id, $volname, $size) = ($2, $3, $4);
		}
		my $key = get_partition_of($disk,$1);
		$partition_info_cache{$key} = [$2, $3, $4];
		$_ = <PDISK>;
	}
	close PDISK;
	if ( !defined ($id)) {
		if ($fpdisk_debug) {
			warn("Unable to find partition information for $partition");
		}
		return;
	} else {
		return ($id, $volname, $size);
	}
}

# Pass it a partition (/dev/hda9 or /dev/ide/host?/bus?/target?/lun?/part?)
# Returns back ( typecode , typename/volume name , size in blocks )
sub get_partition_info {
	my $partition = shift;
	if (! ($partition =~ /\/dev\//)) {
		$partition = "/dev/" . $partition;
	}

	if ( defined ($partition_info_cache{$partition}) ) {
		my @ret = @{$partition_info_cache{$partition}};
		return @ret;
	}

	my $disk = get_disk_of($partition);
	my $type = fdisk_type($disk);


	if ($type eq "fdisk") {
		return(get_partition_info_fdisk($partition));
	} elsif ($type eq "pdisk-linux") {
		return(get_partition_info_pdisk($partition,"pdisk -l $disk 2>&1 |"));
	} else {
		return(get_partition_info_pdisk($partition,"pdisk $disk -dump 2>&1|"));
	}
}


sub get_disk_info_fdisk {
	my $disk = shift;
	my $partitions = 0;
	my ($heads, $sectors, $cylinders);
	my ($cylsize, $blocksize);
	my $disksize;
	open FDISK, 'LC_ALL=C fdisk -l ' . $disk . " 2>&1 |";
	while (<FDISK>) {
		if (/(\d+) heads, (\d+) sectors.*, (\d+) cylinders/) {
			($heads, $sectors, $cylinders) = ($1, $2, $3);
		}
		if (/^Units = cylinders of (\d+) \* (\d+)/) {
			($cylsize, $blocksize) = ($1, $2)
		}
		if (/^\/dev\//) {
			++$partitions;
		}
	}
	close FDISK;
	if (!defined($heads) or !defined($blocksize)) {
		if ($fpdisk_debug) {
			warn("Unable to get disk information for disk $disk.");
		}
		return;
	}
	if ($cylsize != $heads * $sectors) {
		warn("Cylinder size mismatch for $disk!  Ignoring fdisk cylinder size.\n");
	}
	$disksize = $heads * $sectors * $cylinders;
	$disk_info_cache{$disk} = [ $disksize, $blocksize, $partitions ];
	return ($disksize, $blocksize, $partitions);
}

sub get_disk_info_pdisk {
	my $disk = shift;
	my $diskopen = shift;
	my $partitions = 0;
	open PDISK, $diskopen;
	while(<PDISK>) {
		if (/^\s*(\d+):/) {
			$partitions++;
		}
		if (/^Device block size=(\d+),\s+Number of Blocks=(\d+)/) {
			$disk_info_cache{$disk} = [ $2, $1, $partitions ];
			close PDISK;
			return ($2, $1, $partitions);
		}
	}			
	close PDISK;
	if($fpdisk_debug) {
		warn("Unable to get disk information for $disk.");
	}
	return;
}


# pass it a disk, get the size in blocks, the block size, and the number of 
# partitions
sub get_disk_info {
	my $disk = shift;
	if (! ($disk =~ /\/dev\//)) {
		$disk = "/dev/" . $disk;
	}

	if(defined($disk_info_cache{$disk})) {
		return @{$disk_info_cache{$disk}};
	}

	my $type = fdisk_type($disk);
	if($type eq "fdisk") {
		return(get_disk_info_fdisk($disk));
	} elsif ($type eq "pdisk-linux") {
		return(get_disk_info_pdisk($disk,"LC_ALL=C pdisk -l $disk 2>&1|"));
	} else {
		return(get_disk_info_pdisk($disk,"LC_ALL=C pdisk $disk -dump 2>&1|"));
	}
}

# pass a disk, returns a partition_info hash filled with entries, but
# only for that disk's partitions.
sub get_all_partition_info {
	my $disk = shift;
	my %partitions;
	my $partition_base;
	my $a;
	if (! ($disk =~ /\/dev\//)) {
		$disk = "/dev/" . $disk;
	}
	my $partition = get_partition_of($disk,1);
	$partition =~ /^(.*?)\d+$/;
	$partition_base = $1;	

	# we don't care about the return value, but this will fill the cache
	# for the disk concerned.
	get_partition_info($partition); 

	foreach $a (keys %partition_info_cache) {
		if ($a =~ /^$partition_base/) {
			$partitions{$a} = $partition_info_cache{$a};
		}
	}
	return %partitions;
}


1;
