include ../../make.def

SRC=hwloc-1.2
TAR=$(SRC).tar.bz2
URL="http://www.open-mpi.org/software/hwloc/v1.2/downloads/$(TAR)"

EXECS = src/utils/lstopo

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: all

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

all: $(SRC) src/Makefile
	$(MAKE) -C src

src/Makefile: 
	cd src ; CC=$(CC) CFLAGS='$(CFLAGS)' ./configure

clean:
	$(MAKE) -C src clean

distclean:
	-/bin/rm -rf $(SRC) $(TAR) src

install uninstall: default
	$(do-$@)

