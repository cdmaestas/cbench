include ../../make.def

SRC=llcbench
TAR=$(SRC).tar.gz
URL="http://icl.cs.utk.edu/projects/llcbench/$(TAR)"

INSTALLDIR = $(hwtest_bin_dir)
INSTALLTARGETS = src/cachebench/cachebench

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC)
	$(MAKE) -C src reconfig > .make-$(SRC) 2>&1
	$(MAKE) -C src linux-mpich >> .make-$(SRC) 2>&1
	$(MAKE) CB_CC=$(PLAINCC) CB_CFLAGS="$(CFLAGS)" -C src/cachebench cachebench >> .make-$(SRC) 2>&1
	@touch $@

#	$(MAKE) BB_CC=$(PLAINCC) BB_F77=$(PLAINF77) BB_LD=$(PLAINF77) BB_LIBS="$(BLASLIB) -lrt" CB_CC=$(PLAINCC) MP_MPI_CC=$(CC) -C src compile

clean:
	-$(MAKE) -C src clean >> .make-$(SRC) 2>&1; $(MAKE) -C src/cachebench clobber >> .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) $(TAR) .patched src .make-$(SRC)

install uninstall: default
	$(do-$@)

