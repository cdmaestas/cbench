/*
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
*/

/*
 * Simple MPI program to print "hello from rank x" in order for each process.
 * Note: Rank numbers are 0-based.
 */

#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <mpi.h>

int main (int argc, char **argv) {
    int rank, size;
    long dummy;
    char hostname[256];
    char ssize[256];     /* a string representation of size */
    char fmt[256];

    if ( gethostname(hostname, 256) ) {
        fprintf(stderr, "Unable to get hostname\n");
        sprintf(hostname, "UNKNOWN");
    }

    if ( MPI_Init(&argc, &argv) != MPI_SUCCESS ) {
        printf("MPI Init error\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    MPI_Comm_size(MPI_COMM_WORLD, &size);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);

    if ( rank != 0 ) {
        /* receive from n-1 node */
        if ( MPI_Recv(&dummy, 1, MPI_LONG, rank-1, MPI_ANY_TAG, MPI_COMM_WORLD, MPI_STATUS_IGNORE) != MPI_SUCCESS ) {
            printf("MPI Recv error\n");
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
    }

    sprintf(ssize, "%d", size);
    sprintf(fmt, "Hello, I am node %%s with rank %%%lud (%%d/%%d)\n", strlen(ssize));
    printf(fmt, hostname, rank, rank+1, size);
    fflush(stdout);
    /*usleep(1000);*/

    if ( rank != (size - 1) ) {
        /* send message to n+1 node */
        if ( MPI_Send(&dummy, 1, MPI_LONG, rank+1, 1, MPI_COMM_WORLD) != MPI_SUCCESS ) {
            printf("MPI Send error\n");
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
    }

    MPI_Finalize();

    return 0;
}
