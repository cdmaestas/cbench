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
 * MPI program to attempt to measure the time overhead of MPI
 */
#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <limits.h>
#include <unistd.h>
#include <mpi.h>
#include <sys/time.h>
#include <time.h>
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
    	time_t timestamp;

    	timestamp = time(NULL);
		fprintf(stderr, "main() launch: %s\n",ctime(&timestamp));

        int rank, size;
        long i;
        long pagesize = 0;
        int ret;
	char myhost[LEN];
        int hostlen = LEN;

        mpicall(MPI_Init, &argc, &argv);
        mpicall(MPI_Comm_size, MPI_COMM_WORLD, &size);
        mpicall(MPI_Comm_rank, MPI_COMM_WORLD, &rank);

    	MPI_Get_processor_name(myhost, &hostlen);
    	timestamp = time(NULL);

	if (rank == 0) {
		printf("%s MPI launch: %s\n",myhost,ctime(&timestamp));
        }
        
        mpicall(MPI_Barrier, MPI_COMM_WORLD);

        MPI_Finalize();

    	timestamp = time(NULL);
	if (rank == 0) {
		printf("%s POST MPI_Finalize(): %s\n",myhost,ctime(&timestamp));
        }
        return 0;
}
