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


package output_parse::mpioverhead;

use strict;

my $package = __PACKAGE__;
my ($shortpackage) = $package =~ /output_parse::(\S+)/;

=head1 NAME

mpioverhead

Cbench parse module responsible for parsing output files generated
by the mpioverhead benchmark
.

=cut

###############################################################
#
# Public methods
#


=head1 PUBLIC METHODS

=over 4

=item B<new()> - Create a new parse object

  $obj = output_parse::mpioverhead->new();

=cut

sub new {
	my $type = shift;
	my $self = {};
	bless $self, $type;
	$self->_init(@_) or return;

	return $self;
}


=item B<parse()> - Responsible for actually parsing the output
contained in an output file and returning a hash reference with
the extracted data.

parse() takes a reference to a buffer (array) as the single input

  $obj = output_parse::mpioverhead->new();
  .
  read in an output file into @buf
  .
  $datahashref = $obj->parse(\@buf);
  for $k (keys %{$datahashref}) {
  print "$k => $datahashref->{$k}\n";
  }

The implementation of the parse() routine/method for a parse
module encompasses most of the work in creating a new
parse module.

=cut

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

	# process all the lines in the STDOUT buffer
	my $txtbuf = $bufrefs[0];
	my $numlines = scalar @$txtbuf; 

    my $status = 'NOTSTARTED';
	my $found_endrecord = 0;
	my $start_time = 0xdead;
	my $end_time = 0xdead;
	my $launch_time = 0xdead;
	my $total_mpi_mem = 0;
	my $num_ranks_found = 0;
    foreach my $l (@{$txtbuf}) {
        ($l =~ /CBENCH NOTICE/) and $status = $l;
        if ($l =~ /Timestamp before MPI launch = (\d+)/) {
			$start_time = $1;
		}
		
        if ($l =~ /Rank 0: MPI launch timestamp = (\d+)/) {
            $end_time = $1;
            $status = 'STARTED';

            # if we have all the timestamp data we can compute a
            # launch time
            if ($start_time != 0xdead and $end_time != 0xdead) {
                $launch_time = $end_time - $start_time;
                (defined $main::DEBUG and $main::DEBUG > 3) and print
					"$fileid: launch_time=$launch_time\n";
            }
		}

		if ($l =~ /Rank (\d+) \((\S+)\)\: mem used.*= (\d+).*= (\d+) kB/) {
            $num_ranks_found++;
            $total_mpi_mem += $3;
            (defined $main::DEBUG and $main::DEBUG > 3) and print
                "$fileid: rank=$1 mem=$3 ".
                "total_mem=$total_mpi_mem num_ranks=$num_ranks_found\n";
        }
	}

	if ($status =~ /STARTED/ and $num_ranks_found == $main::np and
        $launch_time != 0xdead) {
		$data{'STATUS'} = "PASSED";

        $data{'launch_time'} = $launch_time;
        $data{'ave_mpi_mem'} = ($total_mpi_mem/$main::np)/1024;
	}
    elsif ($status =~ /CBENCH NOTICE/) {
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

=item B<name()> - Return the name of the parse module

For example: output_parse::xhpl

=cut

sub name {
	my $self = shift;
	return $self->{NAME};
}

=item B<files_list()> - Return the ordered array of file(s) we
want to parse

For example: ['STDOUT','STDERR'] or  ['STDOUT','hpccoutf.txt']

STDOUT and STDERR are keywords and not actual filenames. The
keywords are groked by the output parsing core code and handled
appropriately.

=cut

sub file_list {
	my $self = shift;

	return \@{$self->{FILE_LIST}};
}

=item B<alias_spec()> - Return a regex specification of benchmark names
we will parse in addition to our module name, i.e. 'npb'

This routine is optional.

=cut

sub alias_spec {
	my $self = shift;

	return "(ohead)";
}

=item B<metric_units()> - Return a hash with a mapping of the
metrics this module returns to a string specifying the units
of the metric

=cut

sub metric_units {
	my $self = shift;

	return \%{$self->{METRIC_UNITS}};
}


###############################################################
#
# "Private" methods
#

=head1 PRIVATE METHODS

=over 4

=item B<_init> - parse arguments for B<new()>

Parse the arguments passed to B<new()> and sets the
appropriate object variables and such.

=cut

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
		'launch_time' => 'seconds',
		'ave_mpi_mem' => 'MegaBytes',
	);
	
	return 1;
}


1;
