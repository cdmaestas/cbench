include ../../make.def

VERSION=3.2.4
SRC=imb-$(VERSION)
TAR=$(SRC).tgz
#URL="http://software.intel.com/sites/products/mpi-benchmarks/$(TAR)"
URL="http://software.intel.com/sites/default/files/article/157859/$(TAR)"

EXEC = src/$(VERSION)/IMB-MPI1-$(VERSION)

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = src/$(VERSION)/IMB-MPI1-$(VERSION)

default: $(EXEC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	mv imb $(SRC)
	ln -sf $@/$(VERSION)/src src
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC)
	@echo "Compiling $(SRC)"
	$(MAKE) -C src CC=$(CC) > .make-$(SRC) 2>&1
	[ -x src/IMB-MPI1 ] && cp -f src/IMB-MPI1 src/IMB-MPI1-$(VERSION)
	@touch $@

$(EXEC): .make-$(SRC)

clean:
	-$(MAKE) -C src clean  > .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	rm -fr .make-$(SRC) src $(TAR) $(SRC)

install uninstall: default
	$(do-$@)

