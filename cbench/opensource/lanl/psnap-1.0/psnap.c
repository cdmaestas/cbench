/* 
 * P-SNAP v1.0 -- PAL System Noise Activity Program -- LA-CC-06-025
 *        <http://www.c3.lanl.gov/pal/software/psnap/>
 *
 * Copyright (C) 2006, The Regents of the University of California
 *
 *                PAL -- Performance and Architecture Laboratory
 *                  <http://www.c3.lanl.gov/pal/>
 *                Los Alamos National Laboratory
 *                  <http://www.lanl.gov/>
 *
 * Unless otherwise indicated, this software has been authored by an
 * employee or employees of the University of California, operator of
 * the Los Alamos National Laboratory under Contract No. W-7405-ENG-36
 * with the U.S.  Department of Energy. The U.S. Government has rights
 * to use, reproduce, and distribute this software. Neither the
 * Government nor the University makes any warranty, express or
 * implied, or assumes any liability or responsibility for the use of
 * this software.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
 * 02110-1301 USA.
 *
 * Contact: Greg Johnson <gjohnson@lanl.gov>
 *
 */

#define VERSION_STR "v1.0"

#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include <math.h>
#include <string.h>

#include <mpi.h>

#ifdef USE_GETTIMEOFDAY
unsigned long get_usecs()
{
	struct timeval tv;
	if(gettimeofday(&tv, NULL) < 0) {
		perror("reading time");
		exit(1);
	}
	return tv.tv_sec*1000000 + tv.tv_usec;
}
#else
unsigned long get_usecs()
{
	return (unsigned long) (MPI_Wtime()*1000000.0);
}
#endif

unsigned long loop(unsigned long count)
{
	unsigned long i;
	volatile unsigned long foo;
	unsigned long usecs_init, usecs_final;

	usecs_init = get_usecs();

	for(i=0; i<count; ++i) 
		foo = i;

	usecs_final = get_usecs();

	return usecs_final - usecs_init;
}

unsigned long calibrate_loop(unsigned long usecs)
{
	unsigned long count = 1000000UL;
	unsigned long min_time_usecs;

	do {
		unsigned long ntrial = 1000UL;
		unsigned long i;

		min_time_usecs = ~0UL;
		for(i=0; i<ntrial; ++i) {
			unsigned long loop_time = loop(count);
			if(loop_time < min_time_usecs) min_time_usecs = loop_time;
		}

		printf("# count = %ld, time = %ld\n", count, min_time_usecs);
		count = count * (double)usecs/min_time_usecs;

	} while((min_time_usecs - usecs > usecs/1000) && (usecs - min_time_usecs > usecs/1000));

	return count;
}

double correlate(unsigned long *r, unsigned long *q, int n)
{
	unsigned long j;
	double  r_ave = 0,  q_ave = 0;
	double r2_ave = 0, q2_ave = 0;
	double rq_ave = 0;
	
	for(j=0; j<n; ++j) {
		r_ave += r[j];
		q_ave += q[j];
		r2_ave += (double)r[j]*r[j];
		q2_ave += (double)q[j]*q[j];
		rq_ave += (double)r[j]*q[j];
	}
	r_ave /= n;
	q_ave /= n;
	r2_ave /= n;
	q2_ave /= n;
	rq_ave /= n;

	return (rq_ave - r_ave*q_ave)/sqrt((r2_ave - r_ave*r_ave)*(q2_ave - q_ave*q_ave));
}

unsigned long maxof(unsigned long *r, unsigned long n)
{
	unsigned long i;
	unsigned long max = 0UL;

	for(i=0; i<n; ++i) {
		if(r[i] > max) max = r[i];
	}

	return max;
}

unsigned long sumof(unsigned long *r, unsigned long n)
{
	unsigned long i;
	unsigned long sum = 0UL;

	for(i=0; i<n; ++i) {
		sum += r[i];
	}

	return sum;
}

void print_banner(void)
{
	printf("########\n");
	printf("# P-SNAP: PAL System Noise Activity Program " VERSION_STR "\n");
	printf("# Copyright 2006\n");
	printf("# http://www.c3.lanl.gov/pal/software/psnap/\n");
	printf("########\n");
}

void usage(void)
{
	fprintf(stderr, 
"Usage: psnap [OPTIONS]\n"
"\n"
"  -n <reps>   number of repetitions\n"
"                default: 100000\n"
"  -w <reps>   number of warm-up repetitions\n"
"                default: 10%% of the number of reps\n"
"  -c <count>  calibration count\n"
"                default: perform a calibration to match granularity\n"
"  -g <usecs>  granularity of the test in microseconds\n"
"                default: 1000\n"
"  -b          perform a barrier between each loop\n"
"                default: no\n"
"  -h          this message\n"
"\n"
"  Example: psnap -n 1000000 -w 10 > psnap.out\n"
"    runs a test with 1000000 repetitions and 10 warm-up reps.\n"
"\n"
);

	exit(1);
}

int main(int argc, char **argv)
{
	unsigned long n = 100000;
	unsigned long w = 1000;
	unsigned long *r, *q = NULL;
	unsigned long i;
	unsigned long count = 0;
	unsigned long localmax, globalmax;
	unsigned long localsum, *sum_all;
	unsigned long *localhist;
	unsigned long granularity = 1000UL;
	double correl;
	double *correl_all = NULL;
	int rank, np;
	int barrier = 0;
	int c;
	char hostname[1024];

	MPI_Init(&argc, &argv);
	MPI_Comm_rank(MPI_COMM_WORLD, &rank);
	MPI_Comm_size(MPI_COMM_WORLD, &np);

	while ((c = getopt (argc, argv, "bn:w:c:g:h")) != -1)
		switch (c) {
			case 'b':
				++barrier;
				break;
			case 'n':
				n = atol(optarg);
				break;
			case 'w':
				w = atol(optarg);
				break;
			case 'c':
				count = atol(optarg);
				break;
			case 'g':
				granularity = atol(optarg);
				break;
			case 'h':
			default:
				usage();
				break;
		}

	memset(hostname, 0, sizeof(hostname));
	gethostname(hostname, sizeof(hostname));
	hostname[sizeof(hostname)-1] = 0;

	r = calloc(n + w, sizeof(unsigned long));
	if(!r) {
		fprintf(stderr, "unable to allocate memory.\n");
		MPI_Abort(MPI_COMM_WORLD, 1);
	}

	q = calloc(n, sizeof(unsigned long));
	if(!q) {
		fprintf(stderr, "unable to allocate memory.\n");
		MPI_Abort(MPI_COMM_WORLD, 1);
	}

	if(rank == 0) {
		print_banner();
		correl_all = calloc(np, sizeof(double));
		if(!correl_all) {
			fprintf(stderr, "unable to allocate memory.\n");
			MPI_Abort(MPI_COMM_WORLD, 1);
		}
		sum_all = calloc(np, sizeof(unsigned long));
		if(!sum_all) {
			fprintf(stderr, "unable to allocate memory.\n");
			MPI_Abort(MPI_COMM_WORLD, 1);
		}
	}

	if(rank == 0 && !count)
		count = calibrate_loop(granularity);

	MPI_Bcast(&count, 1, MPI_UNSIGNED_LONG, 0, MPI_COMM_WORLD);

	/* touch r[] */
	for(i=0; i<n+w; ++i)
		r[i] = 0UL;

	/* measurement loop */
	MPI_Barrier(MPI_COMM_WORLD);
	for(i=0; i<n+w; ++i) {
		r[i] = loop(count);
		if(barrier) MPI_Barrier(MPI_COMM_WORLD);
	}
	MPI_Barrier(MPI_COMM_WORLD);
	r += w;

	localsum = sumof(r, n);
	MPI_Gather(&localsum, 1, MPI_UNSIGNED_LONG, sum_all, 1, MPI_UNSIGNED_LONG, 0, MPI_COMM_WORLD);

	localmax = maxof(r, n);
	MPI_Allreduce(&localmax, &globalmax, 1, MPI_UNSIGNED_LONG, MPI_MAX, MPI_COMM_WORLD);

	localhist = calloc(globalmax + 1, sizeof(unsigned long));
	if(!localhist) {
		fprintf(stderr, "unable to allocate memory.\n");
		MPI_Abort(MPI_COMM_WORLD, 1);
	}

	for(i=0; i<n; ++i) {
		++localhist[r[i]];
	}
	
	/* compute correlations */
	memcpy(q, r, n*sizeof(unsigned long));
	MPI_Bcast(q, n, MPI_UNSIGNED_LONG, 0, MPI_COMM_WORLD);

	correl = correlate(r, q, n);

	MPI_Gather(&correl, 1, MPI_DOUBLE, correl_all, 1, MPI_DOUBLE, 0, MPI_COMM_WORLD);

	if(rank == 0) {
		/* print rank 0's histogram */
		if(n) printf("# %ld %lf %d %s\n", 0, correl_all[0], sum_all[0], hostname);
		for(i=0; i<globalmax; ++i) {
			if(localhist[i]) printf("%d %ld %ld %s\n", rank, i, localhist[i], hostname);
		}
		/* print rank i's histogram */
		for(i=1; i<np; ++i) {
			unsigned long j;
			MPI_Send(NULL, 0, MPI_UNSIGNED_LONG, i, 0, MPI_COMM_WORLD);
			MPI_Recv(localhist, globalmax, MPI_UNSIGNED_LONG, i, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
			MPI_Recv(hostname, sizeof(hostname), MPI_CHAR, i, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
			if(n) printf("# %ld %lf %d %s\n", i, correl_all[i], sum_all[i], hostname);
			for(j=0; j<globalmax; ++j) {
				if(localhist[j]) printf("%ld %ld %ld %s\n", i, j, localhist[j], hostname);
			}
		}
	} else {
		MPI_Recv(NULL, 0, MPI_UNSIGNED_LONG, 0, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
		MPI_Send(localhist, globalmax, MPI_UNSIGNED_LONG, 0, 0, MPI_COMM_WORLD);
		MPI_Send(hostname, sizeof(hostname), MPI_CHAR, 0, 0, MPI_COMM_WORLD);
	}

	MPI_Finalize();
	return 0;
}
