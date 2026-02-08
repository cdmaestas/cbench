include $(CBENCHOME)/make.def

SRC=sweep3d-2.2b
TAR=sweep3d-2.2b.tar.gz
URL=http://www.ccs3.lanl.gov/pal/software/sweep3d/$(TAR)


EXECS = $(SRC)/sweep
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)


all: $(SRC) src/Makefile
	make -C $(SRC) -j$(MAKE_JOBS)

src/Makefile:
	cd src && ./configure --with-mpi F77=$(F90) CC=$(CC) CPP="cpp" FFLAGS="$(FFLAGS)" CFLAGS="$(CFLAGS)"

$(SRC) src: $(TAR)
	-[ ! -d $(SRC) ] && tar zxf $(TAR)
	ln -sf $(SRC) src
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
