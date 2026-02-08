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

  This program was created to find slow nodes on Red Storm.
  It allocates several large arrays and does numerical operations on
  those arrays.  Currently, we can correlate a large number of ECC
  errors on a node to a node being slow.  In doing numerical operations
  over a large part of the available memory, we hit most of memory and
  can trigger those errors which cause a longer run time.  The run times
  on all of the processors is then compared and anything that is not
  within 1% of the mean is printed out.

  Currently allocates about 870 MBytes of memory and does about 7.7 seconds
  of numerical operations.

  Arthor: Courtenay T. Vaughan, 9224, SNL
  Written: March 27, 2005
*/

#include <stdlib.h>
#include <mpi.h>

#define ASIZE 35000000  /* array size - change to allocate more memory */
//#define ASIZE 3500000  /* array size - change to allocate more memory */
#define REPT 30

main(int argc, char **argv)
{
   int rank, size, i, j, k, *ind;
   double time1, time2, *times, *work, *x, *y, *z, mean, tol, diff;

   MPI_Init(&argc, &argv);
   MPI_Comm_rank(MPI_COMM_WORLD, &rank);
   MPI_Comm_size(MPI_COMM_WORLD, &size);
   if (!rank) printf("start\n");

   ind = (int *) malloc(size*sizeof(int));
   times = (double *) malloc(size*sizeof(double));
   work = (double *) malloc(size*sizeof(double));
   for (i = 0; i < size; i++)
     work[ind[i] = i] = 0.0;

   x = (double *) malloc(ASIZE*sizeof(double));
   y = (double *) malloc(ASIZE*sizeof(double));
   z = (double *) malloc(ASIZE*sizeof(double));
   if (x == NULL || y == NULL || z == NULL) {
     printf("Memory error\n");
     exit(0);
   }

   time1 = MPI_Wtime();
   for (i = 0; i < ASIZE; i++) {
     x[i] = 10.0/(i+1);
     y[i] = (ASIZE - i)*8.0;
     z[i] = 0.0;
   }
   mean = 0.0;
   for (i = 0; i < (ASIZE - REPT); i++) {
     for (j = 0; j < REPT; j++)
          z[i] += x[i+j]*y[i] + x[i]*y[i+j];
     mean += z[i];
   }
   time2 = MPI_Wtime() - time1;

   work[rank] = time2;
   MPI_Allreduce(work, times, size, MPI_DOUBLE, MPI_SUM, MPI_COMM_WORLD);
   work[rank] = mean;

   if (!rank) {                         /* Have processor 0 process results */
     for (i = 0; i < size; i++)         /* brain-dead but adaquate sort */
       for (j = i+1; j < size; j++)
         if (times[ind[j]] < times[ind[i]]) {
           k = ind[i];                  /* sort only the index */
           ind[i] = ind[j];
           ind[j] = k;
         }
     mean = times[ind[size/2]];         /* find mean */
     tol = 0.01*mean;                   /* Set tolorance to 1% of mean */
     printf("Mean time is %lf\n", mean);
     for (i = 0; i < size; i++) {       /* i corresponds to rank */
       diff = times[i] - mean;
       if (diff > tol || diff < -tol)
         printf("%d time %lf\n", i, times[i]);
     }
   }

   MPI_Barrier(MPI_COMM_WORLD);
}
