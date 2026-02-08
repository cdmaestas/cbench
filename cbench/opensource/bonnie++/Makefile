# Makefile for bonnie++ for Cbench
include ../../make.def

#VERSION=1.03e
VERSION=1.97
SRC=bonnie++-$(VERSION)
TAR=$(SRC).tgz

#URL=http://www.coker.com.au/bonnie++/$(TAR)
URL="http://www.coker.com.au/bonnie++/experimental/$(TAR)"

EXEC = $(SRC)/bonnie++
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXEC)

CC = $(PLAINCC)
CXX = $(PLAINCXX)

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	[ -d $(SRC).1 ] && mv $(SRC).1 $(SRC)
	ln -sf $@ src
	@touch $@

.configure-$(SRC): $(SRC)
	@echo "Configuring $(SRC)"
#	cd src && ./configure > ../.configure-$(SRC) 2>&1
	@touch $@

.make-$(SRC): .configure-$(SRC)
	@echo "Make $(SRC)"
	$(MAKE) -C src CC=$(PLAINCC) CXX=$(PLAINCXX) bonnie++ > .make-$(SRC) 2>&1
	@touch $@ 

clean:
	-$(MAKE) -C src clean >> .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean: 
	/bin/rm -rf $(SRC) $(TAR) src .make-$(SRC) .configure-$(SRC)

install uninstall: default
	$(do-$@)

