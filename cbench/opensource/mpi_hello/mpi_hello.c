/*****************************************************************************

 name:		mpi_hello.c

 purpose:	Simple MPI "Hello World" program

 author: 	d. w. doerfler

 date:		10/08/97

 parameters:	

 returns:	

 comments:	

 revisions:	

*****************************************************************************/
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mman.h>
#include <mpi.h>

main(argc, argv)
int argc;
char **argv;
{
  int size, rank;
  void *ptr = NULL;
  char *env_temp;
  char hostname[256];

  env_temp = getenv("GMPI_SHMEM");
  /* printf("shmem = %s\n",env_temp); */

  /**************************************************************
    Initialize transport method
  **************************************************************/
  if ( MPI_Init( &argc, &argv ) != MPI_SUCCESS )
  {
    printf("Unable to initialize MPI\n");
    exit(0);
  }

/*
  ptr = mmap(NULL, 16384, PROT_READ,
             MAP_ANONYMOUS|MAP_PRIVATE, -1, 0);
  printf("mmap ptr = %p\n",ptr);
  if ((long)ptr == -1)
    ptr = NULL;
*/

  MPI_Comm_size( MPI_COMM_WORLD, &size );
  MPI_Comm_rank( MPI_COMM_WORLD, &rank );

  if (gethostname(hostname,256)) {
		printf("Unable to get hostname\n");
		sprintf(hostname,"UNKNOWN");
  }
  
  MPI_Barrier( MPI_COMM_WORLD );
  printf("Hello, I am node %s with rank %d\n", hostname, rank);

  MPI_Finalize();
  
  munmap(ptr,16384);
  
  exit(0);
}
