include ../../make.def

VERSION=1.8.4
SRC=mdtest-$(VERSION)
TAR=$(SRC).tgz
URL="http://sourceforge.net/projects/mdtest/files/mdtest%20latest/$(SRC)/$(TAR)"

EXECS = $(SRC)/mdtest
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default all normal: $(EXECS)

$(EXECS): $(SRC)
	$(MAKE) CC=$(CC) -C $(SRC) > .make-$(SRC) 2>&1

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

clean:
	-$(MAKE) -C src clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) $(TAR) src .make-$(SRC) ._mdtest-1.8.4

install uninstall: default
	$(do-$@)

