include $(CBENCHOME)/make.def

SRC=AMG2006
TAR=AMG2006_v1.0.tar.gz
URL=https://asc.llnl.gov/sequoia/benchmarks/$(TAR)


EXECS = $(SRC)/test/amg2006
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

all: $(EXECS)

$(SRC)/test/amg2006: $(SRC)
	make CC=$(CC) -C $(SRC) veryclean
	$(MAKE) CC=$(CC) -C $(SRC) -j$(MAKE_JOBS)

$(SRC) src: $(TAR)
	-[ ! -d $(SRC) ] && tar zxf $(TAR)
	ln -sf $(SRC) src
	cd $(SRC); /bin/rm -f Makefile.include
	cd $(SRC); ln -sf ../Makefile.include .
	touch $(SRC)

$(TAR) download:
	$(call download-wget-url,$(URL))
	-[ -e $(TAR) ] && touch $(TAR)

clean:
	make CC=$(CC) -C $(SRC) veryclean

distclean:
	/bin/rm -rf $(TAR) $(SRC) src

install uninstall:
	$(do-$@)

include $(CBENCHOME)/make.inc
