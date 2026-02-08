include ../../make.def

VERSION=3_414
SRC=iozone$(VERSION)
TAR=$(SRC).tar
URL="http://www.iozone.org/src/current/$(TAR)"

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = src/src/current/iozone src/src/current/fileop

ifeq ($(ARCH),x86_64)
	TARGET=linux-AMD64
else
	TARGET=linux
endif

ifeq ($(COMPILER),intel)
	LDFLAGS += -i-static -static-libcxa -static
endif

default: src/src/current/iozone src/src/current/fileop

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	gzip -f $(TAR)
	$(call untar-src,$(TAR).gz)
	gzip -d $(TAR)
	ln -sf $@ src
	patch -p0 < make.patch
	@[ -d $@ ] && touch $@

all src/src/current/iozone src/src/current/fileop: $(SRC)
	$(MAKE) CC=$(PLAINCC) CFLAGS="$(CFLAGS)" LDFLAGS="$(LDFLAGS)" -C src/src/current $(TARGET) > .make-$(SRC) 2>&1
#	$(MAKE) all > .make-$(SRC) 2>&1

clean:
	-$(MAKE) -C src/src/current clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	-/bin/rm -rf $(SRC) $(TAR) src .make-$(SRC)

install uninstall: default
	$(do-$@)

