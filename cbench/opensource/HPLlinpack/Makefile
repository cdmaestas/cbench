include ../../make.def

SRC=hpl-1.0
MPICH_CH=ch_shmem

ifeq ($(CBENCH_STANDALONE),yes)
  $(warning ================ STANDALONE MPI COMPILE)
  EXECS = hpl/bin/cbench/xhpl.$(MPICH_CH)
  default_tgt := local
  MPIHOME = $(CBENCHOME)/opensource/mpich
  MPIBINNAME = bin
else
  #$(warning ================ NORMAL MPI COMPILE)
  EXECS = hpl/bin/cbench/xhpl
  default_tgt := hpl/bin/cbench/xhpl
endif

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

.SUFFIXES: .so.gz .so.gz

%.gz: %.so.gz
	gunzip $<

%.so.gz: %.so
	gzip $<

ZIPPED_LIBS = $(wildcard *.gz)
UNZIPPED_LIBS = $(patsubst %.so.gz,%.gz,$(ZIPPED_LIBS))

CLEAN_LIBS_UNZIPPED = $(wildcard *.so)
CLEAN_LIBS_ZIPPED = $(patsubst %.so,%.so.gz,$(CLEAN_LIBS_UNZIPPED))

default: linpack-size $(default_tgt)

download:

linpack-size: linpack-size.c
	$(CC) $(OPTFLAGS) -o $@ linpack-size.c -lm

xerbla:
	$(CC) $(OPTFLAGS) -c xerbla.c
	#$(F77) $(OPTFLAGS) -c xerbla.f

hpl/bin/cbench/xhpl:
	$(MAKE) linpack >> .make-$(SRC) 2>&1

linpack: xerbla
	$(MAKE) -C hpl >> .make-$(SRC) 2>&1

local: linpack
	[ -e hpl/bin/cbench/xhpl ] && /bin/mv -f hpl/bin/cbench/xhpl hpl/bin/cbench/xhpl.ch_shmem 

clean:
	/bin/rm -f linpack-size	
	$(MAKE) -C hpl make.def > .make-$(SRC) 2>&1
	$(MAKE) -C hpl clean_arch_all > .make-$(SRC) 2>&1
	/bin/rm -rf hpl/lib hpl/bin

distclean: clean
	rm -f .make-$(SRC)

install uninstall: default
	$(do-$@)
