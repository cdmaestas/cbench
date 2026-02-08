include ../../make.def

SRC=IOR-2.10.3
TAR=$(SRC).tgz
URL="http://downloads.sourceforge.net/project/ior-sio/IOR%20latest/$(SRC)/$(SRC).tgz"


INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(shell ls IOR.*)

default all: IOR.posix IOR.mpiio

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	mv IOR $@
	ln -s $@/src/C src
	@[ -d $@ ] && touch $@

IOR.posix: $(SRC)
	@echo "Compiling $(SRC) $@"
	$(MAKE) -C src CC.Linux=$(CC) posix >> .make-$(SRC) 2>&1
	/bin/cp -f src/IOR $@

IOR.mpiio: $(SRC)
	@echo "Compiling $(SRC) $@"
	$(MAKE) -C src CC.Linux=$(CC) mpiio >> .make-$(SRC) 2>&1
	/bin/cp -f src/IOR $@

clean:
	-[ -d $(SRC)/src/C ] && $(MAKE) -C src CC.Linux=$(CC) $@ >> .make-$(SRC) 2>&1
	/bin/rm -f IOR.* .make-$(SRC)

distclean: 
	/bin/rm -rf $(TAR) $(SRC) src .make-$(SRC)

install uninstall: default
	$(do-$@)
