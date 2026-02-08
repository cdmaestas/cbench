##### User configurable options #####
include ../../make.def

#CC          = $(CC)
#CCC         = $(CCC)
#F77         = $(F77)
#F90         = $(F90)
CLINKER     = $(CC)
CCLINKER    = $(CCC)
FLINKER     = $(F77)
F90LINKER   = $(F90)
MAKE        = make --no-print-directory
SHELL       = /bin/sh
#

### End User configurable options ###

LIBS =
FLIBS =
EXECS = cpi pi3 cpip pi3p 

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: cpi pi3 cpip pi3p 

download:

# 
# The cp for pi3f90 is needed because different Fortran 90 compilers
# accept *different* suffixes.
# pi3f90 also wants an MPI module.  If modules not supported, don't 
# try to build pi3f90
all: $(EXECS)
	@if [ "1" = 1 -a -s simpleio.c ] ; then $(MAKE) simpleio ; fi
	@if [ "1" = 1 ] ; then $(MAKE) hello++ ; fi
	@if [ "0" = 0 ] ; then  \
		$(MAKE) pi3 ; \
		$(MAKE) pi3p; \
	fi
	@if [ "0" = 0 ] ; then $(MAKE) cpilog ; fi
	@if [ -n "-I" ] ; then \
	    if [ ! -s pi3f90.f90 ] ; then \
		cp pi3f90.f90 pi3f90.f90 ; fi ; \
	    $(MAKE) pi3f90 ; fi
	@if [ "gcc" != "ignore" ] ; then \
	    MPICH_USE_SHLIB="yes" ; export MPICH_USE_SHLIB ; \
	    $(MAKE) clean ; $(MAKE) cpi  ; \
	    if [ "0" = 0 ] ; then $(MAKE) pi3 ; fi ; \
	    if [ -n "-I" ] ; then $(MAKE) pi3f90 ; fi ; \
	fi

cpi: cpi.o 
	$(CLINKER) -o cpi cpi.o -lm
cpip: cpip.o 
	$(CLINKER) -o cpip cpip.o -lm

cpilog: cpilog.o 
	$(CLINKER) -o cpilog cpilog.o -lmpe -lm

#
# This uses MPICH's -mpilog option to the mpicc command to add the automatic
# logging interface.
cpiwithlog: cpi.o
	$(CLINKER) -o cpiwithlog cpi.o -mpilog -lm

pi3: pi3.o 
	$(FLINKER) -o pi3 pi3.o $(FLIBS)
pi3p: pi3p.o 
	$(FLINKER) -o pi3p pi3p.o $(FLIBS)

# Some Fortran 90 compilers do not accept a .f90 suffix (xlf90 for one)
pi3f90.o: pi3f90.f90
	$(F90) $(FFLAGS) -c pi3f90.f90
pi3f90: pi3f90.o 
	$(F90LINKER) -o pi3f90 pi3f90.o $(FLIBS)

#
# Here are the rules for the optional package examples (ROMIO/C++)
simpleio: simpleio.o
	$(CLINKER) -o simpleio simpleio.o 
hello++: hello++.o
	$(CCLINKER) -o hello++ hello++.o
hello++.o: hello++.cc
	$(CCC) -c hello++.cc

#
# The Solaris C++ compiler creates a directory containing miscellaneous
# data.  The action is not documented in the Solaris CC man pages
# IRIX C++ creates ii_files
# pgCC creates .ii and .ti files
# We also remove any copy of pi3f90 that is created (e.g., pi3f90.f; pi3f90.f90
# is the master file)
clean:
	-/bin/rm -f *.o *~ PI* $(EXECS) pi3 simpleio hello++ pi3f90 cpilog
	-/bin/rm -rf SunWS_cache ii_files pi3f90.f pi3p cpip *.ti *.ii

distclean: clean

.c.o:
	$(CC) $(CFLAGS) -c $<
.f.o:
	$(F77) $(FFLAGS) -c $<
.f90.o:
	$(F90) $(FFLAGS) -c $<
.SUFFIXES: .f90

install uninstall: default
	$(do-$@)
