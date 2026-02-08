include ../../make.def

SRC=lmbench3
TAR=$(SRC).tar.gz
URL="http://www.bitmover.com/lmbench/$(TAR)"

EXECS = lat_mem_rd

INSTALLDIR = $(hwtest_bin_dir)
INSTALLTARGETS = src/bin/x86_64-linux-gnu/$(EXECS)

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	patch -p1 -d src < lmbench3.cbench.patch
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC)
	$(MAKE) CC=$(CC) CFLAGS='$(CFLAGS)' -C src > .make-$(SRC) 2>&1
	@touch $@

clean:
	-$(MAKE) -C src clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) $(TAR) src .make-$(SRC)

install uninstall: default
	$(do-$@)

