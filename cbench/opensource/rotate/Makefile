include ../../make.def

DEFINES = 
CFLAGS += 
LIBS = $(MPILIB) -lm

EXEC = rotate rotate_latency

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXEC)

default: $(EXEC)

download: 

rotate: rotate.c
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

rotate_latency: rotate_latency.c
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

clean:
	rm -f *.o $(EXEC)

distclean: clean

install uninstall: default
	$(do-$@)
