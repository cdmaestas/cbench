include ../../make.def

DEFINES = 
#DEFINES += -DNOalltoallv
LIBS = $(MPILIB)

SRC = mpi_latency.c
EXEC = mpi_latency

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXEC)

default: $(EXEC)

download:

$(EXEC): $(SRC)
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

clean:
	rm -f *.o $(EXEC)

distclean: clean

install uninstall: default
	$(do-$@)

