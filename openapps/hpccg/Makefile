include $(CBENCHOME)/make.def

export CFLAGS

SRC=HPCCG-0.4
TAR=$(SRC).tar.gz
URL=http://www.cs.sandia.gov/~maherou/$(TAR)

EXECS = $(SRC)/test_HPCCG
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

all normal: $(SRC)
	cd $(SRC) && ln -sf ../Makefile.cbench Makefile.cbench
	$(MAKE) CXX=$(CXX) LINKER=$(CXX) -C $(SRC) -f Makefile.cbench -j$(MAKE_JOBS)

$(SRC): $(TAR)
	-[ ! -d $(SRC) ] && tar zxf $(TAR)
	ln -sf $(SRC) src

$(TAR) download:
	$(call download-wget-url,$(URL))
	-[ -e $(TAR) ] && touch $(TAR)

clean:
	[ -d $(SRC) ] && $(MAKE) -C $(SRC) -f Makefile.cbench clean || :

distclean:
	/bin/rm -rf $(SRC) $(TAR) src

install uninstall:
	$(do-$@)

include $(CBENCHOME)/make.inc
