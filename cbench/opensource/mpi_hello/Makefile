include ../../make.def

DEFINES = 
#DEFINES += -DNOalltoallv
LIBS = $(MPILIB) -lm

SRC = mpi_hello.c
EXEC = mpi_hello

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
