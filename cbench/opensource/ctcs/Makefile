include ../../make.def

VERSION = 1.3.1pre1
SRC = ctcs-1.3.1-pre1
TAR = $(SRC).tgz
URL="http://sourceforge.net/projects/va-ctcs/files/va-ctcs/$(VERSION)/$(TAR)"

INSTALLDIR = $(hwtest_bin_dir)
INSTALLTARGETS = src/runin/memtst

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	mv ctcs-1.3.1pre1 $(SRC)
	ln -sf src.old src
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC)
	$(MAKE) -C src CC=$(PLAINCC) CLINKER='$(PLAINCC) $(LDFLAGS)' CFLAGS='$(CFLAGS)' MEMTST_CFLAGS='$(CFLAGS) $(NOUNROLL_FLAGS)' all > .make-$(SRC) 2>&1
	@touch $@

clean:
	-$(MAKE) -C src dist-clean > .make-$(SRC) 2>&1
	/bin/rm -rf src/runin/bin .make-$(SRC)

distclean: 
	rm -fr $(SRC) $(TAR) src .make-$(SRC) src.old/runin/bin


install uninstall: default
	$(do-$@)

