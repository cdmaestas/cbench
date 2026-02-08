include ../../make.def

SRC=miranda_io-1.0.1
TAR=$(SRC).tar.gz
URL=https://computing.llnl.gov/code/sio/tarballs/$(TAR)

EXECS = miranda_io
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default all normal: $(EXECS)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	patch -p0 < fix-compile.patch
	patch -p0 < swl.patch
	@[ -d $@ ] && touch $@

$(EXECS): $(SRC)
	$(F90) $(FFLAGS) -o miranda_io $(SRC)/miranda_io.f90 

clean:
	/bin/rm -f $(EXECS)

distclean: clean
	/bin/rm -rf $(SRC) $(TAR) src 

install uninstall: default
	$(do-$@)
