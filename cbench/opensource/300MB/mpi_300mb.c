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
 *  mpi_300mb.c
 *
 *  Jeff Ogden ( jeffry.ogden@hp.com )
 *
 *  Braindead simple MPI "Hello World" to achieve a 300 MB
 *  executable.
*/

#include <stdio.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/time.h>
#include <time.h>
#include <mpi.h>

#define MB              (1024 * 1024)
#define LIB_SIZE_FUDGE  (1 * MB)
#define HOG_SIZE        ((300 * MB) - LIB_SIZE_FUDGE)
volatile char hog[HOG_SIZE] = {55};

int main(int argc, char *argv[])
{
    int size;
    int rank;
    int i;
    char myhost[256];
    time_t timestamp;
    struct timeval start;
    struct timeval stop;
    int elapsed;
    
    gettimeofday(&start, NULL);
    gethostname(myhost, 256);
    timestamp = time(NULL);
    
    if ( MPI_Init( &argc, &argv ) != MPI_SUCCESS )
    {
        printf("Unable to initialize MPI\n");
        exit(0);
    }

    MPI_Comm_size( MPI_COMM_WORLD, &size );
    MPI_Comm_rank( MPI_COMM_WORLD, &rank );
    
    MPI_Barrier( MPI_COMM_WORLD );
    timestamp = time(NULL);

    if (rank == 0) {
        printf("%s started at %s\n",myhost,ctime(&timestamp));
    }
    
    printf("Hello world, I am rank %d\n", rank);
    
    /* touch all the memory to force Linux to fault it in */
    for (i = 0; i < HOG_SIZE; i++) {
        hog[i] = 100;
    }
    
    MPI_Barrier( MPI_COMM_WORLD );
    
    gettimeofday(&stop, NULL);
    timestamp = time(NULL);
    
    if (rank == 0) {
        printf("All nodes finished touching memory at %s",ctime(&timestamp));
        elapsed = stop.tv_sec - start.tv_sec;
        printf("Elapsed seconds with gettimeofday() = %d\n",elapsed);
    }

    MPI_Finalize();

    return 0;
}
