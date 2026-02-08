include ../../make.def

VERSION=1.0.1
SRC=hpl-gpu-$(VERSION)
TAR=$(SRC).tar.bz2
URL="http://code.compeng.uni-frankfurt.de/attachments/download/15/$(TAR)"
HPLGPU=$(CBENCHOME)/opensource/HPLinpack-gpu


install: $(SRC)
	$(do-$@)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	ln -sf $(HPLGPU)/Make.cbench $(HPLGPU)/$(SRC)/Make.cbench
	@[ -d $@ ] && touch $@

linpack: $(SRC)
	$(MAKE) -C $(SRC) arch=cbench

clean:
	-[ -d $(SRC) ] && /bin/rm -fr $(SRC)

distclean: clean
	-[ -f $(TAR) ] && /bin/rm -f $(TAR) 
	-[ -L src ] && /bin/rm -f src

