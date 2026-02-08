include ../../make.def

SRC=bench
TAR=bench-0.985.tgz

EXECS = $(SRC)/bin/dplot*
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

default: .patched

download:

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.patched: $(SRC)
	@[ ! -f .patched ] && \
	for patch in *.patch ; do \
           cd $(SRC); \
           echo "Applying patch [ $$patch ]"; \
           patch -p1 <../$$patch; \
           cd - ; \
        done
	@touch .patched

clean distclean:
	/bin/rm -rf $(SRC) .patched src

install uninstall: default
	$(do-$@)

