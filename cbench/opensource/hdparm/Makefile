include ../../make.def

VERSION=9.43
SRC=hdparm-$(VERSION)
TAR=$(SRC).tar.gz
URL="http://sourceforge.net/projects/hdparm/files/hdparm/$(TAR)"

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = src/hdparm

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC)
	make -C src CC=$(PLAINCC) > .make-$(SRC) 2>&1
	@touch $@

clean:
	-$(MAKE) -C src clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) $(TAR) src .make-$(SRC)

install uninstall: default
	$(do-$@)

