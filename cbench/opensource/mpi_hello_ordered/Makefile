include ../../make.def

DEFINES = 
LIBS = $(MPILIB)

SRC = mpi_hello_ordered.c
EXEC = mpi_hello_ordered

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
