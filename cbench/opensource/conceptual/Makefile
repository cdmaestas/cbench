include ../../make.def

VERSION=1.4
SRC=conceptual-$(VERSION)
TAR=$(SRC).tar.gz
URL="http://sourceforge.net/projects/conceptual/files/conceptual/$(VERSION)/$(TAR)"

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
	cd src && MPICC=$(MPIHOME)/bin/mpicc ./configure --prefix=$(CBENCHTEST)/$(SRC) > ../.configure-$(SRC) 2>&1
	@touch $@

.make-$(SRC): .configure-$(SRC)
	@echo "Compiling $(SRC)"
	$(MAKE) -C src > .make-$(SRC) 2>&1; touch .configure-$(SRC)
	@touch $@

clean:
	@if [ -f src/Makefile ] ; then $(MAKE) -C src clean > .make-$(SRC) 2>&1; fi
	rm -f .make-$(SRC) .configure-$(SRC)

distclean:
	rm -fr .make-$(SRC) .configure-$(SRC) src $(TAR) $(SRC)

install: .make-$(SRC)
	@echo "Installing $(SRC)"
	cd src && make install >> ../.make-$(SRC) 2>&1
