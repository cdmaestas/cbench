include ../../make.def

DEFINES = 
CFLAGS += 
LIBS =

SRC = mpi_slowcpu.c
EXEC = mpi_slowcpu

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
