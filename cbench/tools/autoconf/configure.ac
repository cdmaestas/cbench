#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.65])
AC_INIT([Cbench Scalable Benchmarking and Testing Toolkit], [1.2], [cbench-sf-devel@lists.sourceforge.net])

# Checks for programs.
AC_PROG_CXX
AC_PROG_AWK
AC_PROG_CC
AC_PROG_INSTALL
AC_PROG_LN_S
AC_PROG_MAKE_SET
AC_PROG_RANLIB
AC_PROG_CPP
AC_PROG_F77
#AC_ARG_VAR([PERL], [Practical Extraction and Report Language])
#AC_CHECK_PROGS([PERL], [perl], [$am_aux_dir/missing perl])
AC_CHECK_PROG(PERL, perl, perl)



AC_LANG(C)
# Checks for libraries.
AC_CHECK_LIB([m], [abs])
AC_CHECK_LIB([mpe], [MPE_Log_event])
AC_CHECK_LIB([nsl], [nis_print_directory])
AC_CHECK_LIB([pthread], [pthread_join])
AC_CHECK_LIB([rt], [mq_send])

# Checks for header files.
AC_HEADER_RESOLV
AC_HEADER_STDC
AC_CHECK_HEADERS([arpa/inet.h fcntl.h float.h limits.h malloc.h memory.h netdb.h netinet/in.h stddef.h stdlib.h string.h strings.h sys/file.h sys/ioctl.h sys/param.h sys/socket.h sys/time.h unistd.h])

AC_CHECK_HEADER(asm/page.h, [AC_DEFINE(HAVE_PAGE_H, 1, [Define if we have page.h])],[])
AC_CHECK_HEADER(mpi.h, [AC_DEFINE(HAVE_MPI, 1, [Define if we have MPI])],[])

# Checks for typedefs, structures, and compiler characteristics.
AC_C_INLINE
AC_TYPE_OFF_T
AC_TYPE_PID_T
AC_C_RESTRICT
AC_TYPE_SIZE_T
AC_TYPE_SSIZE_T
AC_HEADER_STDBOOL
AC_CHECK_TYPES([ptrdiff_t])

# Checks for library functions.
AC_FUNC_ERROR_AT_LINE
AC_FUNC_FORK
AC_FUNC_MALLOC
AC_FUNC_MMAP
AC_FUNC_REALLOC
AC_FUNC_STRTOD
AC_CHECK_FUNCS([alarm bzero clock_gettime ftruncate getcwd gethostbyname gethostname gethrtime getpagesize gettimeofday inet_ntoa memmove memset mkdir munmap pow pstat_getdynamic rmdir select socket sqrt strcasecmp strchr strerror strstr strtol strtoul uname utime])

# Check for BLAS libraries
AC_ARG_WITH([blas], AS_HELP_STRING([--with-blas=DIR], 
            [Basic Linear Algebra Subprograms]), 
            BLAS_LIB="$withval")

if test x"$BLAS" = x; then
    AC_CHECK_LIB([blas], [cblas_dgemm], blas=yes, blas=no)

else
    AC_CHECK_LIB([$BLAS_LIB], [cblas_dgemm], blas=yes, blas=no)
fi

if test "$blas" = "no"; then
    AC_MSG_WARN([blas library not specified])
fi

AC_ARG_WITH([fftw2], AC_HELP_STRING([--with-fftw2=DIR], 
            [Fast Fourier Transform Libraries]), 
            FFTW2_LIB="$withval")

AC_ARG_WITH([fftw3], AC_HELP_STRING([--with-fftw3=DIR], 
            [Fast Fourier Transform Libraries]), 
            FFTW3_LIB="$withval")

if test x"$FFTW2_LIB" = x; then
#fftw3) # Much simpler check than fftw2
# Check for header <fftw3.h> AC_CHECK_HEADERS doesnt work, since we must
# use mpicc to get includes - cpp isnt always the same compiler.
    fftw2=yes
    AC_MSG_CHECKING([for fftw3.h])
        AC_TRY_COMPILE([#include<fftw3.h>
        ],,[
        # ok, look for library file too
            AC_MSG_RESULT(yes)
            AC_CHECK_LIB([fftw3],main,fftw3=yes,fftw3=no && AC_MSG_ERROR([Cannot find fftw3 library]))
            ],[
        ])
fi

if test x"$FFTW3_LIB" = x; then
    fftw3=yes
    AC_MSG_CHECKING([for fftw.h])
        AC_TRY_COMPILE([#include<fftw.h>
        ],,[
        # ok, look for library file too
            AC_MSG_RESULT(yes)
            AC_CHECK_LIB([fftw],fftwnd,fftw2=yes,fftw2=no && AC_MSG_ERROR([Cannot find fftw2 library]))
            ],[
        ])
fi

if test "$fftw2" = "no" && "$fftw3" = "no"; then
    AC_MSG_WARN([fftw library not specified])
fi

## MPI environment
AC_ARG_WITH([mpi], [AC_HELP_STRING([--with-mpi=DIR (e.g. /usr/local)], [Compile MPI-based components])],,MPI_PATH="$withval" && mpi=yes)

if test x"$MPI_PATH" = x; then
    AC_CHECK_LIB([mpi], [MPI_Send], mpi=yes, mpi=no)
fi

### Taken from gromacs source code ###
# if we are using mpi, also get an MPICC. We cannot set that in the PROG_CC macro
# above, since autoconf checks that the created file can be executed. This would
# fail on platforms where MPI executables can only be run through a batchqueue.
#if test "$mpi" = "yes"; then
#    if test x"$MPI_PATH" = x; then
#        AC_CHECK_PROGS(MPICC, mpicc, $CC,)
#    else
#        AC_CHECK_PROGS(MPICC, mpicc, $CC, [path=$MPI_PATH])
#    fi
#    # now change the normal cc to the MPI one - see the comment above.
#    CC=$MPICC
#    AC_MSG_CHECKING([whether mpicc works]) # be paranoid
#    AC_TRY_LINK([#include <mpi.h>],[int argc; char **argv; MPI_Init(&argc,&argv);],
#    AC_MSG_RESULT([yes]),AC_MSG_ERROR([Cannot compile and link MPI code with $CC]) && mpi=no)
#
#fi
#
#if test "$mpi" = "no"; then
#    AC_MSG_WARN([MPI not found; only standalone programs will be compiled])
#fi

AC_OUTPUT

# Print summary of what will and won't be built
if test "$mpi" = "no"; then
    echo ""
    echo "No MPI was found - only standalone programs will be compiled"
fi

if test "$fftw2" = "no"; then
    echo "No FFTW2 - LAMMPS will not be built"
fi

if test "$fftw3" = "no"; then
    echo "No FFTW3"
fi

if test "$blas" = "no"; then
    echo "No BLAS was found - Linpack will not be built"
fi

# Print summary of what environment variables to export
echo ""
echo "--------------------------------------------------"
echo "Please export the following environment variables:"
echo ""
echo "CBENCHOME"
echo "CBENCHTEST"
echo "MPI_HOME"
echo "COMPILERCOLLECTION"
if test x"$BLAS_LIB" != x; then
    echo "BLASLIB=$BLAS_PATH"
fi
if test x"$FFTW2_LIB" != x; then
    echo "FFTW_LIB=$FFTW2_LIB"
    echo "FFTW_INCLUDE=$FFTW2_LIB/../include"
fi
if test x"$FFTW3_LIB" != x; then
    echo "FFTW_LIB=$FFTW3_LIB"
    echo "FFTW_INCLUDE=$FFTW3_LIB/../include"
fi
echo "--------------------------------------------------"
echo ""


