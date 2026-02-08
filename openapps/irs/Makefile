include $(CBENCHOME)/make.def

SRC=irs.1.0
TAR=irs_v1.0.tar.gz
URL=https://asc.llnl.gov/sequoia/benchmarks/$(TAR)


EXECS = build.space/codes_opt/irs
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

IRS := $(shell pwd)

all: $(EXECS)

$(EXECS): $(SRC)
	pwd
	export PATH=$(IRS)/src/scripts:$(PATH); \
	  make CC=$(CC) CFLAGS="$(CFLAGS) $(OPENMP_ENABLE)" COMMON_FLAGS="$(COMMON_FLAGS) $(OPENMP_ENABLE)" -C build.space/build depend
	export PATH=$(IRS)/src/scripts:$(PATH); \
	  make CC=$(CC) CFLAGS="$(CFLAGS) $(OPENMP_ENABLE)" COMMON_FLAGS="$(COMMON_FLAGS) $(OPENMP_ENABLE)" -C build.space/build

$(SRC) src: $(TAR)
	-[ ! -d $(SRC) ] && tar zxf $(TAR)
	ln -sf $(SRC) src
	cd $(SRC)/build/arch; ln -sf ../../../make.cbench .
	perl src/scripts/irs_build build.space $(SRC)
	cd build.space/build; perl ../../$(SRC)/scripts/irs_config cbench
	cd $(SRC)/scripts; sed -i 's/local\/bin\/perl/bin\/perl/' irs_*
	cd $(SRC)/scripts; patch -p0 < ../../irs_hrcreate.patch
	touch $(SRC)

$(TAR) download:
	$(call download-wget-url,$(URL))
	-[ -e $(TAR) ] && touch $(TAR)

clean:
	export PATH=$(IRS)/src/scripts:$(PATH); \
	  make CC=$(CC) CFLAGS="$(CFLAGS) $(OPENMP_ENABLE)" COMMON_FLAGS="$(COMMON_FLAGS) $(OPENMP_ENABLE)" -C build.space/build clean
	/bin/rm $(EXECS)

distclean:
	/bin/rm -rf $(TAR) $(SRC) src build.space

install uninstall:
	$(do-$@)

include $(CBENCHOME)/make.inc
