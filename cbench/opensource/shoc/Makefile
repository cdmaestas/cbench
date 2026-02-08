# Makefile for SHOC (Scalable Heterogeneous Computing Benchmark Suite, from ORNL) for Cbench

include ../../make.def

# check for CUDA environment and add flags
ifdef CUDALIB
  ifdef CUDAINC
      CFLAGS += -I$(CUDAINC)
      CXXFLAGS += -I$(CUDAINC)
      CPPFLAGS += -I$(CUDAINC)
      LDFLAGS += -L$(CUDALIB)
      LIBS += -L$(CUDALIB)
      CONFIGPARAMS += --with-cuda
  endif
endif

# Check for OpenCL Environment and add flags
ifdef OPENCLLIB
  ifdef OPENCLINC
      CFLAGS += -I$(OPENCLINC)
      CXXFLAGS += -I$(OPENCLINC)
      CPPFLAGS += -I$(OPENCLINC)
      LDFLAGS += -L$(OPENCLLIB)
      LIBS += -L$(OPENCLLIB)
      CONFIGPARAMS += --with-opencl
  endif
endif

ifndef CUDALIB
  ifndef OPENCLLIB
    $(error "Must define at least one of CUDALIB or OPENCLLIB")
  endif
endif

# these are picked up by the SHOC configure script
export MPICXX
export CFLAGS
export CXXFLAGS
export CPPFLAGS
export LDFLAGS
export LIBS

#SRC=shoc-1.0.3
SRC=shoc-1.1.1
TAR=$(SRC).tar.gz
URL=http://ft.ornl.gov/doku/_media/shoc/$(TAR)
SHOC=$(CBENCHOME)/opensource/shoc

# NORMAL MPI COMPILE
EXECS = $(SRC)
#EXECS = $(SRC)/bin/* $(SRC)/tools/driver.pl
default_tgt := all

INSTALLDIR = $(bin_dir)/shoc
INSTALLTARGETS = $(EXECS)

ENV_SETUP = LD_LIBRARY_PATH=$(CUDALIB):$(OPENCLLIB):$(LD_LIBRARY_PATH) PATH=$(CUDALIB)/../bin:$(OPENCLLIB)/../bin:$(MPIHOME)/bin:$(PATH) CXX=mpicxx 

default: $(default_tgt)

all: $(SRC)
	@cd src; $(ENV_SETUP) ./configure $(CONFIGPARAMS) --with-mpi
	$(ENV_SETUP) $(MAKE) -C $(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

clean:
	-[ -d $(SRC) ] && $(MAKE) -C $(SRC) clean

distclean:
	/bin/rm -rf $(SRC) src $(TAR)

install: default
	$(do-$@-shoc)

uninstall: default
	$(do-$@)

