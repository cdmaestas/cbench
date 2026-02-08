include $(CBENCHOME)/make.def

# https://asc.llnl.gov/computing_resources/purple/archive/benchmarks/sppm/sppm1.1.tar
SRC=sppm
TAR=sppm1.1.tar
URL=https://asc.llnl.gov/computing_resources/purple/archive/benchmarks/sppm/$(TAR)


EXECS = $(SRC)/run/sppm
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

all: $(SRC)
	make -C $(SRC) -f Makefile.cbench -j$(MAKE_JOBS)

$(SRC) src: $(TAR)
	[ ! -d $(SRC) ] && tar xf $(TAR)
	ln -sf $(SRC) src
	cd $(SRC); mv iq.h b_iq.h
	cd $(SRC); mv sync.h b_sync.h
	cd $(SRC); ln -sf ../Makefile.cbench .
	cd $(SRC); ln -sf ../iq.cbench.h ./iq.h
	cd $(SRC); ln -sf ../sync.cbench.h ./sync.h
	touch $(SRC)

$(TAR) download:
	$(call download-wget-url,$(URL))
	-[ -e $(TAR) ] && touch $(TAR)

clean:
	make -C $(SRC) clean

distclean:
	/bin/rm -rf $(TAR) $(SRC) src

install uninstall:
	$(do-$@)

include $(CBENCHOME)/make.inc
