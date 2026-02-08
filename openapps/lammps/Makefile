include $(CBENCHOME)/make.def

SRC=lammps
TAR=$(SRC).tar.gz
URL=http://lammps.sandia.gov/tars/$(TAR)

# note - this make process will strip off Lammps version (date) from the extracted source directory

EXECS = $(SRC)/src/lmp_cbench
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

all: $(EXECS)

$(EXECS): $(SRC)
	$(MAKE) -C $(SRC)/lib/poems -f Makefile.cbench -j$(MAKE_JOBS)
	$(MAKE) -C $(SRC)/lib/meam -f Makefile.cbench
	$(MAKE) -C $(SRC)/lib/reax -f Makefile.cbench -j$(MAKE_JOBS)
	$(MAKE) -C $(SRC)/src yes-all
	$(MAKE) -C $(SRC)/src no-gpu
	$(MAKE) -C $(SRC)/src no-user-atc
	$(MAKE) -C $(SRC)/src no-user-cuda
	$(MAKE) -C $(SRC)/src cbench -j$(MAKE_JOBS)

$(SRC): $(TAR)
	-[ ! -d $(SRC) ] && tar zxf $(TAR)
	@-ls -d lammps-*
	@-mv lammps-* $(SRC)
	ln -sf $(SRC) src
	cd $(SRC)/src/MAKE; ln -sf ../../../Makefile.cbench .
	cd $(SRC)/lib/poems; ln -sf ../../../Makefile.cbench-poems Makefile.cbench
	cd $(SRC)/lib/meam; ln -sf ../../../Makefile.cbench-meam Makefile.cbench
	cd $(SRC)/lib/reax; ln -sf ../../../Makefile.cbench-reax Makefile.cbench
	touch $(SRC)

$(TAR) download:
	$(call download-wget-url,$(URL))
	-[ -e $(TAR) ] && touch $(TAR)

clean:
	-make -C $(SRC)/lib/poems -f Makefile.cbench clean
	-make -C $(SRC)/lib/meam -f Makefile.cbench clean
	-make -C $(SRC)/lib/reax -f Makefile.cbench clean
	-make -C $(SRC)/src clean-all
	-/bin/rm -f $(EXECS)

distclean:
	/bin/rm -rf $(TAR) $(SRC) src

install uninstall:
	$(do-$@)

include $(CBENCHOME)/make.inc
