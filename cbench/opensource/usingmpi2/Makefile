include ../../make.def

VERSION=2
SRC=UsingMPI$(VERSION)
TAR=$(SRC).tar.gz
URL="http://ftp.mcs.anl.gov/pub/mpi/usingmpi2/$(TAR)"

EXECS = src/stress
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))
	@touch $@

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.configure-$(SRC): $(SRC)
	@echo "Configuring $(SRC)"
	cd src && MPICC=$(CC) MPIF77=$(F77) CC=$(PLAINCC) F77=$(PLAINF77) CFLAGS='$(CFLAGS)' FFLAGS='$(FFLAGS)' ./configure  --with-lammpi=$(MPIHOME) > ../.configure-$(SRC) 2>&1
	@touch $@

.make-$(SRC): .configure-$(SRC)
	@echo "Compiling $(SRC)"
	$(MAKE) -C src > .make-$(SRC) 2>&1; touch .configure-$(SRC)
	@touch $@

clean:
	@if [ -f src/Makefile ] ; then $(MAKE) -C src clean > .make-$(SRC) 2>&1; fi
	rm -f .make-$(SRC) .configure-$(SRC)

distclean:
	rm -fr .make-$(SRC) .configure-$(SRC) src $(TAR) $(SRC)

install: .make-$(SRC)
	@echo "Installing $(SRC)"
	cd src && make install >> ../.make-$(SRC) 2>&1
	@for progs in dshbak  pdcp  pdsh  rpdcp; do \
		ln -sf $(CBENCHTEST)/$(SRC)/bin/$$progs $(CBENCHTEST)/sbin/$$progs; \
	done

