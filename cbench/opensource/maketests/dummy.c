
#include <stdio.h>
#include <stdlib.h>

#ifdef FFTW
  #include "fftw.h"
#endif


int main(int argc, char *argv[])
{
	#ifdef BLAS
	dgemm_();
	#endif

	#ifdef FFTW
	fftw_print_max_memory_usage();
	#endif

	#ifdef LAPACK
	cheev_();
	#endif
}
