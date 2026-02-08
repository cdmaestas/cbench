include ../../make.def

SRC=hpcc-1.4.2
TAR=$(SRC).tar.gz
HPL=$(SRC)/hpl
MPICH_CH=ch_shmem
URL=http://icl.cs.utk.edu/projectsfiles/hpcc/download/$(TAR)

# hpcc.ch_shmem won't exist for the normal case, so make install will print an error
ifeq ($(CBENCH_STANDALONE),yes)
  $(warning ================ STANDALONE MPI COMPILE)
  EXECS = $(SRC)/hpcc.$(MPICH_CH)
  default_tgt := local
  MPIHOME = $(CBENCHOME)/opensource/mpich
  MPIBINNAME = bin
else
  #$(warning ================ NORMAL MPI COMPILE)
  EXECS = $(SRC)/hpcc
  default_tgt := normal
endif
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: $(default_tgt)

all: normal clean local

# the normal compile using make.def stuff
normal: $(SRC) .patched .make.def xerbla.o
	cd $(SRC); ln -sf $(CBENCHOME)/make.def
	cd $(HPL)/lib/arch/build; ln -sf $(CBENCHOME)/make.def make.def
	$(MAKE) -C $(SRC) arch=cbench > .make-$(SRC) 2>&1
	@touch .make.def
	@touch $@ 

debug: $(SRC) .patched .debugpatched .make.def xerbla.o
	cd $(SRC); ln -sf $(CBENCHOME)/make.def
	cd $(HPL)/lib/arch/build; ln -sf $(CBENCHOME)/make.def make.def
	$(MAKE) -C $(SRC) arch=cbench > .make-$(SRC) 2>&1
	@touch .make.def
	@touch $@

# This is a special compile that uses a local Cbench version of MPICH
# using the $(MPICH_CH) device. We use this to compile a version of HPCC that
# will run on just a single node.
local: normal
	/bin/mv -f $(SRC)/hpcc $(SRC)/hpcc.$(MPICH_CH)

xerbla.o:
	$(CC) $(OPTFLAGS) -c xerbla.c
	@[ -f $@ ] && touch $@

clean: 
	-[ -d $(SRC) ] && $(MAKE) -C $(SRC) arch=cbench clean > .make-$(SRC) 2>&1
	/bin/rm -f $(SRC)/hpcc.$(MPICH_CH)
	-[ -d $(HPL) ] && $(MAKE) -C $(HPL) arch=cbench clean_arch_all > .make-$(SRC) 2>&1
	/bin/rm -rf $(HPL)/bin
	-find ./$(SRC) -name make.def -print -exec /bin/rm -f {} \;
	-[ -d $(HPL) ] && cd $(HPL) && /bin/rm -f Make.cbench
	/bin/rm -f xerbla.o .make.def

distclean:
	/bin/rm -rf $(SRC) xerbla.o .patched src .debugpatched $(TAR) .make-$(SRC) debug normal .make.def

.make.def: $(SRC)
	[ -d $(HPL) ] && cd $(HPL) && ln -sf $(CBENCHOME)/opensource/hpcc/Make.cbench .
	[ -d $(HPL) ] && cd $(HPL) && ln -sf $(CBENCHOME)/make.def .
	[ -d $(SRC) ] && cd $(SRC); ln -sf $(CBENCHOME)/make.def
	@touch $@

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	rm -f .patched .debugpatched
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.patched:
	@for patch in *.patch ; do \
           cd $(SRC); \
           echo "Applying patch [ $$patch ]"; \
           patch -p1 <../$$patch; \
           cd - ; \
        done
	@touch $@

.debugpatched:
	@for patch in *.debugpatch ; do \
           cd $(SRC); \
           echo "Applying patch [ $$patch ]"; \
           patch -p1 <../$$patch; \
           cd - ; \
        done
	@touch $@

install uninstall: default
	$(do-$@)
