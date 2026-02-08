include ../../make.def

SRC=STRIDE
SRCTAR=STRIDE_GPL
TAR=$(SRCTAR).tar.gz
URL=ftp://ftp.llnl.gov/outgoing/$(TAR)

EXECS = $(addprefix src/, cachec.Opt cachedot.Opt cache.Opt strid3c.Opt strid3.Opt striddot.Opt vecopc.Opt vecop.Opt)
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))
	@touch $@

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@/src src
	cd src && ln -sf ../../Makefile.cbench
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC)
	$(MAKE) -C src -f Makefile.cbench > .make-$(SRC) 2>&1
	@touch $@

clean:
	-$(MAKE) -C src -f Makefile.cbench clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) $(TAR) src .make-$(SRC)

install uninstall: default
	$(do-$@)
