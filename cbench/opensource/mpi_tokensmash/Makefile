include ../../make.def

DEFINES = 
CFLAGS += 
LIBS = $(MPILIB) -lm

SRC = mpi_tokensmash.c
EXEC = mpi_tokensmash

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
