include ../../make.def

SRC = nodeperf.c nodeperf2.c xerbla.c dclock.c
OBJS = xerbla.o dclock.o

OPFLAGS += -g

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = nodeperf nodeperf2-nompi nodeperf2

NODEPERFILE=$(CBENCHOME)/opensource/HPLintel/src/../mp_linpack/nodeperf.c

default: $(INSTALLTARGETS)

# standard Intel nodeperf
nodeperf: $(SRC) $(OBJS)
	$(CC) $(OPTFLAGS) -o $@ nodeperf.c $(OBJS) $(BLASLIB)

# modified nodeperf with MPI and more runtime options
nodeperf2: $(SRC) $(OBJS)
	$(CC) $(OPTFLAGS) -o $@ nodeperf2.c $(OBJS) $(BLASLIB)

# modified nodeperf without MPI and more runtime options
nodeperf2-nompi: $(SRC) $(OBJS)
	$(PLAINCC) $(OPTFLAGS) -DNOMPI -o $@ nodeperf2.c $(OBJS) $(BLASLIB)

xerbla.o:
	$(PLAINCC) $(OPTFLAGS) -c xerbla.c

dclock.o: dclock.c
	$(PLAINCC) $(OPTFLAGS) -D_LINUX -D_GCC_ -DGETCPUFREQUENCY=get_frequency -DDSECND=dsecnd_ -c dclock.c

%.o: %.c
	$(CC) $(OPTFLAGS) -c $<

nodeperf.c:
	@if [ ! -f $(NODEPERFILE) ]; then \
		make -C $(CBENCHOME)/opensource/HPLintel extractnodeperf; \
	fi
	cp $(NODEPERFILE) $(CBENCHOME)/opensource/nodeperf

# nodeperf2 is a customization and tweaking of Intel's nodeperf source that was 
# done circa 2007 based on a much earlier version of nodeperf. i don't think we
# can put the nodeperf2.c source on the Cbench Sourceforge mirror because of 
# licensing, so we instead are distributing a patch to get from the Intel
# distributed version to nodeperf2.
nodeperf2.c: nodeperf.c
	@cp nodeperf.c nodeperf2.c; \
	patch -p0 < n2.patch; \
	if [ $$? -ne 0 ]; then \
		echo "WARNING: Could not patch nodeperf.c to make nodeperf2.c"; \
	    /bin/rm -f nodeperf2.c; \
	else \
	    echo "Patched nodeperf.c to make nodeperf2.c"; \
	fi

download: nodeperf.c nodeperf2.c

clean:
	rm -f $(INSTALLTARGETS) nodeperf.o nodeperf2.o $(OBJS)

distclean: clean
	rm -f nodeperf.c nodeperf2.c nodeperf2.c.orig

install uninstall: default
	$(do-$@)
