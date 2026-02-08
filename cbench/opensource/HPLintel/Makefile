# Makefile for HPLinpack 2.0 for Cbench

include ../../make.def

export CFLAGS
SRC=linpack_10.3.9
TAR=l_lpk_p_10.3.9.014.tgz
URL=http://registrationcenter.intel.com/irc_nas/2487/$(TAR)

MPICH_CH=ch_shmem
HPL2=$(CBENCHOME)/opensource/HPLintel

ifeq ($(CBENCH_STANDALONE),yes)
  $(warning ================ STANDALONE MPI COMPILE)
  EXECS = /src/bin/cbench/xhplintel.$(MPICH_CH)
  default_tgt := local
  MPIHOME = $(CBENCHOME)/opensource/mpich
  MPIBINNAME = bin
else
  # NORMAL MPI COMPILE
  EXECS = src/bin/cbench/xhplintel
  default_tgt := linpack
endif

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: $(default_tgt) 

all: linpack clean local

linpack: $(SRC) xerbla
	$(MAKE) -C $(SRC)/benchmarks/mp_linpack arch=cbench > .make-$(SRC) 2>&1
	[ -e src/bin/cbench/xhpl ] && /bin/mv src/bin/cbench/xhpl src/bin/cbench/xhplintel

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $(SRC)/benchmarks/mp_linpack src
	ln -sf $(HPL2)/Make.cbench $(HPL2)/$(SRC)/benchmarks/mp_linpack/Make.cbench
	@[ -d $@ ] && touch $@

xerbla: 
	$(CC) $(OPTFLAGS) -c xerbla.c

# This is a special compile that uses a local Cbench version of MPICH
# using the $(MPICH_CH) device.  We use this to compile a version of 
# hpl that will run just on a single node.
local: linpack
	/bin/mv -f $(HPL2)/src/bin/cbench/xhplintel $(HPL2)/src/bin/cbench/xhplintel.$(MPICH_CH)


extractnodeperf: $(SRC)

clean:
	-[ -d $(SRC) ] && $(MAKE) -C $(SRC)/benchmarks/mp_linpack clean_arch_all arch=cbench > .make-$(SRC) 2>&1
	/bin/rm -rf $(HPL2)/src/lib/* $(HPL2)/src/bin/*
	/bin/rm -f xerbla.o

distclean:
	/bin/rm -rf $(SRC) xerbla.o src $(TAR) .make-$(SRC)

install uninstall: default
	$(do-$@)
