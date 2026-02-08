include ../../make.def

SRC=IMB-MPI1

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = src/IMB-MPI1

default all: src/IMB-MPI1

download:

src/IMB-MPI1: src/make_cbench
	$(MAKE) -C src -f make_cbench all >> .make-$(SRC) 2>&1

src/make_cbench:
	cp -f make_cbench src/make_cbench 

clean:
	cp -f make_cbench src/make_cbench
	$(MAKE) -C src -f make_cbench $@ > .make-$(SRC) 2>&1
	rm -f src/make_cbench .make-$(SRC)

distclean: clean

install uninstall: default
	$(do-$@)
