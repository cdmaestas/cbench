      program mpi_hello
      include "mpif.h"

      integer :: ierr, rank
      character*80 hostname

      ierr = hostnm(hostname)

      call mpi_init(ierr)

      if (ierr .ne. 0) then
        write (*,*) 'ierr = ', ierr
        call exit
      endif

      call mpi_comm_rank(MPI_COMM_WORLD,rank,ierr)
c      call mpi_comm_size(MPI_COMM_WORLD,sz,ierr)

      print*, 'Hello, I am node ', trim(hostname), ' with rank ', rank

      call mpi_finalize(ierr)

      end
