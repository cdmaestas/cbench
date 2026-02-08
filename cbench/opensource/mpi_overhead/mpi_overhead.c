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
 * MPI program to attempt to measure the memory overhead of MPI
 */
#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <limits.h>
#include <unistd.h>
#include <mpi.h>
#include <sys/time.h>
#include <time.h>
#include "meminfo.h"
#include <assert.h>

#define SLEEP 5
#define MB (1024UL*1024UL)
#define	LEN 256

/*
 * All MPI calls wrapped with this so the code doesn't need return value
 * checking everywhere.  Used for all MPI calls except MPI_Abort and
 * MPI_Finalize.
 */
#define mpicall(f, args...) do {                                  \
                               if (f(args) != MPI_SUCCESS) {      \
                                   fprintf(stderr, #f" error\n"); \
                                   fflush(stderr);                \
                                   MPI_Abort(MPI_COMM_WORLD, 1);  \
                               }                                  \
                            } while (0);


int main (int argc, char **argv) {
        int rank, size;
        long i;
        long pagesize = 0;
        long long mem_delta1 = 0;
        long long mem_delta2 = 0;
        long long swap_delta = 0;
        int ret;
        MEMINFO memdata1;
        MEMINFO memdata2;
        MEMINFO memdata3;
	    char myhost[LEN];
        int hostlen = LEN;
    	time_t timestamp;

		/* grab a snapshot of memory before MPI */
		meminfo(&memdata1);

        mpicall(MPI_Init, &argc, &argv);
        mpicall(MPI_Comm_size, MPI_COMM_WORLD, &size);
        mpicall(MPI_Comm_rank, MPI_COMM_WORLD, &rank);

    	MPI_Get_processor_name(myhost, &hostlen);
    	timestamp = time(NULL);

		if (rank == 0) {
        	printf("Rank 0: MPI launch timestamp = %lu\n",
            	timestamp);
        }
        
		/* grab a snapshot of memory after MPI is initialized */
		meminfo(&memdata2);
		
        mpicall(MPI_Barrier, MPI_COMM_WORLD);

		/* grab a snapshot of memory after a simple MPI op is performed */
		meminfo(&memdata3);

		/* assert we have valid memory data > 0 unless mpi does something weird */
		assert (memdata1.free >= 0);
		assert (memdata2.free >= 0);
		assert (memdata3.free >= 0);
		if (memdata1.free <= memdata2.free) {
			printf ("host: %s reports more data free after MPI_Init! PRE: %llu POST: %llu\n", myhost, memdata1.free, memdata2.free);
		}
		mem_delta1 = (memdata1.free - memdata2.free); 
		assert (mem_delta1 >= 0);
		mem_delta1 = mem_delta1 / 1024;
		if (memdata2.free <= memdata3.free) {
				printf ("host: %s reports more data free for MPI_Barrier after MPI_Init! PRE: %llu POST: %llu\n", myhost, memdata2.free, memdata3.free);
			if (memdata1.free <= memdata3.free) {
				printf ("host: %s reports more data free for MPI_Barrier before MPI_Init! PRE: %llu POST: %llu\n", myhost, memdata2.free, memdata3.free);
			} else {
				/* get memory footprint from before init */
				mem_delta2 = (memdata1.free - memdata3.free);
			}
		} else {
			mem_delta2 = (memdata2.free - memdata3.free); 
		}
		assert (mem_delta2 >= 0);
		mem_delta2 = mem_delta2 / 1024;


/* DEBUG INFO
printf ("host: %s _ memdata1.free %llu _ memdata2.free %llu _ memdata3.free %llu _ mem_delta1 %llu _ mem_delta2 %llu\n", myhost, memdata1.free, memdata2.free, memdata3.free, mem_delta1, mem_delta2);
fflush(stdout);
*/

		/*
        printf("Rank %d: mem free before MPI = %llu kB, mem after MPI = %llu kB\n",
			rank, memdata1.free, memdata2.free);
		*/

        printf("Rank %d (%s): mem used by MPI init = %llu kB, mem used by MPI barrier = %llu kB\n",
			rank, myhost, mem_delta1, mem_delta2);
        fflush(stdout);

        MPI_Finalize();

		if (rank == 0) {
        	printf("Rank 0: Finished.\n");
        }
		
        return 0;
}
