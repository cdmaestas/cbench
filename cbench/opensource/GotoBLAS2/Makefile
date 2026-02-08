include ../../make.def

VERSION = 1.13
NAME = GotoBLAS2
SRC = $(NAME)-$(VERSION)
TAR=$(SRC)_bsd.tar.gz

LAPACKTAR=lapack-3.1.1.tgz
LAPACKURL=http://www.netlib.org/lapack/$(LAPACKTAR)
LARGETAR=large.tgz
LARGEURL=http://www.netlib.org/lapack/timing/$(LARGETAR)
TIMINGTAR=timing.tgz
TIMINGURL=http://www.netlib.org/lapack/timing/$(TIMINGTAR)

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = src/OpenBLAS

default: .make-$(SRC)

download: $(LAPACKTAR) $(LARGETAR) $(TIMINGTAR)

$(TAR):

$(LAPACKTAR): 
	$(call download-curl-url,$(LAPACKURL))

$(LARGETAR): 
	$(call download-curl-url,$(LARGEURL))

$(TIMINGTAR): 
	$(call download-curl-url,$(TIMINGURL))

$(SRC): $(TAR) $(LAPACKTAR) $(LARGETAR) $(TIMINGTAR)
	$(call untar-src,$(TAR))
	mv GotoBLAS2 $(SRC)
	ln -sf $@ src
	[ -d $(SRC) ] && cd src && ln -sf ../$(LAPACKTAR) 
	[ -d $(SRC) ] && cd src && ln -sf ../$(LARGETAR) 
	[ -d $(SRC) ] && cd src && ln -sf ../$(TIMINGTAR) 
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC) 
	@echo "Compiling $(SRC)"
	@if [ $(ARCH) = "x86_64" ]; then cd src && /bin/sh ./quickbuild.64bit > ../.make-$(SRC) 2>&1; touch $@; \
	elif [ $(ARCH) = "x86" ]; then  cd src && /bin/sh ./quickbuild.32 > ../.make-$(SRC) 2>&1; touch $@; \
	else \
		echo No $(ARCH) found for $(SRC); \
		exit 1;	\
	fi

distclean: 
	rm -fr .make-$(SRC) ._$(SRC) $(SRC) src .install-$(SRC) $(LAPACKTAR) $(LARGETAR) $(TIMINGTAR)

clean:
	rm -fr .make-$(SRC) ._$(SRC) $(SRC) src

.install-$(SRC): .make-$(SRC)
	@echo "Installing $(SRC)"
	mkdir -p $(CBENCHTEST)/$(SRC)
	cd src && make PREFIX=$(CBENCHTEST)/$(SRC) install >> ../.make-$(SRC) 2>&1
	cd $(CBENCHTEST) && ln -sf $(SRC) GotoBLAS
	@touch $@

install: .install-$(SRC)

reinstall: clean_install install

clean_install:
	rm -f .install-$(SRC)
