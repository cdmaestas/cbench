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

Original code written by John Naegle of Sandia National Labs

*/

#include <stdio.h>
#include <stdlib.h>
#include "mpi.h"

#define NUMBER_OF_TESTS 1
#define MSGLEN 0
#define DEBUG 0

/* 
   This version of pingpong sends and receives from the processes
   p, p + n/2

   If n is odd, leave out the "last" process
 */

int main( argc, argv )
int argc;
char **argv;
{
    double       *buf;
    int          rank, size, half_size;
    int          n;
    double       t1, t2, tmin = 0.0, tmin_local;
    double	*tmin_all;
    int          rotation, i, j, k, nloop;
    MPI_Status   status;
	int	namelen;
    int          source, dest;
	char processor_name[MPI_MAX_PROCESSOR_NAME];
    double overall_min = 99999999.0;
    double overall_max = 0.0;
    double average_total = 0.0;
    double link_average_total = 0.0;
    
    MPI_Init( &argc, &argv );

    MPI_Comm_rank( MPI_COMM_WORLD, &rank );
    MPI_Comm_size( MPI_COMM_WORLD, &size );
    MPI_Get_processor_name(processor_name,&namelen);

	printf("process %d on %s\n",
		rank,processor_name);    

/* If odd, reduce number of processes */
    if ((size & 0x1) != 0) {
	    size--;
    }
    if (size < 2) {
	    if (rank == 0) 
	        printf( "Must use at least 2 processes\n" );
	    MPI_Abort( MPI_COMM_WORLD, 1 );
    }

	tmin_all = (double *) malloc( size * sizeof(double) );
	if (!tmin_all) {
	    fprintf( stderr, 
		     "Could not allocate tmin_all buffer of size %d\n", size );
	    MPI_Abort( MPI_COMM_WORLD, 1 );
	}

    /* The rate printed by this program is the rate in the presense of contention */

    source = rank;
    dest   = (rank + (size/2)) % size;
    n=64;
	nloop=10000;
	half_size = size/2;
    for (rotation=0; rotation<half_size; rotation++) {

		source = rank;
		if(source < half_size) {
			dest = rank + half_size + rotation;
			if (dest>=size) dest -= half_size;
		}
		else {
			dest = rank - half_size - rotation;
			if (dest < 0) dest += half_size;
		}

		buf = (double *) malloc( n * sizeof(double) );
		if (!buf) {
	    	fprintf( stderr, 
		    	 "Could not allocate send/recv buffer of size %d\n", n );
	    	MPI_Abort( MPI_COMM_WORLD, 1 );
		}
		tmin = 1000;
		for (k=0; k<NUMBER_OF_TESTS; k++) {
			/* The barrier helps each link to start at about the same time */
	    	MPI_Barrier( MPI_COMM_WORLD );

	    	if (source < size/2) {
				/* Make sure both processes are ready */
				MPI_Sendrecv( MPI_BOTTOM, 0, MPI_INT, dest, 14,
			    		  MPI_BOTTOM, 0, MPI_INT, dest, 14, MPI_COMM_WORLD, 
			    		  &status );
				t1 = MPI_Wtime();
                for (j=0; j<nloop; j++) {
		    	    MPI_Send( buf, MSGLEN, MPI_DOUBLE, dest, k, MPI_COMM_WORLD );
				    MPI_Recv( buf, MSGLEN, MPI_DOUBLE, dest, k, MPI_COMM_WORLD, &status);
                }
				t2 = (MPI_Wtime() - t1) / nloop;
				if (t2 < tmin) tmin = t2;
	    	}
	    	else if (source < size) {
				/* If original size is odd, source == size on last process */
				tmin = 0.0;
				/* Make sure both processes are ready */
				MPI_Sendrecv( MPI_BOTTOM, 0, MPI_INT, dest, 14,
			    		  MPI_BOTTOM, 0, MPI_INT, dest, 14, MPI_COMM_WORLD, 
			    		  &status );
                for (j=0; j<nloop; j++) {
				    MPI_Recv( buf, MSGLEN, MPI_DOUBLE, dest, k, MPI_COMM_WORLD, &status);
		    	    MPI_Send( buf, MSGLEN, MPI_DOUBLE, dest, k, MPI_COMM_WORLD );
                }
	    	}
		}

		tmin_local = tmin * 1e6 / 2.0;

		/* Get the WORST case for output (could use MPI_MAXLOC to get
		   location as well) */
		MPI_Reduce( &tmin_local, &tmin, 1, MPI_DOUBLE, MPI_MAX, 0, 
		    	   MPI_COMM_WORLD );
		MPI_Gather( &tmin_local, 1, MPI_DOUBLE,
			tmin_all, 1, MPI_DOUBLE, 
			0, MPI_COMM_WORLD );

		if (rank == 0) {
	    	double rate;
        	double t_min = 99999999.0;
        	double t_max = 0.0;
        	double aggregate = 0.0;
        	double aggregate_floor = 0.0;

        	printf("rotate %d ** ",rotation);

	    	for (i=0;i<size/2;i++)
	    	{
            	if (tmin_all[i] > t_max)
                	t_max = tmin_all[i];
            	if (tmin_all[i] < t_min)
                	t_min = tmin_all[i];

            	aggregate += tmin_all[i];
		    	printf( "%.2lf , ", tmin_all[i] );
	    	}
        	aggregate_floor = t_min * half_size;        
	    	printf("** min=%.2lf max=%.2lf ave=%.2lf\n",
                	t_min,t_max,aggregate/half_size);

        	if (t_min < overall_min)
            	overall_min = t_min;
        	if (t_max > overall_max)
            	overall_max = t_max;

        	average_total += aggregate;
        	link_average_total += aggregate/half_size;
		}
		free( buf );
    }

    if (rank == 0) {
        printf("\nMin Link Latency: %.2lf us\n",overall_min);
        printf("Max Link Latency: %.2lf us\n",overall_max);
        printf("Average Link Latency: %.2lf us\n",link_average_total/half_size);
        printf("Using %d byte messages, %d tests of %d iterations\n",MSGLEN,
        	NUMBER_OF_TESTS,nloop);
    }

	free( tmin_all );
    MPI_Finalize( );
    return 0;
}
