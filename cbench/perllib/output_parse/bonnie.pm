# vim: syntax=perl tabstop=4
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


package output_parse::bonnie;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /output_parse::(\S+)/;

=head1 NAME

bonnie 

Cbench parse module responsible for parsing output files generated
Bonnie++ filesystem metatdata test
.

=cut

###############################################################
#
# Public methods
#

sub new {
	my $type = shift;
	my $self = {};
	bless $self, $type;
	$self->_init(@_) or return;

	return $self;
}


sub parse {
	my $self = shift;
	# a string identifying the file(s) we are parsing output from,
	# used mainly for printing out things
	my $fileid = shift;
	# should be one or more buffer references passed in,
	# they are ordered according to our very own FILE_LIST
	# array (see file_list() below)
	my @bufrefs = @_;

	my %data;

	my $status = 'NOTSTARTED';

    foreach (@bufrefs) {
		# process all the lines in the buffer
		my $txtbuf = $_;
		my $numlines = scalar @$txtbuf;

		foreach my $l (@{$txtbuf}) {
		#print "yo $l\n";
			($l =~ /CBENCH NOTICE/) and $status = $l;
			($l =~ /Writing with putc/) and $status = "STARTED";

			($l =~ /Version\s+\S+\s+.*Sequential Output.*Sequential Input/) and $status = 'COMPLETED';


			#Version 1.03d       ------Sequential Output------ --Sequential Input- --Random-
			#                    -Per Chr- --Block-- -Rewrite- -Per Chr- --Block-- --Seeks--
			#Machine        Size K/sec %CP K/sec %CP K/sec %CP K/sec %CP K/sec %CP  /sec %CP
			#tb6             16G 87042  99 128721  98 85973  97 78972  98 218669  95 156.2   0
			#                    ------Sequential Create------ --------Random Create--------
			#                    -Create-- --Read--- -Delete-- -Create-- --Read--- -Delete--
			#              files  /sec %CP  /sec %CP  /sec %CP  /sec %CP  /sec %CP  /sec %CP
			#                 16  1551  15  1615  31  1593   9  1923  14  1578  34  1669   6
			#tb6,16G,87042,99,128721,98,85973,97,78972,98,218669,95,156.2,0,16,1551,15,1615,31,1593,9,1923,14,1578,34,1669,6

			if ($l =~ /^\S+\,\S+\,\S+\,\S+\,\S+\,.*$/) {
				main::debug_print(2,"DEBUG:$shortpackage\.parse() bonnie csv data found");
				my @a = split(/,/,$l);
				$data{'sequential_write_char'} += $a[2];
				$data{'sequential_write_block'} += $a[4];
				$data{'sequential_write_rewrite'} += $a[6];
				$data{'sequential_read_char'} += $a[8];
				$data{'sequential_read_block'} += $a[10];
				$data{'random_seeks'} += $a[12];
				$data{'sequential_create'} += $a[15];
				$data{'sequential_create_read'} += $a[17];
				$data{'sequential_delete'} += $a[19];
				$data{'random_create'} += $a[21];
				$data{'random_create_read'} += $a[23];
				$data{'random_delete'} += $a[25];
			}
		}
	}

	if ($status =~ /COMPLETED/) {
		$data{'STATUS'} = "PASSED";
	}
	elsif ($status =~ /CBENCH NOTICE/) {
		# this means the job was not an error, but did not
		# run because of some known non-error reason
		$data{'STATUS'} = 'NOTICE';
		(my $tmp = $status) =~ s/CBENCH NOTICE://;
        defined $main::diagnose and main::print_job_err($fileid,'NOTICE',$tmp);
	}
	else {
		$data{'STATUS'} = "ERROR($status)";
        defined $main::diagnose and main::print_job_err($fileid,'ERROR',$status);
	}

	return \%data;
}

sub name {
	my $self = shift;
	return $self->{NAME};
}

sub file_list {
	my $self = shift;

	return \@{$self->{FILE_LIST}};
}

sub alias_spec {
    my $self = shift;

    return 'gears';
}

sub metric_units {
	my $self = shift;

	return \%{$self->{METRIC_UNITS}};
}


###############################################################
#
# "Private" methods
#

sub _init {
	my $self = shift;

	# save our name so callers can ask us
	$self->{NAME} = $package;
	$self->{SHORTNAME} = $shortpackage;

	# this is a KEY array... see the file_list method above for
	# more info
	@{$self->{FILE_LIST}} = qw/STDOUT/;

	# this is a KEY array... see the metric_units method above for
	# more info
	%{$self->{METRIC_UNITS}} = (
		'random_create_read' => 'ops/sec',
		'sequential_delete' => 'ops/sec',
		'sequential_create' => 'ops/sec',
		'sequential_create_read' => 'ops/sec',
		'sequential_write_char' => 'KB/s',
		'random_delete' => 'ops/sec',
		'sequential_read_block' => 'KB/sec',
		'random_seeks' => 'ops/sec',
		'random_create' => 'ops/sec',
		'sequential_read_char' => 'KB/s',
		'sequential_write_block' => 'KB/s',
		'sequential_write_rewrite' => 'KB/s',
	);
	
	return 1;
}


1;
