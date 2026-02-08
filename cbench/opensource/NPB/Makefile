include ../../make.def

INSTALLDIR = $(bin_dir)
#INSTALLTARGETS = $(shell find bin -type f)

SRC=NPB3.2.1
TAR=$(SRC).tar.gz

MPIDIR=$(SRC)/NPB3.2-MPI
SERDIR=$(SRC)/NPB3.2-SER

default all: serial mpi

download:

$(MPIDIR)/config/suitedef:
	./gen_suitedef --nasdir $(MPIDIR) --maxprocs $(MAXPROCS)

$(SERDIR)/config/suitedef:
	./gen_suitedef --nasdir $(SERDIR) --serial

serial:
	@echo "Compiling $(SRC) $@"
	$(MAKE) serial_real >> .make-$(SRC) 2>&1
	@touch serial

mpi: 
	@echo "Compiling $(SRC) $@"
	$(MAKE) mpi_real >> .make-$(SRC) 2>&1
	@touch mpi

serial_real: .patched $(SERDIR)/config/suitedef
	@ if [ ! -d bin ] ; then mkdir bin ; fi
	cd $(SERDIR)/config; ln -sf ../../../make.def .
	$(MAKE) CC=$(PLAINCC) F77=$(PLAINF77) F90=$(PLAINF90) -C $(SERDIR) suite

mpi_real: .patched $(MPIDIR)/config/suitedef
	@ if [ ! -d bin ] ; then mkdir bin ; fi
	cd $(MPIDIR)/config; ln -sf ../../../make.def .
	$(MAKE) -C $(MPIDIR) suite

$(SRC): $(TAR)
	$(call untar-src, $(TAR))
	rm -f .patched
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.patched: $(SRC)
	for patch in *.patch ; do \
           cd $(SRC); \
           echo "Applying patch [ $$patch ]"; \
           patch -p1 <../$$patch; \
           cd - ; \
        done
	@touch .patched

clean: cleanserial cleanmpi
	rm -f .make-$(SRC)

cleanserial:
	-$(MAKE) -C $(SERDIR) clean >> .make-$(SRC) 2>&1 ; /bin/rm -f $(SERDIR)/config/suite.def 
	/bin/rm -f bin/*.[ABCDSW] serial

cleanmpi:
	-$(MAKE) -C $(MPIDIR) clean >> .make-$(SRC) 2>&1; /bin/rm -f $(MPIDIR)/config/suite.def >> .make-$(SRC) 2>&1
	/bin/rm -f bin/*.[ABCDSW].* mpi

distclean:
	/bin/rm -rf $(SRC) .patched src bin serial mpi .make-$(SRC)

install uninstall: default
	$(do-$@)

