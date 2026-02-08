include ../../make.def

DEFINES = 

# make sure we go to 2^26 (64MB) message size
#  can probably make it as large as we want now
LARGEDEFINES = "-DMAX_MSG_SIZE=(1<<26)"

CFLAGS += 
LIBS = $(MPILIB) -lm

SRC = mpi_tokensmash.c
EXECS = osu_bw osu_bibw osu_latency osu_bcast osu_mbw_mr large_osu_bw large_osu_bibw large_osu_latency large_osu_mbw_mr

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: $(EXECS)

download:

osu_bw: osu_bw.c 
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

osu_bibw: osu_bibw.c 
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

osu_mbw_mr: osu_mbw_mr.c
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

osu_latency: osu_latency.c 
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

osu_bcast: osu_bcast.c 
	$(CC) $(CFLAGS) $(DEFINES) -o $@ $< $(LIBS)

large_osu_bw: osu_bw.c
	$(CC) $(CFLAGS) $(LARGEDEFINES) -o $@ $< $(LIBS)

large_osu_bibw: osu_bibw.c
	$(CC) $(CFLAGS) $(LARGEDEFINES) -o $@ $< $(LIBS)

large_osu_latency: osu_latency.c
	$(CC) $(CFLAGS) $(LARGEDEFINES) -o $@ $< $(LIBS)

large_osu_mbw_mr: osu_mbw_mr.c
	$(CC) $(CFLAGS) $(LARGEDEFINES) -o $@ $< $(LIBS)

clean:
	rm -f *.o $(EXECS)

distclean: clean

install uninstall: default
	$(do-$@)
