#!/usr/bin/perl

#
# VA-CTCS's custom hash storage routine.
# Woof.  We should replace this.
#

sub load_hash {
        my $hashref = shift;
        my $filename = shift;
        my $key;
        open (HASH, $filename) or return 0; #false
        while (<HASH>) {
                s/\n//gs;
                $key = $_;
                if (defined ($_ = <HASH>)) {
                        s/\n//gs;
                        if ( $_ =~ /\S+\s+\S+/ ) {
                                my @list;
                                @list = split ' ',$_ ;
                                $hashref->{$key} = \ @list;
                        } else {
                                s/\s//gs;
                                $hashref->{$key} = $_;
                        }
                }
        }
        close HASH;
        return 1; # true
}

sub save_hash {
        my $hashref = shift;
        my $filename = shift;
        my $key;
        my $item;
        open (HASH, "> $filename") or return 0; #false
        seek HASH, 0, 0;
        foreach $key (keys(%$hashref)) {
                print HASH "$key\n";
                if (ref($hashref->{$key}) eq "ARRAY") {
                        print HASH join ' ',@{$hashref->{$key}};
                } else {
                        print HASH "$hashref->{$key}";
                }
                print HASH "\n";
        }
        close HASH;
        return 1;
}

1;
