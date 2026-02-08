include ../../make.def

VERSION=2.29
SRC=pdsh-$(VERSION)
TAR=$(SRC).tar.bz2
#URL="http://sourceforge.net/projects/pdsh/files/pdsh/pdsh-$(VERSION)/$(TAR)"
URL="http://pdsh.googlecode.com/files/$(TAR)"

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = src/src/pdsh/pdsh

default: .make-$(SRC)

download: $(TAR) 

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.configure-$(SRC): $(SRC)
	@echo "Configuring $(SRC)"
	cd src && ./configure --prefix=$(CBENCHTEST)/$(SRC) --enable-static --enable-static-modules --with-ssh --with-exec --with-readline --without-pam > ../.configure-$(SRC) 2>&1
	@touch $@

.make-$(SRC): .configure-$(SRC)
	@echo "Compiling $(SRC)"
	$(MAKE) -C src CC=$(PLAINCC) > .make-$(SRC) 2>&1; touch .configure-$(SRC)
	@touch $@

clean:
	[ -f src/Makefile ] && $(MAKE) -C src clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC) .configure-$(SRC)

distclean:
	rm -fr .make-$(SRC) .configure-$(SRC) src $(TAR) $(SRC) .install-$(SRC)

.install-$(SRC): .make-$(SRC)
	@echo "Installing $(SRC)"
	@$(MAKE) -C src install >> .make-$(SRC) 2>&1
	@for progs in dshbak  pdcp  pdsh  rpdcp; do \
		ln -sf $(CBENCHTEST)/$(SRC)/bin/$$progs $(CBENCHTEST)/sbin/$$progs; \
	done
	@touch $@

install: .install-$(SRC)

reinstall: clean_install install

clean_install:
	rm -f .install-$(SRC)
