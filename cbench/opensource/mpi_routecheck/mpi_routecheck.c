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

/*****************************************************************************
 $Id: mpi_routecheck.c,v 1.1 2003/10/13 16:59:09 jbogden Exp $
 
 name:		mpi_routecheck.c

 purpose:	Performs a simple (brute force?) all to all message passing
            pattern between all nodes. It's primary purpose is to 
            test the route and links between all nodes.

 author: 	d. w. doerfler

 parameters:	

 returns:	

 comments:	

 revisions:	
            2006/02/28 - mrepper - added CPU affinity calls to limit execution
                                   to first CPU only (for testing on tbird)
                                   Could definitely be made more generic,
                                   but since the current API isn't generic
                                   I'm not going to bother for now.

*****************************************************************************/

/*
 * To enable the (fairly platform-specific) sched_setaffinity call to limit
 * execution to CPU 0 only.  Still requires a command-line option to enable.
 */
//#define CPUAFFINITY

#include <stdio.h>
#include <stddef.h>
#include <stdlib.h>
#include <getopt.h>
#include <mpi.h>
#undef MCPCHECK
#ifdef MCPCHECK
#include <mcpget.h>
#endif
#include "meminfo.h"
#ifdef CPUAFFINITY
#  define __USE_GNU
#  include <sched.h>
#endif

#define MIN_DATA_XFER   8
#define MAX_DATA_XFER   8192
#define MAX_BURST       16

int data_size[MAX_BURST];
MPI_Status status[MAX_BURST];
MPI_Request request[MAX_BURST];
int mpi_size, my_rank, dealer_node, dest_node;
static void *msg = NULL;
int burst_size = 1;
int burst_index = 0;
long min_data_xfer = MIN_DATA_XFER;
long max_data_xfer = MAX_DATA_XFER;
long interval = 0;
int verbose = 1;
#ifdef CPUAFFINITY
int cpumask = 0;
#endif

/* getopt stuff */
extern char* optarg;
static struct option opts[] = {
    {"verbose",     no_argument,        0,  'v'},
    {"help",        no_argument,        0,  'h'},
    {"usage",       no_argument,        0,  'U'},
#ifdef CPUAFFINITY
    {"cpumask",     no_argument,        0,  'c'}, /* set cpumask via sched_setaffinity */
#endif
    {"interval",    required_argument,  0,  'i'}, /* loop time in seconds */
    {"smin",        required_argument,  0,  's'}, /* min message size */
    {"emax",        required_argument,  0,  'e'}, /* max message size */
    {"msgsize",     required_argument,  0,  'm'}, /* min == max msg size */
    {"burst",       required_argument,  0,  'b'}, /* burst mode and burst size */
    {0, 0, 0, 0}
};


void usage(char *name) {
    if (my_rank == 0) {
        fprintf(stderr, "Usage: %s \n\
  -v verbose\n\
  -interval <loop time in seconds>  default is disabled\n\
  -smin <min_msg_size>  default = %d bytes\n\
  -emax <max_msg_size>  default = %d bytes\n\
  -m msg_size  min == max\n"
#ifdef CPUAFFINITY
  "-cpumask       set cpumask to first CPU\n"
#endif
  "-burst <size>  number of sends to do at once (sort of)\n",
        name, MIN_DATA_XFER, MAX_DATA_XFER);
  
        MPI_Finalize();
        exit(0);
    }
}


int main(int argc, char **argv)
{
    double start;
    double delta;
    int ch = 0;
    int index = 0;
    MEMINFO memdata1;
    MEMINFO memdata2;
    unsigned long long mem_delta1 = 0;
    unsigned long long mem_delta2 = 0;

      
#ifdef MCPCHECK
    mcpshmem_t *mcp_shmem, mcp_state1, mcp_state2;
    int type;
#endif

#ifdef MCPCHECK
    if (!mcpopen(&mcp_shmem, &type))
    {
      printf("Unable to open MCP\n");
      exit(1);
    }
#endif

    /* grab memory stats before MPI is initialized */
    meminfo(&memdata1);

    /**************************************************************
      Initialize transport method
    **************************************************************/
    if ( MPI_Init( &argc, &argv ) != MPI_SUCCESS )
    {
        printf("Unable to initialize MPI\n");
        exit(1);
    }

    MPI_Comm_size( MPI_COMM_WORLD, &mpi_size );
    MPI_Comm_rank( MPI_COMM_WORLD, &my_rank );
    MPI_Barrier( MPI_COMM_WORLD );

    if ( mpi_size == 1 ) {
        printf("This program requires more than 1 process\n");
        MPI_Finalize();
        exit(1);
    }

    if (my_rank == 0  &&  verbose >= 2)
    {
        printf("sizeof(MPI_Status) = %d bytes\n",sizeof(MPI_Status));
        printf("sizeof(MPI_Request) = %d bytes\n",sizeof(MPI_Request));
    }

    /**************************************************************
      Parse the Command Args
    **************************************************************/
    while ((ch = getopt_long_only(argc, argv, "", opts, &index)) != EOF) {
        switch (ch) {
            case 'v':
                verbose++;
                break;
            case 'h':
            case 'U':
                usage(argv[0]);
                break;
            case 'i':
                interval = strtol(optarg, (char**)NULL, 10);
                break;
            case 'b':
                burst_size = strtol(optarg, (char**)NULL, 10);
                if (my_rank == 0)
                    printf("BURST MODE: size = %d\n",burst_size);
                break;
            case 's':
                min_data_xfer = strtol(optarg, (char**)NULL, 10);
                break;
            case 'e':
                max_data_xfer = strtol(optarg, (char**)NULL, 10);
                break;
            case 'm':
                min_data_xfer = max_data_xfer = strtol(optarg, (char**)NULL, 10);
                break;
#ifdef CPUAFFINITY
            case 'c':
                cpumask = 1;
                break;
#endif
            default:
                usage(argv[0]);
        }
    }

#ifdef CPUAFFINITY
    /**************************************************************
      Set cpu affinity (this API is platform-dependent, sorry
      if it breaks, but you can undef CPUAFFINITY above)
    **************************************************************/
    if (cpumask) {
        cpu_set_t mask;

        CPU_ZERO(&mask);        /* clear all CPUs */
        CPU_SET(0, &mask);      /* add first CPU (0) to the set */

        if ( my_rank == 0 )
            printf("Setting affinity to CPU 0\n");

        if ( sched_setaffinity(0, sizeof(mask), &mask) ) {
            perror("sched_setaffinity");
            exit(1);
        }

        //if ( my_rank == 0 ) {
        //    sched_getaffinity(0, sizeof(mask), &mask);
        //    ... do some magic ...
        //    printf("CPU affinity is now 0x%x\n", ...);
        //}
    }
#endif
    
    /**************************************************************
      Allocate message
    **************************************************************/
    if (msg == NULL)
    {
        if ((msg = malloc(max_data_xfer)) == NULL)
        {
            printf("Unable to allocate %d bytes of memory\n",max_data_xfer);
            exit(1);
        }
    }

    /**************************************************************
      Announce parameters
    **************************************************************/
    if (my_rank == 0)
    {
        printf("Timing resolution is %f seconds\n", (float)MPI_Wtick());
        if (min_data_xfer == max_data_xfer)
          printf("Message size = %d bytes\n", min_data_xfer);
        else
          printf("Min msg = %d bytes, Max = %d bytes\n", 
          min_data_xfer, max_data_xfer);

        fflush(stdout);
    }

    /**************************************************************
      Loop through using every node as a dealer node
    **************************************************************/
    start = MPI_Wtime();
    do 
    {
    for (dealer_node = 0; dealer_node < mpi_size; dealer_node++)
    {
      if (my_rank == dealer_node)
      {
        if (verbose)
        {
          printf("dealer node is now rank %d\n",dealer_node);            
          fflush(stdout);
        }

        for (dest_node = 0; dest_node < mpi_size; ++dest_node)
        {
          if (dest_node == dealer_node) continue;

#ifdef MCPCHECK
          mcpget(mcp_shmem, &mcp_state1, &type);
#endif

          /**************************************************************
            Loop through different data sizes
          **************************************************************/
          data_size[0] = min_data_xfer;
          do
          {
            for (burst_index=0; burst_index < burst_size; burst_index++)
            {
              if (MPI_Irecv( msg,
                             max_data_xfer,
                             MPI_BYTE,
                             dest_node,
                             1,
                             MPI_COMM_WORLD,
                             &request[burst_index] ) != MPI_SUCCESS )
              {
                printf("Error posting return message\n");
                break;
              }
            }

            if (verbose >= 2)
              printf("Sending to node %d of size %d\n", dest_node, data_size[0]);

            for (burst_index=0; burst_index < burst_size; burst_index++)
            {
              if ( MPI_Send( msg,
	                     data_size[0],
	                     MPI_BYTE,
	                     dest_node,
	                     1,
	                     MPI_COMM_WORLD ) != MPI_SUCCESS )
              {
                printf("Unable to send message\n");
                break;
              }
            }

            for (burst_index=0; burst_index < burst_size; burst_index++)
            {
              MPI_Wait(&request[burst_index],&status[burst_index]);
            }

            if (verbose >= 2)
              printf("Received confirmation from node %d\n", dest_node);

            data_size[0] *= 2;
          } while( data_size[0] <= max_data_xfer );
#ifdef MCPCHECK
          mcpget(mcp_shmem, &mcp_state2, &type);
          {
            char buf[80];
            sprintf(buf, "snd: ranks %d <-> %d", my_rank, dest_node);
            mcpcmp(&mcp_state1, &mcp_state2, &type, buf);
	    fflush(stdout);
          }
#endif
        }

        /* send kill message to slave node */
        for (dest_node = 0; dest_node < mpi_size; ++dest_node)
        {
          if (dest_node == dealer_node) continue;

          if ( MPI_Send( NULL,
                         0,
	                 MPI_BYTE,
		         dest_node,
		         1,
		         MPI_COMM_WORLD ) != MPI_SUCCESS )
          {
            printf("Unable to send KILL message to node %d\n", dest_node);
          }
        }

        if (verbose >= 2)
          printf("dealer node %d done\n", my_rank);

      } /* end of dealer node */

      /**************************************************************
        Slave node
      **************************************************************/
      else
      {
        if (verbose >= 2)
          printf("I am node %d and I am a slave\n", my_rank);

#ifdef MCPCHECK
        mcpget(mcp_shmem, &mcp_state1, &type);
#endif



        /* Process all the incoming burst data */
        memset(data_size,0,sizeof(data_size));
        for (burst_index=0; burst_index < burst_size; burst_index++)
        {

          /* receive data */
          if (MPI_Irecv( msg,
                         max_data_xfer,
                         MPI_BYTE,
                         MPI_ANY_SOURCE,
                         1,
                         MPI_COMM_WORLD,
                         &request[burst_index]) != MPI_SUCCESS )
          {
             printf("Error receiving message data\n");
             break;
          }
        }

        if (verbose >= 2)
          printf("Node %d posted all burst receives\n",my_rank);

        for (burst_index=0; burst_index < burst_size; burst_index++)
        {

          MPI_Wait(&request[burst_index], &status[burst_index]);
          MPI_Get_count(&status[burst_index], MPI_BYTE, &data_size[burst_index]);

          /* send data back */
          if (data_size[burst_index] != 0)
          {
            if ( MPI_Send( msg,
                           data_size[burst_index],
	                   MPI_BYTE,
	                   status[burst_index].MPI_SOURCE,
	                   1,
	                   MPI_COMM_WORLD ) != MPI_SUCCESS )
            {
              printf("Unable to send return data\n");
            }
          }
        } 

        if (verbose >= 2)
          printf("Node %d finished receiving burst data\n",my_rank);

        /* Process any remaining incoming packets including the kill packet */
        do 
        {
          memset(data_size,0,sizeof(data_size));
          burst_index = 0;

          /* receive data */
          if (MPI_Irecv( msg,
                         max_data_xfer,
                         MPI_BYTE,
                         MPI_ANY_SOURCE,
                         1,
                         MPI_COMM_WORLD,
                         &request[burst_index]) != MPI_SUCCESS )
          {
             printf("Error receiving message data\n");
             break;
          }

          MPI_Wait(&request[burst_index], &status[burst_index]);
          MPI_Get_count(&status[burst_index], MPI_BYTE, &data_size[burst_index]);

          /* send data back */
          if (data_size[burst_index] != 0)
          {
            if ( MPI_Send( msg,
                           data_size[burst_index],
	                   MPI_BYTE,
	                   status[burst_index].MPI_SOURCE,
	                   1,
	                   MPI_COMM_WORLD ) != MPI_SUCCESS )
            {
              printf("Unable to send return data\n");
            }
          }

        } while (data_size[burst_index] != 0);

#ifdef MCPCHECK
	    mcpget(mcp_shmem, &mcp_state2, &type);
	    {
	      char buf[80];
	      sprintf(buf, "rcv: ranks %d <-> %d", status.MPI_SOURCE, my_rank);
	      mcpcmp(&mcp_state1, &mcp_state2, &type, buf);
	      fflush(stdout);
	    }
#endif

        if (verbose >= 2)
          printf("Slave node %d done\n", my_rank);

      } /* end of slave node */

      if (my_rank == 0)
      {
        if (interval)
        {
          if ((MPI_Wtime() - start) > (double)interval)
	  {
	    printf("Aborting due to time interval expiration\n");
	    MPI_Abort(MPI_COMM_WORLD, 0);
          }
        }
      }

    } /* end of looping through dealer nodes */

    } while (interval);

    delta = MPI_Wtime() - start;
    if (my_rank == 0)
    {
      printf("Total time = %lf\n", delta);
      printf("Avg loop time = %lf\n", delta / mpi_size);
    }

    meminfo(&memdata2);

    mem_delta1 = (memdata1.free - memdata2.free) / 1024;

    if (my_rank == 0) {
        printf("Rank %d: mem used by MPI = %llu kB\n",
	    my_rank, mem_delta1);
        fflush(stdout);
    }

    if (verbose >= 2)
      printf("Node %d calling finalize\n", my_rank);

    MPI_Finalize();
    free (msg);
    exit(0);
}
