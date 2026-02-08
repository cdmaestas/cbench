include ../../make.def

SRC=MATMULT
SRCTAR=MATMULT_GPL
TAR=$(SRCTAR).tar.gz
# no llnl site for this tarball yet
URL=http://cbench.org/common/tarballs/$(TAR)

EXECS = $(addprefix src/, mmc mmf) 
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

# turn on OpenMP support
COMMON_FLAGS += $(OPENMP_ENABLE)

# matmult needs both BLAS and LAPACK linkages, so depeneding on what
# blas lib we are using, we might also need lapack
WHICHBLAS = $(findstring goto,$(BLASLIB))
ifeq ($(WHICHBLAS),goto)
  LDFLAGS=../../second.o $(LAPACKLIB) $(BLASLIB) -lm
else
  LDFLAGS=$(BLASLIB) -lm
endif

  LDFLAGS=../../second.o $(LAPACKLIB) $(BLASLIB) -lm

ifeq ($(COMPILER),gcc)
 #LDFLAGS += -lg2c
endif

# this is for the second.c implicit rule to get the CC we want
CC=$(PLAINCC) 

default: $(EXECS)

$(EXECS): .make-$(SRC)
	@[ -x $@ ] && touch $@

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@/matmult src
	cd src; mv Makefile Makefile.orig;ln -s ../../Makefile.cbench Makefile
	@[ -d $@ ] && touch $@

.patched:
	@[ ! -f .patched ] && for patch in *.patch ; do \
           cd $(SRC); \
           echo "Applying patch [ $$patch ]"; \
           patch -p1 <../$$patch; \
           cd - ; \
        done
	@touch .patched

.make-$(SRC): $(SRC) .patched second.o
	@echo "Compiling $(SRC)"
	$(MAKE) FC=$(PLAINF90) CC=$(PLAINCC) CFLAGS="$(CFLAGS) -DDGEMM -DMXMD16 -DLINUX" \
		FFLAGS="$(FFLAGS) -DLINUX" LDFLAGS="$(LDFLAGS)" -C src > .make-$(SRC) 2>&1

clean:
	-$(MAKE) -C src clean > .make-$(SRC) 2>&1
	/bin/rm -f second.o .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) $(TAR) src second.o .patched .make-$(SRC)

install uninstall: default
	$(do-$@)
