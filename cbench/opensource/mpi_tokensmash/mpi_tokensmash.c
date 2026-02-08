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
 *
 * mpi_tokensmash.c
 *
 * Jeff Ogden
 *
 * The original idea of this test is to mimic the communication stress that CTH 
 * puts on the Cplant communication layers. The test I hope will controllably
 * exercise regular asynchronous communication patterns with multiple
 * sends and receives in flight at any given time depending on the number
 * of tokens.  The intent is to stress out the dealer nodes while the
 * edge nodes should just be pre-posting receives with appropriate tags
 * and bouncing messages back to the dealer.
*/

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include "mpi.h"

/* defines for the layout of the MPI tags used */
#define MPI_TAG_BITS        0x0000ffff
#define DEALER_ID           0x0000ff00
#define TOKEN_ID            0x000000ff
#define DEALER_ID_SHIFT     8
#define GENERIC_TAG         0x000a0000
#define CTRL_WORD_TAG       0x000b0000
#define STATS_TAG           0x000c0000

/* token_obj_t defines */
#define TAG_IDLE            0
#define TAG_RUNNING         1
#define TAG_FINISHED        2

/* ctrl_word defines */
#define CTRL_SHUTDOWN       0xdeaddead
#define CTRL_DEALER_DONE    0x99999999
#define DEALER_RUNNING      1
#define DEALER_DONE         2

/* defines for the layout of the role-dealer 32-bit value */
#define DEALER              1
#define EDGE                2
#define DEALER_EDGE         3

/* size defines */
#define KBYTE                       1024LU
#define MB_STRING                   "MB"
#define MEGABYTE                    (KBYTE * 1024)
#define GB_STRING                   "GB"
#define GIGABYTE                    (MEGABYTE * 1024)
#ifdef __i386__
#define TERABYTE                    (GIGABYTE)
#define TB_STRING                   "GB"
#else
#define TERABYTE                    (GIGABYTE * 1024)
#define TB_STRING                   "TB"
#endif

/* misc config defines */
#define SHORT_TO_LONG_MSG_RATIO     0.20
#define MAX_LONG_MSG_SIZE           (KBYTE * 256)
#define MIN_LONG_MSG_SIZE           9000
#define MAX_SHORT_MSG_SIZE          8000
#define MIN_SHORT_MSG_SIZE          4
#define SHORT_MSG_FACTOR            8
#define LONG_MSG_FACTOR             2
#define TRUE                        1
#define FALSE                       0
#define REPORT_PERIOD               4
#define CTRL_PERIOD                 5.0    /* in seconds */
#define INTEGRITY_PERIOD            10     /* in cycles */
#define STATS_PERIOD                60.0  /* in seconds */
#define STATS_REPORT_PERIOD         70.0   /* in seconds */
#define DEFAULT_MPI_CALL_SCHEME     1
#define MAX_MPI_CALL_SCHEME         2


typedef enum {STAR,MESH_2D,MESH_3D} topology_t;

/* typedefs and structures */
typedef struct {
    int tag;
    unsigned int start_edge;
    unsigned int current_edge;
    unsigned int last_edge;
    unsigned int cycles;        /* number of times the token has been passed around */
    double last_cycle_start;
    double tot_cycle_time;
    double ave_cycle_time;
    double velocity;
    unsigned int status;
    void *buf;
} token_obj_t;

typedef struct {
    unsigned int status;
    int tag;
    MPI_Status mpi_status;
    MPI_Request *mpi_request;
    MPI_Request *send_mpi_request;
	unsigned int send_request_active;
    void *buf;
} tag_recv_t;

typedef struct {
    unsigned int role;
    unsigned int dealer;
    unsigned int num_edges;
    unsigned int *edges;
    tag_recv_t *recv_queue;
} role_t;

typedef struct {
    double num_isends;
    double num_irecvs;
    double num_mpi_test;
    double total_bytes_sent;
    double total_bytes_recv;
    double integrity_errors;
    double total_bad_bytes;
    double start_time;
    double current_time;
    double end_time;
    double time;
    unsigned long tokens_dealt;
    unsigned long tokens_bounced;
} stats_t;

typedef struct {
    unsigned long ctrl_word;
    MPI_Request mpi_request;
    MPI_Status mpi_status;
    unsigned int status;
    MPI_Request stats_mpi_request; 
} dealer_ctrl_t;

/* getopt related variables */
int ch;
extern char *optarg;
extern int optind;

/* local variables */
unsigned int verbose = 0;
unsigned int count = REPORT_PERIOD;    /* number of times a token is passed */
long walltime = -1;
unsigned int tokens = 2;
unsigned int tokens_finished = 0;
unsigned int integrity_period = INTEGRITY_PERIOD;
double stats_period = STATS_PERIOD;
double stats_report_period = STATS_REPORT_PERIOD;
int stats_size = 1;
unsigned long max_long_msg_size = MAX_LONG_MSG_SIZE;
unsigned long uniform_msg_size = 0;
float short_to_long_msg_ratio = SHORT_TO_LONG_MSG_RATIO;
unsigned int mpi_call_scheme = DEFAULT_MPI_CALL_SCHEME;
unsigned int integrity_check = 2;
topology_t topology = STAR;
unsigned int xsize = 0;
unsigned int ysize = 0;
unsigned int zsize = 0;
int mpi_size;
int my_rank;
unsigned long *token_len = NULL;
token_obj_t *token_obj = NULL;
unsigned int num_roles = 0;
role_t *roles = NULL;
MPI_Request *mpi_request_array = NULL;
unsigned int num_mpi_requests = 0;
unsigned int mpi_request_index = 0;
int completion_flag;
int completion_flag2;
int recv_bytes;
int main_loop_exit = FALSE;
unsigned int dealers_finished = 0;
double last_ctrl_coord_time = 0.0;
double last_stats_time = 0.0;
double last_stats_report_time = 0.0;
unsigned long ctrl_word;
unsigned long ctrl_word_send;
unsigned long ctrl_status;
dealer_ctrl_t *dealer_ctrl = NULL;
MPI_Request ctrl_request;
MPI_Status ctrl_mpi_status;
MPI_Request stats_mpi_request;
unsigned int stats_mpi_request_active = 0;
MPI_Status stats_mpi_status;
stats_t stats;
stats_t overall_stats;
stats_t *allstats = NULL;

/* forward declarations */
void final_cleanup(int retcode);
void send_recv_buf_init(void);
void token_len_init(void);
void topology_roles_init(void);
void usage(char *name);
int xminus(int rank);
int xplus(int rank);
int yminus(int rank);
int yplus(int rank);
int zminus(int rank);
int zplus(int rank);



/*********************************************************************
*   final_cleanup()
*
*/
void final_cleanup(int retcode) {
    int i;
    int j;
    
    if (verbose > 1)
        printf("%d: Doing final_cleanup()\n",my_rank);
        
    if (token_len != NULL)
        free(token_len);

    if (token_obj != NULL) {
        for (j=0; j<tokens; j++) {
            if (token_obj[j].buf != NULL)
                free(token_obj[j].buf);
        }
        free(token_obj);
    }
    
    if (roles != NULL) {
        for (i=0; i<num_roles; i++) {
            if (roles[i].recv_queue != NULL) {
                for (j=0; j<tokens; j++) {
                    if (roles[i].recv_queue[j].buf != NULL)
                        free(roles[i].recv_queue[j].buf);
                }
                free(roles[i].recv_queue);
            }
            
            if (roles[i].edges != NULL) {
                free(roles[i].edges);
            }
        }
        free(roles);
    }
    
    if (dealer_ctrl != NULL)
        free(dealer_ctrl);

    if (allstats != NULL)
        free(allstats);
            
    if (retcode != 0) {
        if (verbose > 1)
            printf("%d: final_cleanup() error exit with code = %d\n",
                   my_rank,retcode);
        MPI_Finalize();
        exit(retcode);
    }
}


/*********************************************************************
*   send_recv_buf_init()
*
*   Everybody needs to allocate the required send and receive buffers. 
*   The dealer nodes need to init their token objects (token_obj_t)
*   first. Then all will prepost their receives. Then the dealers will
*   start their initial sends of all tokens.
*/
void send_recv_buf_init(void) {

    int rc;    
    int i;
    int j;
    int k;
    int current_edge;
    unsigned char *ptr_uchar = NULL;
    
    for (i=0; i<num_roles; i++) {
        if (roles[i].role == DEALER) {
        
            /* allocate our MPI communication buffers */
            for (j=0; j<tokens; j++) {
                roles[i].recv_queue[j].buf = NULL;
                roles[i].recv_queue[j].buf = calloc(token_len[j],1);
                if (roles[i].recv_queue[j].buf == NULL) {
                    printf("%d: Error calloc()ing roles[%d].recv_queue[%d].buf\n",my_rank,i,j);
                    MPI_Abort(MPI_COMM_WORLD,-7);
                    final_cleanup(-7);
                }
                
                if (verbose > 1)
                    printf("%d: Allocated %lu bytes for roles[%d].recv_queue[%d].buf\n",
                           my_rank,token_len[j],i,j);
            }
            
            if (verbose > 1)
                printf("%d: Allocated MPI recv buffers\n",my_rank);
                
            /* allocate the token object array */
            token_obj = (token_obj_t*)calloc(tokens,sizeof(token_obj_t));
            if (token_obj == NULL) {
                printf("%d: Error calloc()ing token_obj\n",my_rank);
                MPI_Abort(MPI_COMM_WORLD,-8);
                final_cleanup(-8);
            }
            
            if (verbose > 1)
                printf("%d: Allocated token object array\n",my_rank);

            current_edge = 0;                
            
            /* init our token objects and then prepost recieves for them */
            for (j=0; j<tokens; j++) {
                token_obj[j].tag = (my_rank << DEALER_ID_SHIFT) | (j+1);
                token_obj[j].cycles = -1; /* because first receive isn't a completed trip */
                token_obj[j].status = TAG_IDLE;
                token_obj[j].last_cycle_start = 0.0;
                token_obj[j].tot_cycle_time = 0.0;
                token_obj[j].ave_cycle_time = 0.0;

                /* allocate the send buffer for the token */
                token_obj[j].buf = NULL;
                token_obj[j].buf = calloc(token_len[j],1);
                if (token_obj[j].buf == NULL) {
                    printf("%d: Error calloc()ing token_obj[%d].buf\n",my_rank,j);
                    MPI_Abort(MPI_COMM_WORLD,-9);
                    final_cleanup(-9);
                }
                
                /* fill the send buffer with some data we can check later */
                ptr_uchar = (unsigned char*)token_obj[j].buf;
                for (k=0; k<token_len[j]; k++) {
                    ptr_uchar[k] = k % 256;
                }

                if (verbose > 1) {
                    printf("%d: Initialized token_obj[%d] with tag %08x\n",my_rank,j,token_obj[j].tag);
                    /*printf("%d: roles[%d].edges = %p\n",my_rank,i,roles[i].edges);
                    printf("%d: current_edge = %d  rank = %d\n",my_rank,current_edge,
                           roles[i].edges[current_edge]);*/
                }

                /* pre-post a receive for this token */
                rc = MPI_Irecv(roles[i].recv_queue[j].buf,
                               token_len[j],
                               MPI_BYTE,
                               roles[i].edges[current_edge],
                               token_obj[j].tag,
                               MPI_COMM_WORLD,
                               roles[i].recv_queue[j].mpi_request);
                               
                if (rc != MPI_SUCCESS) {
                    printf("%d: MPI_Irecv failed for tag %08x from edge %d (rank %d)\n",
                           my_rank,token_obj[j].tag,current_edge,roles[i].edges[current_edge]);
                    MPI_Abort(MPI_COMM_WORLD,-10);
                    final_cleanup(-11);
                }
                stats.num_irecvs++;
                
                token_obj[j].start_edge = current_edge;
                token_obj[j].current_edge = current_edge;
                token_obj[j].last_edge = current_edge;
                
                if (verbose > 1)
                    printf("%d: Pre-posted recv for tag %08x from edge %d (rank %d)\n",
                           my_rank,token_obj[j].tag,current_edge,roles[i].edges[current_edge]);
                
                current_edge = (current_edge + 1) % roles[i].num_edges;
                
                if (verbose > 1)
                    printf("%d: current_edge = %d (rank %d)\n",my_rank,
                           current_edge,roles[i].edges[current_edge]);
            }
            
            if (verbose > 1)
                printf("%d: Allocated token objects and pre-posted receives\n",my_rank);
        }
        else if (roles[i].role == EDGE) {

            /* allocate our MPI communication buffers */
            for (j=0; j<tokens; j++) {
                roles[i].recv_queue[j].buf = NULL;
                roles[i].recv_queue[j].buf = calloc(token_len[j],1);
                if (roles[i].recv_queue[j].buf == NULL) {
                    printf("%d: Error calloc()ing roles[%d].recv_queue[%d].buf\n",my_rank,i,j);
                    MPI_Abort(MPI_COMM_WORLD,-7);
                    final_cleanup(-7);
                }
                
                if (verbose > 1)
                    printf("%d: Allocated %lu bytes for roles[%d].recv_queue[%d].buf\n",
                           my_rank,token_len[j],i,j);

                /* pre-post a receive for this token from the appropriate dealer */
                rc = MPI_Irecv(roles[i].recv_queue[j].buf,
                               token_len[j],
                               MPI_BYTE,
                               roles[i].dealer,
                               roles[i].recv_queue[j].tag,
                               MPI_COMM_WORLD,
                               roles[i].recv_queue[j].mpi_request);

                if (rc != MPI_SUCCESS) {
                    printf("%d: MPI_Irecv failed for tag %08x from dealer %d\n",
                           my_rank,roles[i].recv_queue[j].tag,roles[i].dealer);
                    MPI_Abort(MPI_COMM_WORLD,-10);
                    final_cleanup(-10);
                }
                stats.num_irecvs++;

                if (verbose > 1)
                    printf("%d: Pre-posted recv for tag %08x from rank %d\n",
                           my_rank,roles[i].recv_queue[j].tag,roles[i].dealer);
            }
            
            if (verbose > 1)
                printf("%d: Allocated MPI recv buffers and pre-posted recvs\n",my_rank);
        }
    }
}


/*********************************************************************
*   token_len_init()
*
*   Each token ID (i.e. 1,2,3,4) has a static message length.
*   Here we determine the message length for each token
*   ID based on the short-to-long message ratio.
*
*/
void token_len_init(void) {

    int num_short;
    float temp_float;
    unsigned long short_msg_size;
    unsigned long long_msg_size;
    unsigned long short_msg_increment;
    unsigned long long_msg_increment;
    int i;
    int rc;

    token_len = (unsigned long *)calloc(tokens,sizeof(unsigned long));
    if (token_len == NULL) {
        printf("%d: token_len calloc() failed!\n",my_rank);
        MPI_Abort(MPI_COMM_WORLD,-1);
        final_cleanup(-1);
    }

    if (my_rank == 0) {
        temp_float = (float)tokens * short_to_long_msg_ratio;
        num_short = (int)temp_float;
        short_msg_size = MIN_SHORT_MSG_SIZE;
        long_msg_size = MIN_LONG_MSG_SIZE;
        
        /* distribute the token lengths evenly through the range
         * of short and long token sizes.
        */
        if (num_short >= 1)
            short_msg_increment = (MAX_SHORT_MSG_SIZE - MIN_SHORT_MSG_SIZE)/num_short - 1;
        long_msg_increment = (max_long_msg_size - MIN_LONG_MSG_SIZE)/(tokens - num_short - 1);
        
        if (verbose > 1)
            printf("%d: short_msg_increment = %ld long_msg_increment = %ld\n",
                   my_rank,short_msg_increment,long_msg_increment);
               
        for (i=0; i<tokens; i++) {
            if (uniform_msg_size != 0) {
                token_len[i] = uniform_msg_size;
            }
            else if (i < num_short) {
                /* short messages should fit in one rtscts packet,
                 * so about 8000 bytes is the max
                */
                token_len[i] = short_msg_size;
                short_msg_size += short_msg_increment;
                if (short_msg_size > MAX_SHORT_MSG_SIZE)
                    short_msg_size = MIN_SHORT_MSG_SIZE;
                
                if (verbose > 1)
                    printf("%d: short token_len[%d] = %lu\n",my_rank,i,token_len[i]);
            }
            else {
                /* long messages are > ~8K and < the max message size */
                token_len[i] = long_msg_size;
                long_msg_size += long_msg_increment;
                if (long_msg_size > max_long_msg_size)
                    long_msg_size = MIN_LONG_MSG_SIZE;
                
                if (verbose > 1)
                    printf("%d: long token_len[%d] = %lu\n",my_rank,i,token_len[i]);
            }
        }
    }

    /* send token_len to everyone */
    rc = MPI_Bcast((void*)token_len,tokens,MPI_UNSIGNED_LONG,0,MPI_COMM_WORLD);
    if (rc != MPI_SUCCESS) {
        printf("%d: MPI_Bcast of token_len failed!\n",
               my_rank);
        MPI_Abort(MPI_COMM_WORLD,-2);
        final_cleanup(-2);        
    }
}


/*********************************************************************
*   topology_roles_init()
*
*   Init all the topology related variables and data structures and
*   then init the roles data structures accordingly so everybody knows
*   what their job is.
*
*/
void topology_roles_init(void) {
    
    int i;
    int j;
    
    if (topology == STAR) {
        /* This is the easy case. Rank 0 is the dealer and the
         * rest are the edges.
        */
        num_roles = 1;

        roles = (role_t*)calloc(num_roles,sizeof(role_t));
        if (roles == NULL) {
            printf("%d: Error calloc()ing roles array!\n",my_rank);
            MPI_Abort(MPI_COMM_WORLD,-5);
            final_cleanup(-5);
        }

        if (my_rank == 0) {
            roles[0].role = DEALER;
            roles[0].dealer = my_rank;
            roles[0].num_edges = mpi_size - 1;
            roles[0].edges = NULL;
            roles[0].recv_queue = NULL;
            
        }
        else {
            roles[0].role = EDGE;
            roles[0].dealer = 0;
            roles[0].num_edges = 0;
            roles[0].edges = NULL;
            roles[0].recv_queue = NULL;        
        }

        roles[0].edges = (unsigned int*)calloc(roles[0].num_edges,sizeof(unsigned int));
        if (roles[0].edges == NULL) {
            printf("%d: Error calloc()ing roles[0].edges array!\n",my_rank);
            MPI_Abort(MPI_COMM_WORLD,-4);
            final_cleanup(-4);
        }

        for (j=0; j<roles[0].num_edges; j++) {
            roles[0].edges[j] = j+1;
        }
    }
    else if (topology == MESH_2D) {
        /* We are using a toroid 2d mesh. So each node is a dealer and an edge
         * to the nodes (and their dealer role) to the north, south, east, and
         * west.
        */
        num_roles = 5;

        roles = (role_t*)calloc(num_roles,sizeof(role_t));
        if (roles == NULL) {
            printf("%d: Error calloc()ing roles array!\n",my_rank);
            MPI_Abort(MPI_COMM_WORLD,-5);
            final_cleanup(-5);
        }

        /* the first role will be the dealer role for all nodes */
        roles[0].role = DEALER;
        roles[0].dealer = my_rank;
        roles[0].num_edges = 4;
        roles[0].edges = NULL;
        roles[0].recv_queue = NULL;

        roles[0].edges = (unsigned int*)calloc(roles[0].num_edges,sizeof(unsigned int));
        if (roles[0].edges == NULL) {
            printf("%d: Error calloc()ing roles[0].edges array!\n",my_rank);
            MPI_Abort(MPI_COMM_WORLD,-4);
            final_cleanup(-4);
        }

        roles[0].edges[0] = xplus(my_rank);
        roles[0].edges[1] = xminus(my_rank);
        roles[0].edges[2] = yplus(my_rank);
        roles[0].edges[3] = yminus(my_rank);
        
        
        for (i=1; i<5; i++) {
            roles[i].role = EDGE;
            roles[i].num_edges = 0;
            roles[i].edges = NULL;
            roles[i].recv_queue = NULL;            
        }
        
        roles[1].dealer = xplus(my_rank);
        roles[2].dealer = xminus(my_rank);
        roles[3].dealer = yplus(my_rank);
        roles[4].dealer = yminus(my_rank);
    }
    else if (topology == MESH_3D) {
        /* We are using a toroid 3d mesh. So each node is a dealer and an edge
         * to the nodes (and their dealer role) to the north, south, east, 
         * west, up, and down.
        */
        num_roles = 7;

        roles = (role_t*)calloc(num_roles,sizeof(role_t));
        if (roles == NULL) {
            printf("%d: Error calloc()ing roles array!\n",my_rank);
            MPI_Abort(MPI_COMM_WORLD,-5);
            final_cleanup(-5);
        }

        /* the first role will be the dealer role for all nodes */
        roles[0].role = DEALER;
        roles[0].dealer = my_rank;
        roles[0].num_edges = 6;
        roles[0].edges = NULL;
        roles[0].recv_queue = NULL;

        roles[0].edges = (unsigned int*)calloc(roles[0].num_edges,sizeof(unsigned int));
        if (roles[0].edges == NULL) {
            printf("%d: Error calloc()ing roles[0].edges array!\n",my_rank);
            MPI_Abort(MPI_COMM_WORLD,-4);
            final_cleanup(-4);
        }

        roles[0].edges[0] = xplus(my_rank);
        roles[0].edges[1] = xminus(my_rank);
        roles[0].edges[2] = yplus(my_rank);
        roles[0].edges[3] = yminus(my_rank);
        roles[0].edges[4] = zplus(my_rank);
        roles[0].edges[5] = zminus(my_rank);
        
        
        for (i=1; i<7; i++) {
            roles[i].role = EDGE;
            roles[i].num_edges = 0;
            roles[i].edges = NULL;
            roles[i].recv_queue = NULL;            
        }
        
        roles[1].dealer = xplus(my_rank);
        roles[2].dealer = xminus(my_rank);
        roles[3].dealer = yplus(my_rank);
        roles[4].dealer = yminus(my_rank);
        roles[5].dealer = zplus(my_rank);
        roles[6].dealer = zminus(my_rank);
    }
    
    /* do the rest of the roles initializing which can be done generically */
    for (i=0; i<num_roles; i++) {
        roles[i].recv_queue = (tag_recv_t*)calloc(tokens,sizeof(tag_recv_t));
        if (roles[i].recv_queue == NULL) {
            printf("%d: Couldn't calloc() recv_queue stuff!\n",
                   my_rank);
            MPI_Abort(MPI_COMM_WORLD,-6);
            final_cleanup(-6);                    
        }

        /* init the tags, this has to be done per dealer so
         * there is num_dealers*tokens tags to setup and associated recv queues
        */
        for (j=0; j<tokens; j++) {
            roles[i].recv_queue[j].tag = (roles[i].dealer << DEALER_ID_SHIFT) | (j+1);
            if (verbose > 1)
                printf("%d: roles[%d].recv_queue[%d].tag = %08x\n",my_rank,i,j,roles[i].recv_queue[j].tag);

            roles[i].recv_queue[j].mpi_request = &mpi_request_array[mpi_request_index++];
            roles[i].recv_queue[j].send_mpi_request = &mpi_request_array[mpi_request_index++];
            roles[i].recv_queue[j].send_request_active = 0;

            if (mpi_request_index == num_mpi_requests) {
                if (verbose > 1)
                    printf("%d: Mpi_requests used up, max=%d curr=%d\n",
                            my_rank,num_mpi_requests,mpi_request_index);
            }
            else if (mpi_request_index == num_mpi_requests) {
                printf("%d: Too many mpi_requests used, max=%d curr=%d\n",
                       my_rank,num_mpi_requests,mpi_request_index);
                MPI_Abort(MPI_COMM_WORLD,-27);
                final_cleanup(-27);
            }
        }
    }
    
}


/*********************************************************************
*   usage()
*
*/
void usage(char *name)
{
    if (my_rank == 0) {
        printf("Usage: %s\n",name);
        printf("    -v  verbose\n");
        printf("    -c <count>  number of times tokens are passed\n");
        printf("    -w <walltime in minutes> run until walltime has elapsed, ignore count\n");
        printf("    -t <num tokens>\n");
        printf("    -p <time in seconds> progress/stats update period\n");
        printf("    -m <max msg size in bytes>\n");
        printf("    -u <msg size in bytes> uniform message size\n");
        printf("    -r <%% short messages, i.e. 20=20%%> ratio of short to long msgs\n");
        printf("    -i <0,1,2> integrity check\n");
        printf("        0 = no checking\n");
        printf("        1 = dealer checks token buffer upon recv\n");
        printf("        2 = dealer checks token buffer after several cycles (default)\n");
        printf("    -s <0,1,2> mpi non-blocking calling scheme\n");
        printf("        0 = ISend + MPI_Request_Free per send request\n");
        printf("        1 = ISend + MPI_Test per send request after token bounce (default)\n");
        printf("        2 = ISend + MPI_Test per token every loop\n");
        /*printf("        3 = ISend + MPI_Waitany for all send/recv requests\n");*/
        printf("    -x <num> number of X planes in the logical mesh\n");
        printf("    -y <num> number of Y planes in the logical mesh\n");
        printf("    -z <num> number of Z planes in the logical mesh (implies 3D mesh mode)\n");
    }

    MPI_Finalize();
    exit(0);
}


/*********************************************************************
*   xminus()
*
*/
int xminus(int rank) {
    int xnorm;
    int xminus;
    
    xnorm = rank - ((rank/xsize)*xsize);
    if (xnorm == 0) {
        xminus = rank + (xsize - 1);
    }
    else if (xnorm == (xsize-1)) {
        xminus = rank - 1;
    }
    else {
        xminus = rank - 1;
    }
    return xminus;
}


/*********************************************************************
*   xplus()
*
*/
int xplus(int rank) {
    int xnorm;
    int xplus;
    
    xnorm = rank - ((rank/xsize)*xsize);
    if (xnorm == 0) {
        xplus = rank + 1;
    }
    else if (xnorm == (xsize-1)) {
        xplus = rank - (xsize - 1);
    }
    else {
        xplus = rank + 1;
    }
    return xplus;
}


/*********************************************************************
*   yplus()
*
*/
int yplus(int rank) {
    int znorm;
    
    znorm = rank/(xsize*ysize);
    return ( ((rank + xsize) % (xsize*ysize)) + (znorm*(xsize*ysize)) );
}


/*********************************************************************
*   yminus()
*
*/
int yminus(int rank) {
    int yminus;
    int znorm;
    
    znorm = rank/(xsize*ysize);
    
    if ((rank - (znorm*(xsize*ysize)))  < xsize) {
        yminus = (xsize*ysize) - (xsize - rank);
    }
    else {
        yminus = rank - xsize;
    }
    return yminus;
}


/*********************************************************************
*   zplus()
*
*/
int zplus(int rank) {
    return ( (rank + (xsize*ysize)) % (xsize*ysize*zsize) );
}


/*********************************************************************
*   zminus()
*
*/
int zminus(int rank) {
    int zminus;
    
    if (rank < (xsize*ysize)) {
        zminus = (xsize*ysize*zsize) - ((xsize*ysize) - rank);
    }
    else {
        zminus = rank - (xsize*ysize);
    }
    return zminus;
}


int main(int argc, char *argv[])
{
    unsigned char *ptr_uchar = NULL;
    unsigned int temp_uint = 0;
    double temp_double = 0.0;
    MPI_Status mpi_status;
    int i;
    int j;
    int k;
    int rc;
    double send_rate;
    double recv_rate;
    double send_units;
    double recv_units;
    unsigned long temp_bad_bytes;
    char unit_str[16];
    unsigned long stats_updates;
    
    /* init MPI */
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

    /* parse the command line */
    while ((ch= getopt(argc, argv, "c:i:m:p:r:s:t:u:vw:x:y:z:")) != EOF)   {
        switch (ch) {
            case 'v':
                verbose++;
                break;
            case 'c':
                count = atoi(optarg);
                break;
            case 't':
                tokens = atoi(optarg);
                break;
            case 'm':
                max_long_msg_size = atoi(optarg);
                if (max_long_msg_size < MIN_LONG_MSG_SIZE)
                    max_long_msg_size = 4 * MIN_LONG_MSG_SIZE;
                break;
            case 'r':
                short_to_long_msg_ratio = (float) atoi(optarg)/100.0;
                break;
            case 's':
                mpi_call_scheme = atoi(optarg);
                if (mpi_call_scheme > MAX_MPI_CALL_SCHEME) {
                    mpi_call_scheme = DEFAULT_MPI_CALL_SCHEME;
                }
                break;
            case 'u':
                uniform_msg_size = atoi(optarg);
                break;
            case 'w':
                walltime = atoi(optarg);
                count = 1000;  /* just to help the runtime status printout logic */
                break;
            case 'x':
                xsize = atoi(optarg);
                topology = MESH_2D;
                stats_size = mpi_size;
                break;
            case 'y':
                ysize = atoi(optarg);
                topology = MESH_2D;
                stats_size = mpi_size;
                break;
            case 'z':
                zsize = atoi(optarg);
                topology = MESH_3D;
                stats_size = mpi_size;
                break;
            case 'i':
                integrity_check = atoi(optarg);
                break;
            case 'p':
                stats_period = (float)atoi(optarg);
                stats_report_period = stats_period + 10.0;
                break;
            default:
                usage(argv[0]);
                exit(-1);
        }
    }

    /* sanity checks on options */
    if (count < REPORT_PERIOD)
        count = REPORT_PERIOD;
    
    if (integrity_period > count)
        integrity_period = count;
    
    if (my_rank == 0) {
        if ((topology == MESH_2D) && (xsize*ysize != mpi_size)) {
            printf("%d: Bad 2D mesh dimensions, %d * %d != %d\n",my_rank,xsize,ysize,
                   mpi_size);
            MPI_Abort(MPI_COMM_WORLD,-30);
        }
        else if ((topology == MESH_3D) && (xsize*ysize*zsize != mpi_size)) {
            printf("%d: Bad 3D mesh dimensions, %d * %d * %d != %d\n",my_rank,xsize,ysize,
                   zsize,mpi_size);
            MPI_Abort(MPI_COMM_WORLD,-30);
        }
    }

    /* init the stats stuff */
    memset(&stats,0,sizeof(stats_t));
    stats.start_time = 0.0;
    stats.end_time = 0.0;
    stats.current_time = 0.0;
    stats.time = 0.0;

    token_len_init();

    /* Allocate enough MPI_request structures to deal with all the requests for
     * all our roles. Max of 7 roles: 1 dealer roles + 6 edge roles.
     * Each role has the same number of tokens. Need a request for both
     * send and receive.
    */
    num_mpi_requests = 2 * 7 * tokens;
    
    if (verbose > 1)
        printf("%d: num_mpi_requests = %d\n",my_rank,num_mpi_requests);
    
    mpi_request_array = (MPI_Request*)calloc(num_mpi_requests,sizeof(MPI_Request));
    if (mpi_request_array == NULL) {
        printf("%d: Couldn't calloc() mpi_request_array\n",my_rank);
        MPI_Abort(MPI_COMM_WORLD,-21);
        final_cleanup(-21);
    }

    topology_roles_init();
                
    /* print out our settings and config*/
    if (my_rank == 0  &&  verbose) {
        printf("%d: sizeof(double) = %d\n",my_rank,(int)sizeof(double));
        printf("%d: sizeof(unsigned long) = %d\n",my_rank,(int)sizeof(unsigned long));
        printf("%d: sizeof(unsigned int) = %d\n",my_rank,(int)sizeof(unsigned int));
        printf("%d: count(iterations) = %d\n",my_rank,count);
        printf("%d: walltime = %ld minutes\n",my_rank,walltime);
        printf("%d: stats period = %.01f seconds\n",my_rank,stats_period);
        printf("%d: stats report period = %.01f seconds\n",my_rank,stats_report_period);
        printf("%d: number of tokens = %d\n",my_rank,tokens);
        printf("%d: SHORT_TO_LONG_MSG_RATIO = %.02f\n",my_rank,short_to_long_msg_ratio);
        printf("%d: min short message size = %d bytes\n",my_rank,MIN_SHORT_MSG_SIZE);
        printf("%d: max short message size = %d bytes\n",my_rank,MAX_SHORT_MSG_SIZE);
        printf("%d: min long message size = %d bytes\n",my_rank,MIN_LONG_MSG_SIZE);
        printf("%d: max long message size = %lu bytes\n",my_rank,max_long_msg_size);
        printf("%d: uniform message size = %lu bytes\n",my_rank,uniform_msg_size);
        printf("%d: non-blocking mpi function calling scheme = %d\n",
               my_rank,mpi_call_scheme);
        printf("%d: integrity check = %d\n",my_rank,integrity_check);
        
        switch (topology) {
            case STAR:
                printf("%d: STAR topology, 1 dealer, %d edges\n",my_rank,mpi_size-1);
                break;
            case MESH_2D:
                printf("%d: MESH_2D topology, %d x %d\n",my_rank,xsize,ysize);
                break;
            case MESH_3D:
                printf("%d: MESH_3D topology, %d x %d x %d\n",my_rank,xsize,ysize,zsize);
                break;
        }

        for (i=0; i<tokens; i++) {
            printf("%d: token %d message length = %lu bytes\n",my_rank,i,token_len[i]);
        }
    }

    send_recv_buf_init();
    
    /* The last thing we need to do before starting the actual data transfers
     * is for all nodes except rank 0 to pre-post a receive for a control
     * word.  Rank 0 will use this word to coordinate the shutdown or whatever
     * of the other ranks. For the case of mesh topologies, rank 0 also will
     * prepost a receive for every other node.
    */
    if (my_rank == 0) {
        
        /* allocate the array to hold stats from other nodes */
        allstats = calloc(mpi_size,sizeof(stats_t));
        if (allstats == NULL) {
            printf("%d: Error calloc()ing allstats[]!\n",my_rank);
            MPI_Abort(MPI_COMM_WORLD,-59);
            final_cleanup(-59);
        }

        if (topology != STAR) {
            dealer_ctrl = (dealer_ctrl_t*)calloc(mpi_size,sizeof(dealer_ctrl_t));
            if (dealer_ctrl == NULL) {
                printf("%d: Error calloc()ing dealer_ctrl array\n",my_rank);
                MPI_Abort(MPI_COMM_WORLD,-51);
                final_cleanup(-51);
            }

            for (i=1; i<mpi_size; i++) {
                /* Irecv for getting control messages from other dealers */
                rc = MPI_Irecv(&dealer_ctrl[i].ctrl_word,
                               1,
                               MPI_UNSIGNED_LONG,
                               i,
                               CTRL_WORD_TAG,
                               MPI_COMM_WORLD,
                               &dealer_ctrl[i].mpi_request);

                if (rc != MPI_SUCCESS) {
                    printf("%d: MPI_Irecv failed for CTRL_WORD_TAG from rank %d\n",
                           my_rank,i);
                    MPI_Abort(MPI_COMM_WORLD,-17);
                    final_cleanup(-17);
                }
                dealer_ctrl[i].status = DEALER_RUNNING;

                /* Irecv for getting stats update messages from other nodes */
                rc = MPI_Irecv(&allstats[i],
                               sizeof(stats_t),
                               MPI_BYTE,
                               i,
                               STATS_TAG,
                               MPI_COMM_WORLD,
                               &dealer_ctrl[i].stats_mpi_request);

                if (rc != MPI_SUCCESS) {
                    printf("%d: MPI_Irecv failed for STATS_TAG from rank %d\n",
                           my_rank,i);
                    MPI_Abort(MPI_COMM_WORLD,-61);
                    final_cleanup(-61);
                }
            }
        }
    }
    else {
        rc = MPI_Irecv(&ctrl_word,
                       1,
                       MPI_UNSIGNED_LONG,
                       0,
                       CTRL_WORD_TAG,
                       MPI_COMM_WORLD,
                       &ctrl_request);

        if (rc != MPI_SUCCESS) {
            printf("%d: MPI_Irecv failed for CTRL_WORD_TAG from rank 0\n",
                   my_rank);
            MPI_Abort(MPI_COMM_WORLD,-17);
            final_cleanup(-17);
        }
    }
    
    /* Now everything should be ready.  The dealers will start their sends. */
    for (i=0; i<num_roles; i++) {
        if (roles[i].role == DEALER) {
            for (j=0; j<tokens; j++) {
                rc = MPI_Isend(token_obj[j].buf,
                               token_len[j],
                               MPI_BYTE,
                               roles[i].edges[token_obj[j].start_edge],
                               token_obj[j].tag,
                               MPI_COMM_WORLD,
                               roles[i].recv_queue[j].send_mpi_request);

				roles[i].recv_queue[j].send_request_active = 1;

                if (rc != MPI_SUCCESS) {
                    printf("%d: MPI_Isend failed for tag %08x to edge %d (rank %d)\n",
                           my_rank,token_obj[j].tag,token_obj[j].start_edge,
                           roles[i].edges[token_obj[j].start_edge]);
                    MPI_Abort(MPI_COMM_WORLD,-11);
                    final_cleanup(-11);
                }
                stats.num_isends++;
                stats.total_bytes_sent += token_len[j];
                stats.tokens_dealt++;
                
                if (mpi_call_scheme == 0) {
                    /* we don't care about the request object from Isends */
                    MPI_Request_free(roles[i].recv_queue[j].send_mpi_request);
					roles[i].recv_queue[j].send_request_active = 0;
                }
                
                token_obj[j].status = TAG_RUNNING;
                token_obj[j].last_cycle_start = MPI_Wtime();
            }
        }
    }

    MPI_Barrier(MPI_COMM_WORLD);
    
    /* all nodes grab starting timestamps as needed */
    last_ctrl_coord_time = MPI_Wtime();
    stats.start_time = last_ctrl_coord_time;
    last_stats_time = last_ctrl_coord_time;
    last_stats_report_time = last_ctrl_coord_time;
    
    if (my_rank == 0)
        printf("%d: INIT COMPLETED. STARTING MAIN LOOP.\n",my_rank);
               
    /* MAIN LOOP
     * At this point, everything is now receive event driven.
     *
     * For a dealer role,
     * the loop continually checks the status of pre-posted receives for
     * completion. When a receive has completed, a new receive is
     * pre-posted for the received tag from the next destination the tag
     * object will be sent to. Appropriate status is update upon receives.
     *
     * For an edge role,
     * the loop continually checks the status of pre-posted receives for
     * completion. When a receive has completed, this means a tag object
     * has arrived from a dealer. The tag object message is immediately
     * sent back to the dealer that it came from and then a receive
     * is pre-posted for that tag again.
    */
    tokens_finished = 0;
    dealers_finished = 0;
    ctrl_status = DEALER_RUNNING;
    stats_updates = 0;
    
    while (!main_loop_exit) {
        for (i=0; i<num_roles; i++) {            
            for (j=0; j<tokens; j++) {

                if ((roles[i].role == DEALER) && (token_obj[j].status == TAG_FINISHED))
                    continue;
                
                completion_flag = FALSE;
                MPI_Test(roles[i].recv_queue[j].mpi_request,
                         &completion_flag,
                         &roles[i].recv_queue[j].mpi_status);

                if (mpi_call_scheme == 2 && roles[i].recv_queue[j].send_request_active) {
                    MPI_Test(roles[i].recv_queue[j].send_mpi_request,
                             &completion_flag2,
                             &mpi_status);                
					roles[i].recv_queue[j].send_request_active = 0;
                }
                else if (mpi_call_scheme == 2 && !roles[i].recv_queue[j].send_request_active) {
					if (verbose > 1) {
						printf ("%d: DEBUG: send request not active at location 1\n",
							my_rank);
					}
				}
                                
                if (completion_flag) {
                    /* the receive seems to be complete according to MPI */
                    
                    /* if the receive of the token object completed, then no
                     * doubt the Isend that sent it is completed!
                    */
                    if (mpi_call_scheme == 1) {
                        completion_flag2 = FALSE;
                        temp_uint = 0;
                        
                        while (!completion_flag2 && roles[i].recv_queue[j].send_request_active) {
                            MPI_Test(roles[i].recv_queue[j].send_mpi_request,
                                     &completion_flag2,
                                     &mpi_status);                    

                            temp_uint++;
                        }
						roles[i].recv_queue[j].send_request_active = 0;
                        
                        stats.num_mpi_test += temp_uint;                        
                    }
                    
                    /* query for the amount of data received */
                    MPI_Get_count(&roles[i].recv_queue[j].mpi_status,MPI_BYTE,&recv_bytes);
                    
                    /* just check to see if the message size received agrees with what
                     * we were expecting.
                    */
                    if (recv_bytes != token_len[j]) {
                        printf("%d: ERROR! received %d bytes, wanted %lu bytes, tag %08x\n",
                               my_rank,recv_bytes,token_len[j],roles[i].recv_queue[j].tag);
                    }
                    
                    stats.total_bytes_recv += recv_bytes;
                    
                    if (roles[i].role == DEALER) {
                        /* We just receieved a tag object that was bounced back to us by
                         * an edge node. We need to send the tag object on to the next
                         * node the tag object is destined for, and of course we pre-post
                         * a receive.
                        */
                        if ((token_obj[j].current_edge == token_obj[j].start_edge))
                        {
                            /* looks like the token has cycled "around" */
                            token_obj[j].cycles++;

                            if (token_obj[j].cycles > 0) {
                                /* do stats */
                                temp_double = MPI_Wtime();
                                token_obj[j].tot_cycle_time += temp_double - token_obj[j].last_cycle_start;
                                token_obj[j].last_cycle_start = temp_double;
                                token_obj[j].ave_cycle_time = token_obj[j].tot_cycle_time / token_obj[j].cycles;
                                token_obj[j].velocity = token_obj[j].cycles * roles[i].num_edges / token_obj[j].tot_cycle_time;
                            }

                            if (verbose > 2  &&  token_obj[j].cycles != 0) {
                                printf("%d: Token %d completed cycle %d\n",
                                       my_rank,j,token_obj[j].cycles);
                            }
                            else if (verbose > 1 &&
                                     ((token_obj[j].cycles % (count / REPORT_PERIOD)) == 0) &&
                                     (token_obj[j].cycles != 0) ) {
                                printf("%d: (Token %d) cycle=%d average cycle time (ms)=%.6f velocity=%.2f nodes/sec\n",
                                       my_rank,j,token_obj[j].cycles,token_obj[j].ave_cycle_time*1000.0,token_obj[j].velocity);
                            }
                           
                            /* did the token finish? */
                            if (token_obj[j].cycles == count  &&  walltime == -1) {
                                if (verbose > 1)
                                    printf("%d: Token %d finished %d cycles!\n",my_rank,j,token_obj[j].cycles);
                                    
                                    token_obj[j].status = TAG_FINISHED;
                                    
                                    tokens_finished++;
                                    
                                    if (verbose > 2)
                                        printf("%d: tokens_finished = %d\n",my_rank,
                                               tokens_finished);
                                               
                                    continue;
                            }
                            else if (integrity_check == 2  &&
                                     (token_obj[j].cycles % integrity_period) == 0) {
                                temp_bad_bytes = 0;
                                ptr_uchar = (unsigned char*)roles[i].recv_queue[j].buf;

                                for (k=0; k<token_len[j]; k++) {
                                    if (ptr_uchar[k] != (k % 256)) {
                                        temp_bad_bytes++;
										/*
                                        printf("%d: token %d recv buffer corrupted!\n",
                                               my_rank,j);
                                        continue;
										*/
                                    }
                                }
                                
                                if (temp_bad_bytes) {
                                    stats.integrity_errors++;
                                    stats.total_bad_bytes += temp_bad_bytes;
                                }
                            }
                        }
                        
                        token_obj[j].last_edge = token_obj[j].current_edge;
                        
                        /* if set, check the integrity of the buffer */
                        if (integrity_check == 1  &&
                            (token_obj[j].cycles % integrity_period) == 0) {
                            temp_bad_bytes = 0;
                            ptr_uchar = (unsigned char*)roles[i].recv_queue[j].buf;
                            
                            for (k=0; k<token_len[j]; k++) {
                                if (ptr_uchar[k] != (k % 256)) {
                                    temp_bad_bytes++;
									/* 
                                    printf("%d: token %d recv buffer corrupted!\n",
                                           my_rank,j);
                                    continue;
									*/
                                }
                            }
                            
                            if (temp_bad_bytes) {
                                stats.integrity_errors++;
                                stats.total_bad_bytes += temp_bad_bytes;
                            }
                        }
                        
                        /* compute the next destination for the tag object */
                        token_obj[j].current_edge = (token_obj[j].current_edge + 1) % roles[i].num_edges;
                        
                        if (verbose > 2)
                            printf("%d: Next destination for tag %08x is edge %d (rank %d)\n",
                                   my_rank,token_obj[j].tag,token_obj[j].current_edge,
                                   roles[i].edges[token_obj[j].current_edge]);
                                   
                        /* pre-post a receive for this token object*/
                        rc = MPI_Irecv(roles[i].recv_queue[j].buf,
                                       token_len[j],
                                       MPI_BYTE,
                                       roles[i].edges[token_obj[j].current_edge],
                                       token_obj[j].tag,
                                       MPI_COMM_WORLD,
                                       roles[i].recv_queue[j].mpi_request);

                        if (rc != MPI_SUCCESS) {
                            printf("%d: MPI_Irecv failed for tag %08x from edge %d (rank %d)\n",
                                   my_rank,token_obj[j].tag,token_obj[j].current_edge,
                                   roles[i].edges[token_obj[j].current_edge]);
                            MPI_Abort(MPI_COMM_WORLD,-12);
                            final_cleanup(-12);
                        }
						stats.num_irecvs++;

                        /* send the token to is next destination depending on 
                         * the integrity_check
                        */
                        if (integrity_check == 2) {
                            /* send the token object to its next destination using
                             * the last buffer we received, thus we are passing
                             * the buffer data around. allows us to test for
                             * data integrity more stringently.
                             *
                             * if the buffer we just received for this token had
                             * integrity errors, then send a clean one.
                            */
                            if (temp_bad_bytes) {
                                rc = MPI_Isend(token_obj[j].buf,
                                               token_len[j],
                                               MPI_BYTE,
                                               roles[i].edges[token_obj[j].current_edge],
                                               token_obj[j].tag,
                                               MPI_COMM_WORLD,
                                               roles[i].recv_queue[j].send_mpi_request);
								roles[i].recv_queue[j].send_request_active = 1;
                            }
                            else {
                                rc = MPI_Isend(roles[i].recv_queue[j].buf,
                                               token_len[j],
                                               MPI_BYTE,
                                               roles[i].edges[token_obj[j].current_edge],
                                               token_obj[j].tag,
                                               MPI_COMM_WORLD,
                                               roles[i].recv_queue[j].send_mpi_request);                            
								roles[i].recv_queue[j].send_request_active = 1;
                            }
                        }
                        else {
                            /* send the token object to its next destination 
                             * with our original clean send buffer
                            */
                            rc = MPI_Isend(token_obj[j].buf,
                                           token_len[j],
                                           MPI_BYTE,
                                           roles[i].edges[token_obj[j].current_edge],
                                           token_obj[j].tag,
                                           MPI_COMM_WORLD,
                                           roles[i].recv_queue[j].send_mpi_request);                        
							roles[i].recv_queue[j].send_request_active = 1;
                        }
                        
                        if (rc != MPI_SUCCESS) {
                            printf("%d: MPI_Isend failed for tag %08x to edge %d (rank %d)\n",
                                   my_rank,token_obj[j].tag,token_obj[j].current_edge,
                                   roles[i].edges[token_obj[j].current_edge]);
                            MPI_Abort(MPI_COMM_WORLD,-13);
                            final_cleanup(-13);
                        }
                        stats.num_isends++;
                        stats.total_bytes_sent += token_len[j];
                        stats.tokens_dealt++;
                        
                        if (mpi_call_scheme == 0) {
                            /* we don't care about the request object from Isends */
                            MPI_Request_free(roles[i].recv_queue[j].send_mpi_request);
							roles[i].recv_queue[j].send_request_active = 0;
                        }
                    }
                    else if (roles[i].role == EDGE) {
                        /* We just need to bounce the tag object back to the dealer it
                         * came from.
                        */

                        /* send the token object back to its dealer */
                        rc = MPI_Isend(roles[i].recv_queue[j].buf,
                                       token_len[j],
                                       MPI_BYTE,
                                       roles[i].dealer,
                                       roles[i].recv_queue[j].tag,
                                       MPI_COMM_WORLD,
                                       roles[i].recv_queue[j].send_mpi_request);

						roles[i].recv_queue[j].send_request_active = 1;

                        if (rc != MPI_SUCCESS) {
                            printf("%d: MPI_Isend failed for tag %08x to dealer %d\n",
                                   my_rank,roles[i].recv_queue[j].tag,roles[i].dealer);
                            MPI_Abort(MPI_COMM_WORLD,-14);
                            final_cleanup(-14);
                        }
                        stats.num_isends++;
                        stats.total_bytes_sent += token_len[j];
                        stats.tokens_bounced++;
                        
                        if (mpi_call_scheme == 0) {
                            /* we don't care about the request object from Isends */
                            MPI_Request_free(roles[i].recv_queue[j].send_mpi_request);
							roles[i].recv_queue[j].send_request_active = 0;
                        }

                        if (verbose > 2)
                            printf("%d: Bounced token object %08x to dealer %d\n",
                                   my_rank,roles[i].recv_queue[j].tag,roles[i].dealer);
                                   
                        /* pre-post a receive for this token object */
                        rc = MPI_Irecv(roles[i].recv_queue[j].buf,
                                       token_len[j],
                                       MPI_BYTE,
                                       roles[i].dealer,
                                       roles[i].recv_queue[j].tag,
                                       MPI_COMM_WORLD,
                                       roles[i].recv_queue[j].mpi_request);

                        if (rc != MPI_SUCCESS) {
                            printf("%d: MPI_Irecv failed for tag %08x from dealer %d\n",
                                   my_rank,roles[i].recv_queue[j].tag,roles[i].dealer);
                            MPI_Abort(MPI_COMM_WORLD,-15);
                            final_cleanup(-15);
                        }
						stats.num_irecvs++;
                    }
                }
            }
        }

        /* is it time to check for control coordination? */
        if ( (MPI_Wtime() - last_ctrl_coord_time) > CTRL_PERIOD ) {

            /* Control coordination from rank 0 */
            if (my_rank != 0) {
                    completion_flag = FALSE;
                    MPI_Test(&ctrl_request,
                             &completion_flag,
                             &ctrl_mpi_status);

                    if (completion_flag) {
                        /* seems to be word from rank 0 */
                        if (ctrl_word == CTRL_SHUTDOWN) {
                            if (verbose)
                                printf("%d: Received CTRL_SHUTDOWN from rank 0\n",
                                       my_rank);
                        }
                        main_loop_exit = TRUE;
                    }
            }

            /* Control coordination logic for all ranks */
            if ( (topology == STAR) && (my_rank == 0) ) {
                temp_double = MPI_Wtime() - stats.start_time;
                temp_uint = (unsigned int)(temp_double/60.0);
                
                if (tokens_finished == tokens)
                    main_loop_exit = TRUE;

                /* if we are in walltime mode, then check to see if time is up */
                if (walltime != -1  &&  temp_uint >= walltime) {
                    main_loop_exit = TRUE;
                    
                    if (verbose)
                        printf("%d: Walltime of %ld minutes exceeded! Shutting down...\n",
                               my_rank,walltime);
                }
            }
            else if ( (topology != STAR) && (my_rank != 0) ) {
                if (tokens_finished == tokens  &&   ctrl_status == DEALER_RUNNING) {
                    /* We are a dealer but not rank 0 and all the tokens we are
                     * responsible for have finished. We need to tell rank 0
                     * we are finished.
                    */
                    if (verbose)
                        printf("%d: Dealer is finished, notifying rank 0\n",
                               my_rank);

                    ctrl_word_send = CTRL_DEALER_DONE;
                    rc = MPI_Send(&ctrl_word_send,1,MPI_UNSIGNED_LONG,0,
                                  CTRL_WORD_TAG,MPI_COMM_WORLD);
                    if (rc != MPI_SUCCESS) {
                        printf("%d: MPI_Send to rank 0 of CTRL_DEALER_DONE failed!\n",
                               my_rank);
                        MPI_Abort(MPI_COMM_WORLD,-50);
                        final_cleanup(-50);
                    }
                    ctrl_status = DEALER_DONE;
                }
                else if ((MPI_Wtime() - last_stats_time) > stats_period ) {
                    /* time to send a stats update to rank 0 */
                    stats.current_time = MPI_Wtime();
                    
                    rc = MPI_Isend(&stats,
                                   sizeof(stats_t),
                                   MPI_BYTE,
                                   0,
                                   STATS_TAG,
                                   MPI_COMM_WORLD,
                                   &stats_mpi_request);

				   stats_mpi_request_active = 1;

                    if (rc != MPI_SUCCESS) {
                        printf("%d: MPI_Isend failed for STATS_TAG to rank 0\n",
                               my_rank);
                        MPI_Abort(MPI_COMM_WORLD,-64);
                        final_cleanup(-64);
                    }

                    last_stats_time = MPI_Wtime();
                }
                else {
                    /* This block should happen most of the time. All we want to
                     * do is call MPI_Test() on the request handles for the Isends
                     * used to send stats to rank 0. Untested Isends is a bad
                     * thing since they eat up precious Portals kernel resources.
                     * We don't care if the Isends completed, we just want MPI to
                     * reclaim resources when possible, i.e. when completed
                     * Isends are Tested.
                    */ 
					if (stats_mpi_request_active) {
						MPI_Test(&stats_mpi_request,
								 &completion_flag,
								 &stats_mpi_status);

					   stats_mpi_request_active = 0;
					}
                }
            }
            else if ( (topology != STAR) && (my_rank == 0) ) {
                temp_double = MPI_Wtime() - stats.start_time;
                temp_uint = (unsigned int)(temp_double/60.0);

                /* check for any notifications from other dealers */
                for (i=1; i<mpi_size; i++) {
                    if (dealer_ctrl[i].status == DEALER_RUNNING) {
                        /* test for CTRL_WORD_TAG receives */
                        completion_flag = FALSE;
                        MPI_Test(&dealer_ctrl[i].mpi_request,
                                 &completion_flag,
                                 &dealer_ctrl[i].mpi_status);

                        if (completion_flag &&
                            dealer_ctrl[i].ctrl_word == CTRL_DEALER_DONE) {
                            /* a dealer is telling us they are finished */

                            dealer_ctrl[i].status = DEALER_DONE;
                            dealers_finished++;

                            if (verbose > 1)
                                printf("%d: Dealer %d is finished (%d of %d done)\n",
                                       my_rank,i,dealers_finished,mpi_size);
                        }

                        /* test for STATS_TAG receives */
                        completion_flag = FALSE;
                        MPI_Test(&dealer_ctrl[i].stats_mpi_request,
                                 &completion_flag,
                                 &stats_mpi_status);

                        if (completion_flag) {
                            /* we received new stats data from node i */
                            stats_updates++;

                            /* post a new Irecv for getting stats update from 
                             * the node next time.
                            */
                            rc = MPI_Irecv(&allstats[i],
                                           sizeof(stats_t),
                                           MPI_BYTE,
                                           i,
                                           STATS_TAG,
                                           MPI_COMM_WORLD,
                                           &dealer_ctrl[i].stats_mpi_request);

                            if (rc != MPI_SUCCESS) {
                                printf("%d: MPI_Irecv failed for STATS_TAG from rank %d\n",
                                       my_rank,i);
                                MPI_Abort(MPI_COMM_WORLD,-61);
                                final_cleanup(-61);

                            }
                        }
                    }
                }

                /* has the rank 0 dealer finished ? */
                if (tokens_finished == tokens  &&  ctrl_status == DEALER_RUNNING) {
                    dealers_finished++;
                    ctrl_status = DEALER_DONE;
                    
                    if (verbose > 1)
                        printf("%d: Dealer 0 finished\n",my_rank);
                }

                /* have all the other dealers finished? */
                if (dealers_finished == mpi_size) {
                    main_loop_exit = TRUE;

                    if (verbose > 1)
                        printf("%d: All dealers finished!\n",my_rank);
                }

                /* if we are in walltime mode, then check to see if time is up */
                if (walltime != -1  &&  temp_uint >= walltime) {
                    main_loop_exit = TRUE;
                    
                    if (verbose)
                        printf("%d: Walltime of %ld minutes exceeded! Shutting down...\n",
                               my_rank,walltime);
                }
            }

            /* is it time to report on progress? */
            if ( my_rank == 0 &&
                ((MPI_Wtime() - last_stats_report_time) > stats_report_period)) {
                /* put stats for rank 0 into the right place */
                stats.current_time = MPI_Wtime();
                memcpy(&allstats[0],&stats,sizeof(stats_t));

                overall_stats.total_bytes_sent = 0.0;
                overall_stats.total_bytes_recv = 0.0;
				overall_stats.num_isends = 0.0;
				overall_stats.num_irecvs = 0.0;
                overall_stats.time = 0.0;
                overall_stats.total_bad_bytes = 0;
                overall_stats.integrity_errors = 0;

                for (i=0; i<stats_size; i++) {
                    overall_stats.total_bytes_sent += allstats[i].total_bytes_sent;
                    overall_stats.total_bytes_recv += allstats[i].total_bytes_recv;
                    overall_stats.num_isends += allstats[i].num_isends;
                    overall_stats.num_irecvs += allstats[i].num_irecvs;
                    overall_stats.time += allstats[i].current_time - allstats[i].start_time;
                    overall_stats.total_bad_bytes += allstats[i].total_bad_bytes;
                    overall_stats.integrity_errors += allstats[i].integrity_errors;
                }

                if ((overall_stats.total_bytes_sent / (double)TERABYTE) > 1.0) {
                    recv_units = overall_stats.total_bytes_sent / (double)TERABYTE;
                    send_units = overall_stats.total_bytes_sent / (double)TERABYTE;
                    sprintf(unit_str,TB_STRING);
                }
                else if ((overall_stats.total_bytes_sent / (double)GIGABYTE) > 1.0) {
                    recv_units = overall_stats.total_bytes_sent / (double)GIGABYTE;
                    send_units = overall_stats.total_bytes_sent / (double)GIGABYTE;
                    sprintf(unit_str,GB_STRING);
                }
                else {
                    recv_units = overall_stats.total_bytes_sent / (double)MEGABYTE;
                    send_units = overall_stats.total_bytes_sent / (double)MEGABYTE;
                    sprintf(unit_str,MB_STRING);
                }

                send_rate = (overall_stats.total_bytes_sent / (overall_stats.time * (double)MEGABYTE));
                recv_rate = (overall_stats.total_bytes_recv / (overall_stats.time * (double)MEGABYTE));
                overall_stats.time = overall_stats.time / stats_size;

                printf("0: STATUS: ave send rate = %.02f MB/s  ave recv rate = %.02f MB/s\n",
                       send_rate,recv_rate);
                printf("0: STATUS: total data sent = %.04f %s  total data recv = %.04f %s  average time = %.02f s\n",
                       send_units,unit_str,recv_units,unit_str,overall_stats.time);
				printf("0: STATUS: ave sent msgrate = %0.2f msgs/s/rank   ave recv msgrate = %0.2f msgs/s/rank\n",
						overall_stats.num_isends/overall_stats.time/stats_size,overall_stats.num_irecvs/overall_stats.time/stats_size);
                printf("0: STATUS: integrity_errors = %.01f  total_bad_bytes = %.01f  stats_updates = %lu\n",
                       overall_stats.integrity_errors,overall_stats.total_bad_bytes,stats_updates);

                /* if the completion checking is being driven by cycle count
                 * and not walltime, print out some extra status info to
                 * get an idea of progress w.r.t cycle count.
                */
                if (walltime == -1) {
                    temp_uint = 0;
                    for (j=0; j<tokens; j++) {
                        temp_uint += token_obj[j].cycles;
                    }
                    printf("0: STATUS: average cycles completed = %.01f\n",
                           (float)temp_uint/(float)tokens);
                }

                last_stats_report_time = MPI_Wtime();
            }

            /* take timestamp of last control coordination activity */
            last_ctrl_coord_time = MPI_Wtime();
        }
    } /* end while (!main_loop_exit) */

    /* all nodes grab their finishing timestamp */
    stats.end_time = MPI_Wtime();            

    /* The rank 0 node will exit the main loop first and then tell all
     * the other nodes to shutdown. Rank 0 has to make the decision
     * shut everything down; this logic is at the end of the main 
     * loop.
    */
    if (my_rank == 0) {
        /* tell other ranks we are done */
        ctrl_word = CTRL_SHUTDOWN;
        printf("%d: Sending CTRL_SHUTDOWN to everyone...\n",my_rank);

        for (i=1; i<mpi_size; i++) {
            rc = MPI_Send(&ctrl_word,1,MPI_UNSIGNED_LONG,i,CTRL_WORD_TAG,MPI_COMM_WORLD);
            if (rc != MPI_SUCCESS) {
                printf("%d: MPI_Send to %d of CTRL_SHUTDOWN failed!\n",
                       my_rank,i);
                MPI_Abort(MPI_COMM_WORLD,-9);
                final_cleanup(-9);
            }
        }
        MPI_Barrier(MPI_COMM_WORLD);
    }
    else {
        MPI_Barrier(MPI_COMM_WORLD);

        printf("%d: Main loop shutdown.\n",my_rank);
    }
    
    /* gather all the stats back to rank 0 */
    if (topology != STAR) {
        rc = MPI_Gather(&stats,sizeof(stats_t),MPI_BYTE,allstats,sizeof(stats_t),
                        MPI_BYTE,0,MPI_COMM_WORLD);
        if (rc != MPI_SUCCESS) {
            printf("%d: MPI_Gather of stats failed!\n",my_rank);
            MPI_Abort(MPI_COMM_WORLD,-69);
            final_cleanup(-69);        
        }
    }
    else if (my_rank == 0) {
        /* special case for the STAR topology */
        memcpy(&allstats[0],&stats,sizeof(stats_t));
    }
    
    if (my_rank == 0) {
        overall_stats.total_bytes_sent = 0.0;
        overall_stats.total_bytes_recv = 0.0;
		overall_stats.num_isends = 0.0;
		overall_stats.num_irecvs = 0.0;
        overall_stats.time = 0.0;
        overall_stats.total_bad_bytes = 0;
        overall_stats.integrity_errors = 0;

        for (i=0; i<stats_size; i++) {
            if ((allstats[i].total_bytes_recv / (double)TERABYTE) > 1.0) {
                recv_units = allstats[i].total_bytes_recv / (double)TERABYTE;
                send_units = allstats[i].total_bytes_sent / (double)TERABYTE;
                sprintf(unit_str,TB_STRING);
            }
            else if ((allstats[i].total_bytes_sent / (double)GIGABYTE) > 1.0) {
                recv_units = allstats[i].total_bytes_recv / (double)GIGABYTE;
                send_units = allstats[i].total_bytes_sent / (double)GIGABYTE;
                sprintf(unit_str,GB_STRING);
            }
            else {
                recv_units = allstats[i].total_bytes_recv / (double)MEGABYTE;
                send_units = allstats[i].total_bytes_sent / (double)MEGABYTE;
                sprintf(unit_str,MB_STRING);
            }

            printf("Rank %d: total data sent = %.04f %s total data recv = %.04f %s time = %.02f s\n",
                   i,send_units,unit_str,recv_units,unit_str,
                   allstats[i].end_time - stats.start_time);

            send_rate = (allstats[i].total_bytes_sent / (double)MEGABYTE) / 
                         (allstats[i].end_time - stats.start_time);
            overall_stats.total_bytes_sent += allstats[i].total_bytes_sent;
            recv_rate = (allstats[i].total_bytes_recv / (double)MEGABYTE) /
                         (allstats[i].end_time - stats.start_time);
            overall_stats.total_bytes_recv += allstats[i].total_bytes_recv;
            overall_stats.time += allstats[i].end_time - stats.start_time;
            printf("Rank %d: send rate = %.02f MB/s  recv rate = %.02f MB/s\n",
                   i,send_rate,recv_rate);
            
			overall_stats.num_isends += allstats[i].num_isends;
			overall_stats.num_irecvs += allstats[i].num_irecvs;
			printf("Rank %d: sent msgrate = %0.2f msgs/s   recv msgrate = %0.2f msgs/s\n",
				i,allstats[i].num_isends/(allstats[i].end_time - stats.start_time),
				allstats[i].num_irecvs/(allstats[i].end_time - stats.start_time));

            overall_stats.total_bad_bytes += allstats[i].total_bad_bytes;
            overall_stats.integrity_errors += allstats[i].integrity_errors;
            printf("Rank %d: integrity_errors = %.01f  total_bad_bytes = %.01f\n",
                   i,allstats[i].integrity_errors,allstats[i].total_bad_bytes);
            
            printf("Rank %d: tokens_dealt = %lu  tokens_bounced = %lu\n",
                   i,allstats[i].tokens_dealt,allstats[i].tokens_bounced);
        }

        send_rate = (overall_stats.total_bytes_sent / (overall_stats.time * (double)MEGABYTE));
        recv_rate = (overall_stats.total_bytes_recv / (overall_stats.time * (double)MEGABYTE));
        overall_stats.time = overall_stats.time / stats_size;

        if ((overall_stats.total_bytes_recv / (double)TERABYTE) > 1.0) {
            recv_units = overall_stats.total_bytes_recv / (double)TERABYTE;
            send_units = overall_stats.total_bytes_sent / (double)TERABYTE;
            sprintf(unit_str,"TB");
        }
        else if ((overall_stats.total_bytes_sent / (double)GIGABYTE) > 1.0) {
            recv_units = overall_stats.total_bytes_recv / (double)GIGABYTE;
            send_units = overall_stats.total_bytes_sent / (double)GIGABYTE;
            sprintf(unit_str,"GB");
        }
        else {
            recv_units = overall_stats.total_bytes_recv / (double)MEGABYTE;
            send_units = overall_stats.total_bytes_sent / (double)MEGABYTE;
            sprintf(unit_str,"MB");
        }
        
        printf("AVERAGE: send rate = %.02f MB/s  recv rate = %.02f MB/s time = %.02f s\n",
               send_rate,recv_rate,overall_stats.time);
		printf("AVERAGE: sent msgrate = %0.2f msgs/s/rank   recv msgrate = %0.2f msgs/s/rank\n",
				overall_stats.num_isends/overall_stats.time/stats_size,overall_stats.num_irecvs/overall_stats.time/stats_size);
        printf("TOTAL: total data sent = %.04f %s total data recv = %.04f %s\n",
               send_units,unit_str,recv_units,unit_str);
        printf("TOTAL: integrity_errors = %.01f  total_bad_bytes = %.01f\n",
               overall_stats.integrity_errors,overall_stats.total_bad_bytes);
    }
    
    if (verbose > 1) {
		MPI_Barrier(MPI_COMM_WORLD);
        printf("%d: num_isends = %.01f num_mpi_test = %.01f average num mpi_test = %.02f\n",
                my_rank,stats.num_isends,stats.num_mpi_test,
                (float)stats.num_mpi_test/(float)stats.num_isends);
    }


    /*final_cleanup(0);*/
    MPI_Barrier(MPI_COMM_WORLD);
    MPI_Finalize();
    return 0;
        
} /* end main */

