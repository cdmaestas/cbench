include ../../make.def

MEMORY = $(shell $(CBENCHOME)/sbin/get_clusterdef_param --param memory_per_processor | sed 's/\..*//')
#MEMORY = 1024

DEFINES = -DMEMORY_PER_PROCESSOR=$(MEMORY) -DPRINTLEVEL=1
#DEFINES += -DNOalltoallv
CFLAGS += 
LIBS = $(MPILIB) -lm

SRC = b_eff.c
EXEC = b_eff

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
