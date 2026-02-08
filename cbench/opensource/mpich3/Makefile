include ../../make.def

VERSION = 3.0.4
SRC=mpich-$(VERSION)
TAR=$(SRC).tar.gz
URL=http://www.mpich.org/static/downloads/$(VERSION)/$(TAR)

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
	(cd src && export CC=$(PLAINCC) && export F77=$(PLAINF77) && export FC=$(PLAINF77) && export CXX=$(PLAINCXX) && ./configure --prefix=$(CBENCHTEST)/$(SRC)-$(COMPILERCOLLECTION) > ../.configure-$(SRC) 2>&1)
	@touch $@

.make-$(SRC): .configure-$(SRC)
	@echo "Compiling $(SRC)"
	$(MAKE) -C src -j 3 > .make-$(SRC) 2>&1; touch .configure-$(SRC)
	@touch $@ 

clean: .configure-$(SRC)
	$(MAKE) -C src clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC) 

distclean:
	rm -fr .make-$(SRC) .configure-$(SRC) src $(TAR) $(SRC) .install-$(SRC)

.install-$(SRC): .make-$(SRC)
	@echo "Installing $(SRC)"
	$(MAKE) -C src PREFIX=$(CBENCHTEST)/$(SRC)-$(COMPILERCOLLECTION) install >> .make-$(SRC) 2>&1
	cd $(CBENCHTEST) && ln -sf $(SRC) mpich3
	@touch $@ 

install: .install-$(SRC)

reinstall: clean_install install

clean_install:
	rm -f .install-$(SRC)
