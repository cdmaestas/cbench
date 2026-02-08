include ../../make.def

DEFINES = 
LIBS = $(MPILIB)

SRC = mpiGraph.c
EXEC = mpiGraph

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXEC) crunch_mpiGraph

default: $(EXEC)

$(EXEC): $(SRC)
	$(CC) -o $@ $<
#	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

dbg: debug
debug:
	$(CC) -g -O0 -o $(EXEC) $(SRC)

clean:
	rm -f *.o $(EXEC)

install uninstall: default
	$(do-$@)
