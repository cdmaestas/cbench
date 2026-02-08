include ../../make.def

VERSION=1.5
SRC=perftest-$(VERSION)
TAR=$(SRC).tar.gz
URL="http://ftp.mcs.anl.gov/pub/mpi/tools/$(TAR)"

EXECS = src/stress
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

# since the perftest configure snapshots the Cbench COMPILERCOLLECTION
# and MPIHOME state, if the COMPILERCOLLECTION changes and perftest has
# already been configured, we need to force a reconfigure
#ifeq ($(wildcard .config), .config)
#ifneq ($(shell cat .config), ${COMPILERCOLLECTION})
#	@echo "COMPILERCOLLECTION changed, forcing reconfigure.."
#	@/bin/rm -f .config src/Makefile $(EXECS)
#	$(MAKE)
#endif
#endif

default: $(EXECS)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

src/Makefile: $(SRC)
	echo ${COMPILERCOLLECTION} > src/.config
	cd src && MPICC=$(CC) MPIF77=$(F77) CC=$(PLAINCC) F77=$(PLAINF77) CFLAGS='$(CFLAGS)' FFLAGS='$(FFLAGS)' ./configure > ../.configure-$(SRC) 2>&1
	@if [ -f $(SRC)/Makefile ]; then \
		sed -i 's/-O4 -Ofast//' $(SRC)/Makefile; \
	fi
	touch $@

src/stress: src/Makefile
	make -C src stress > .make-$(SRC) 2>&1

clean:
	-$(MAKE) -C src clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) $(TAR) src .configure-$(SRC) .make-$(SRC)

install uninstall: default
	$(do-$@)
