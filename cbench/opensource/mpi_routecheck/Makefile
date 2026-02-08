include ../../make.def

DEFINES = 
#DEFINES += -DNOalltoallv
LIBS = $(MPILIB) -lm

SRC = mpi_routecheck.c
EXEC = mpi_routecheck

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXEC) $(EXEC)-cpumask

default all: $(INSTALLTARGETS)

download:

$(EXEC): $(SRC) meminfo.o
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS) meminfo.o

$(EXEC)-cpumask: $(SRC) meminfo.o
	$(CC) $(CFLAGS) $(DEFINES) -DCPUAFFINITY -o $@ $< $(LIBS) meminfo.o

clean:
	rm -f *.o $(EXEC) $(EXEC)-cpumask

distclean: clean

install uninstall: default
	$(do-$@)
