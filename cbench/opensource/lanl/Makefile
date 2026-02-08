include $(CBENCHOME)/make.def

MPICH_CH=ch_shmem

ifeq ($(CBENCH_STANDALONE),yes)
  $(warning ================ STANDALONE MPI COMPILE)
  EXECS = psnap-1.0/psnap.$(MPICH_CH)
  default_tgt := local
  MPIHOME = $(CBENCHOME)/opensource/mpich
  MPIBINNAME = bin
else
  #$(warning ================ NORMAL MPI COMPILE)
  EXECS = psnap-1.0/psnap
  default_tgt := normal
endif

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: $(default_tgt)

download:

normal: psnap

psnap: psnap-1.0/psnap

psnaplocal local: psnap-1.0/psnap.$(MPICH_CH)

psnap-1.0/psnap:
	$(MAKE) -C psnap-1.0 > .make-$(SRC) 2>&1

psnap-1.0/psnap.$(MPICH_CH): psnap-1.0/psnap
	/bin/mv -f psnap-1.0/psnap psnap-1.0/psnap.$(MPICH_CH)

clean: smallclean
	/bin/rm -f $(EXECS)

distclean: clean
	rm -f .make-$(SRC)

smallclean:
	$(MAKE) -C psnap-1.0 clean > .make-$(SRC) 2>&1
	
install uninstall: default
	$(do-$@)
