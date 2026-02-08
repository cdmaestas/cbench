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
#include "meminfo.h"

#define SLEEP 5
#define MB (1024UL*1024UL)

#define DEBUG 1

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
        unsigned long long mem_delta1 = 0;
        unsigned long long mem_delta2 = 0;
        unsigned long long swap_delta = 0;
        int ret;
        MEMINFO memdata1;
        MEMINFO memdata2;
        MEMINFO memdata3;
		long dummy = 0xdeaddead;

		/* grab a snapshot of memory before MPI */
		meminfo(&memdata1);

        mpicall(MPI_Init, &argc, &argv);
        mpicall(MPI_Comm_size, MPI_COMM_WORLD, &size);
        mpicall(MPI_Comm_rank, MPI_COMM_WORLD, &rank);

        pagesize = sysconf(_SC_PAGESIZE);

		/* grab a snapshot of memory after MPI is initialized */
		meminfo(&memdata2);

		if (DEBUG) printf("Rank %d:  Before barrier\n", rank);

		if (rank == 0) dummy = 0xdeadbeef;
		mpicall(MPI_Bcast,(void*)dummy,1,MPI_LONG,0,MPI_COMM_WORLD);

		/* grab a snapshot of memory after a simple MPI op is performed */
		meminfo(&memdata3);

		mem_delta1 = (memdata1.free - memdata2.free) / 1024;
		mem_delta2 = (memdata2.free - memdata3.free) / 1024;

		/*
        printf("Rank %d: mem free before MPI = %llu kB, mem after MPI = %llu kB\n",
			rank, memdata1.free, memdata2.free);
		*/

        printf("Rank %d: mem used by MPI init = %llu kB, mem used by MPI barrier = %llu kB\n",
			rank, mem_delta1, mem_delta2);
        fflush(stdout);

        MPI_Finalize();

        return 0;
}
