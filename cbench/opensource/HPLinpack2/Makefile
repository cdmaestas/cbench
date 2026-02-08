# Makefile for HPLinpack 2.0 for Cbench

include ../../make.def

export CFLAGS

SRC=hpl-2.0
TAR=$(SRC).tar.gz
URL=http://www.netlib.org/benchmark/hpl/$(TAR)
MPICH_CH=ch_shmem
HPL2=$(CBENCHOME)/opensource/HPLinpack2

ifeq ($(CBENCH_STANDALONE),yes)
  $(warning ================ STANDALONE MPI COMPILE)
  EXECS = /src/bin/cbench/xhpl2.$(MPICH_CH)
  default_tgt := local
  MPIHOME = $(CBENCHOME)/opensource/mpich
  MPIBINNAME = bin
else
  # NORMAL MPI COMPILE
  EXECS = src/bin/cbench/xhpl2
  default_tgt := src/bin/cbench/xhpl2
endif

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: $(default_tgt) 

all: linpack clean local

src/bin/cbench/xhpl2:
	$(MAKE) linpack

linpack: $(SRC) xerbla
	$(MAKE) -C $(SRC) arch=cbench >> .make-$(SRC) 2>&1
	[ -e src/bin/cbench/xhpl ] && /bin/mv src/bin/cbench/xhpl src/bin/cbench/xhpl2

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	ln -sf $(HPL2)/Make.cbench $(HPL2)/$(SRC)/Make.cbench
	@[ -d $@ ] && touch $@

xerbla: 
	$(CC) $(OPTFLAGS) -c xerbla.c

# This is a special compile that uses a local Cbench version of MPICH
# using the $(MPICH_CH) device.  We use this to compile a version of 
# hpl that will run just on a single node.
local: linpack
	[ -e $(HPL2)/src/bin/cbench/xhpl2 ] && /bin/mv -f $(HPL2)/src/bin/cbench/xhpl2 $(HPL2)/src/bin/cbench/xhpl2.$(MPICH_CH)

clean:
	-[ -d $(SRC) ] && $(MAKE) -C $(SRC) clean_arch_all arch=cbench
	/bin/rm -rf $(HPL2)/src/lib/* $(HPL2)/src/bin/*
	/bin/rm -f xerbla.o .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) xerbla.o src $(TAR) .make-$(SRC)

install uninstall: default
	$(do-$@)
