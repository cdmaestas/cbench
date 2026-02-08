include ../../make.def

VERSION=source
SRC=dt-$(VERSION)
TAR=$(SRC).tar.gz
URL="http://www.scsifaq.org/RMiller_Tools/ftp/dt/$(TAR)"

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = src/dt

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	mv dt.d-WIP $(SRC)
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC)
	@echo "Compiling $(SRC)"
	cp -f src/Makefile.linux src/Makefile
	$(MAKE) -C src CC=$(PLAINCC) > .make-$(SRC) 2>&1

clean:
	-$(MAKE) -C src clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) $(TAR) src .make-$(SRC)

install uninstall: default
	$(do-$@)

