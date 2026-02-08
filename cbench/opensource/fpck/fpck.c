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

#include <stdlib.h>
#include <stdio.h>
#include <malloc.h>
#include <unistd.h>
#include <sys/mman.h>
#include "meminfo.h"
#include <getopt.h>

void usage(void);

#define BLOCKS 3
#define TESTS 20

#define HALF 0.5
#define TWO 2.0

#define MB ((unsigned long)(1<<20))

int main ( int argc, char** argv ) {
  MEMINFO memdata;
  unsigned long headroom = (1UL*MB);
  long memavail, memreq, memincr=65536;
  int k,m,M,i, passm[TESTS+1];
  int dsize=sizeof(double);
  double *A0, *B0, *C0,
         *A , *B , *C ;
  double tempV, trueV, testV;
  int c; double hm;
  char response[12] = {0,};
  int lock_mem = 0;
  int h_used = 0;
  int p_used = 0;
  int c_used = 0;
  long pagesize = 0;
  long totalsize = 0;
  char *byteA0, *byteB0, *byteC0;
  long ceiling = 0;

  /*
   * setenv MALLOC_MMAP_MAX_=0
   * setenv MALLOC_TRIM_THRESHOLD_=-1
   */
     mallopt(M_MMAP_MAX, 0);
  /* mallopt(M_TRIM_THRESHOLD, -1); */

  hm = 1.0;
  while ( (c = getopt(argc,argv,"c:h:pl")) != -1 ) {
    switch (c) {
      case 'c':
        ceiling = strtol(optarg,(char **)NULL,10);
		ceiling *= (1024*1024);
        c_used = 1;
        break;
      case 'h':
        hm = strtod(optarg,(char **)NULL);
        h_used = 1;
        break;
      case 'p':
        p_used = 1;
        break;
      case 'l':
        lock_mem = 1;
        break;
      default:
        return 1;
        break;
    }
  }       

  if ( p_used && h_used ) {
    usage();
  } else if (p_used) {
    printf("\n headroom multiplier?  ");
    scanf("%s",response);
    hm = strtod(response,(char **)NULL);
  }

  /*
   * Query Linux for current memory state and figure out
   * how much memory to consume in testing.
  */
  
  headroom *= hm;

  meminfo(&memdata);

  printf("\nMemory summary");
  printf("\n total      %12lu",memdata.total);
  printf("\n free       %12lu",memdata.free);
  printf("\n shared     %12lu",memdata.shared);
  printf("\n buffers    %12lu",memdata.buffers);
  printf("\n cached     %12lu",memdata.cached);
  printf("\n headroom   %12lu",headroom);

  if (c_used)
    memavail = ceiling - headroom;
  else
    memavail = memdata.free - headroom;

  if (memavail <= 0) {
    printf("\n");
    fprintf(stderr, "Error: headroom > free memory. Exiting...\n");
    return 1;
  }

  printf("\n\nAvailable memory %ld\n",memavail);

  memreq = memavail/(dsize*BLOCKS);

  printf("Allocating %ld bytes (%d blocks of %ld bytes)\n",
  	memavail,BLOCKS,memreq*dsize);

  /*
   * Allocate memory for all the blocks
  */
  A0 = malloc(dsize*memreq);
  printf("\n &A %p",A0);
  if ( A0 == NULL ) { printf("\n"); exit(1); }
  if (lock_mem) {
    if (mlock(A0,dsize*memreq) == -1) {
      perror("mlock A0");
      return -1;
    }
  }

  B0 = malloc(dsize*memreq);
  printf("\n &B %p",B0);
  if ( B0 == NULL ) { printf("\n"); exit(2); }
  if (lock_mem) {
    if (mlock(B0,dsize*memreq) == -1) {
      perror("mlock B0");
      return -1;
    }
  }

  C0 = malloc(dsize*memreq);
  printf("\n &C %p",C0);
  if ( C0 == NULL ) { printf("\n"); exit(3); }
  printf("\n");
  if (lock_mem) {
    if (mlock(C0,dsize*memreq) == -1) {
      perror("mlock C0");
      return -1;
    }
  }

  /*
   * Touch every page in the memory we allocated to force it in
  */
  pagesize = sysconf(_SC_PAGESIZE);
  if ( pagesize == 0 || pagesize == -1 ) {
	fprintf(stderr, "Cannot determine pagesize.  Every byte in array will be touched.\n");
	fflush(stderr);
	pagesize = 1;
  } else if ( pagesize != 4096 ) {
	printf("unusual pagesize (%ld)\n", pagesize);
  }

  /* skip pagesize bytes at a time */
  totalsize = dsize * memreq;
  byteA0 = (char*)A0;
  byteB0 = (char*)B0;
  byteC0 = (char*)C0;
  for( i = 0 ; i < (totalsize) ; i += pagesize ) {
	byteA0[i] = 0xaa;
	byteB0[i] = 0xbb;
	byteC0[i] = 0xcc;
  }

  /*
   * Run the floating point testing algorithm
  */
  M = memreq/memincr;
  for (k=0;k<TESTS+1;k++) passm[k] = M;
  printf("\n Taking %d steps of %ld doubles",M,memincr);
  printf("\n");

  A = A0; B = B0; C= C0;
  for (m=0;m<M;m++) {
    /* -------------------------------------------------------------- test 1 */
    for (k=0;k<memincr;k++) {
      A[k] = (double)(k+1); B[memincr-(k+1)] = A[k];
    }
    for (k=0;k<memincr;k++) {
      C[k] = A[k] + B[k];
    }
    tempV = (double)(1+memincr);
    trueV = (double)0;
    testV = (double)0;
    for (k=0;k<memincr;k++) {
      testV += (C[k]-tempV);
    }
    if (testV != trueV) {
      passm[1] -= 1;
      printf("\n test 1 FAIL at offset %d",m);
      printf(" : %p %p %p",A,B,C);
    }
    /* -------------------------------------------------------------- test 2 */
    for (k=memincr-1;k>0-1;k--) {
      C[k] = A[k] + B[k];
    }
    tempV = (double)(1+memincr);
    trueV = (double)0;
    testV = (double)0;
    for (k=memincr-1;k>0-1;k--) {
      testV += (C[k]-tempV);
    }
    if (testV != trueV) {
      passm[2] -= 1;
      printf("\n test 2 FAIL at offset %d",m);
      printf(" : %p %p %p",A,B,C);
    }
    /* -------------------------------------------------------------- test 3 */
    C[0] = (double)(-1);
    for (k=1;k<memincr;k++) {
      C[k] = -C[k-1];
    }
    if (memincr%2 == 0) {
      trueV = (double)(memincr/2);
    } else {
      trueV = (double)(-(memincr+1)/2);
    }
    testV = (double)0;
    for (k=0;k<memincr;k++) {
       testV += A[k]*C[k];
    }
    if (testV != trueV) {
      passm[3] -= 1;
      printf("\n test 3 FAIL at offset %d",m);
      printf(" : %p %p %p",A,B,C);
    }
    /* -------------------------------------------------------------- test 4 */
    for (k=0;k<memincr;k++) {
      C[k] /= HALF; B[k] /= TWO;
    }
    if (memincr%2 == 0) {
      trueV = (double)(-memincr/2);
    } else {
      trueV = (double)(-(memincr+1)/2);
    }
    testV = (double)0;
    for (k=0;k<memincr;k++) {
       testV += B[k]*C[k];
    }
    if (testV != trueV) {
      passm[4] -= 1;
      printf("\n test 4 FAIL at offset %d",m);
      printf(" : %p %p %p",A,B,C);
      printf("\n testV = %f",testV);
    }
    /* ------------------------------------------------- next memory segment */
    A+=memincr; B+=memincr; C+=memincr;
  }
  printf("\n");

  for (k=1;k<TESTS+1;k++) {
    if (M == passm[k]) {
      printf("\n test %d PASS",k);
    } else {
      printf("\n test %d pass %d",k,passm[k]);
    }
  }
  printf("\n"); printf("\n");

  /*
   * See what Linux thinks memory looks like after all the testing
  */
  meminfo(&memdata);

  printf("\nMemory summary");
  printf("\n total      %12lu",memdata.total);
  printf("\n free       %12lu",memdata.free);
  printf("\n shared     %12lu",memdata.shared);
  printf("\n buffers    %12lu",memdata.buffers);
  printf("\n cached     %12lu",memdata.cached);
  printf("\n");

  /*
   * Clean up
  */
  if (lock_mem) {
    if (mlock(A0,dsize*memreq) == -1) {
      perror("munlock A0");
      return -1;
    }
    if (mlock(B0,dsize*memreq) == -1) {
      perror("munlock B0");
      return -1;
    }
    if (mlock(C0,dsize*memreq) == -1) {
      perror("munlock C0");
      return -1;
    }
  }

  return 0;
}


void
usage(void) {
  fprintf(stderr, "Usage: fpck [-l] [-c <ceiling>] [-p]|[-h <headroom>]\n");
  exit(1);
}
