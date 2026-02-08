include ../../make.def

VERSION=1.0.0
SRC=caldgemm-$(VERSION)
TAR=$(SRC).tar.bz2
URL="http://code.compeng.uni-frankfurt.de/attachments/download/8/$(TAR)"
CALDGEMMDIR="$(CBENCHOME)/opensource/CALDGEMM"

GOTOBLAS2VERSION=1.13
GOTOBLAS2SRC=GotoBLAS2-$(GOTOBLAS2VERSION)_bsd
GOTOBLAS2DIR="$(CBENCHOME)/opensource/GotoBLAS2"
GOTOBLAS2TAR="$(GOTOBLAS2DIR)/$(GOTOBLAS2SRC).tar.gz"

default: all

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	patch -p0 < rtlib.patch
	@[ -d $@ ] && touch $@

patchgoto2: $(SRC)
	@echo "Compiling patching GotoBLAS2"
	@if [ ! -f $(GOTOBLAS2TAR) ]; then \
		echo "Failed to find $(GOTOBLAS2TAR) ..."; exit 1; \
	else \
		cd $(CALDGEMMDIR); \
		[ -d GotoBLAS2 ] && rm -fr $(CALDGEMMDIR)/GotoBLAS2; \
		tar -xzf $(GOTOBLAS2TAR); cd GotoBLAS2; \
		patch -p0 < ../$(SRC)/gotoblas_patch/gotoblas.patch; \
		make NO_MEMPOLICY=1 -j; \
	fi \

all: patchgoto2
	@echo "Compiling $(SRC)"
	make CC=$(PLAINCC) -C src 

clean:
	/bin/rm -fr $(SRC)

distclean: clean
	/bin/rm -fr $(TAR) src GotoBLAS2 

install: default
	$(do-$@)

