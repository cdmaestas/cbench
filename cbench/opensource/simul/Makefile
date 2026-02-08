include ../../make.def

SRC=simul-1.14
TAR=$(SRC).tar.gz
URL=https://computing.llnl.gov/code/sio/tarballs/$(TAR)

EXECS = simul
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default all normal: $(EXECS)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

$(EXECS): $(SRC)
	$(CC) $(CFLAGS) -o simul $(SRC)/simul.c

clean:
	/bin/rm -f simul

distclean: clean
	/bin/rm -rf $(SRC) $(TAR) src

install uninstall: default
	$(do-$@)
