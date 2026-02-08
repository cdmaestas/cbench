include ../../make.def

DEFINES = 
LIBS = $(MPILIB)

EXEC = mpi_overhead mpi_overhead_bcast mpi_overhead_time

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXEC)

default: $(EXEC)

download:

mpi_overhead: mpi_overhead.o meminfo.o
	$(CC) $(COMMON_FLAGS) $(DEFINES) -o $@ $< $(LIBS) meminfo.o

mpi_overhead_bcast: mpi_overhead_bcast.o meminfo.o
	$(CC) $(COMMON_FLAGS) $(DEFINES) -o $@ $< $(LIBS) meminfo.o

mpi_overhead_time: mpi_overhead_time.o 
	$(CC) $(COMMON_FLAGS) $(DEFINES) -o $@ $< $(LIBS) 

clean:
	rm -f *.o $(EXEC)

distclean: clean

install uninstall: default
	$(do-$@)
