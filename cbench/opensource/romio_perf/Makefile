include ../../make.def

DEFINES = 
#DEFINES += -DNOalltoallv
LIBS = $(MPILIB)

SRC = perf.c
EXEC = perf

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXEC)

CFLAGS += -D_LARGEFILE_SOURCE -D_LARGEFILE64_SOURCE -D_FILE_OFFSET_BITS=64

$(EXEC): $(SRC)
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

clean:
	rm -f *.o $(EXEC)

install uninstall: default
	$(do-$@)
